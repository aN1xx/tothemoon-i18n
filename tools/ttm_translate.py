#!/usr/bin/env python3
"""CLI entry point for the ToTheMoon translation pipeline."""

from __future__ import annotations

import argparse
from pathlib import Path

from tools.config import AppSettings
from tools.pipeline import PipelineConfig, TranslationPipeline
from tools.provider_openai import create_client


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Batch translate UI JSON with context-aware prompts using two reference languages"
        ),
    )
    # Backward compatibility: keep --src for legacy usage
    parser.add_argument(
        "--src", help="[DEPRECATED] Use --source-en instead. Path to the source locale JSON"
    )
    parser.add_argument("--source-en", help="Path to the English (first reference) locale JSON")
    parser.add_argument("--source-ru", help="Path to the Russian (second reference) locale JSON")
    parser.add_argument("--dst", required=True, help="Path to the output translated locale JSON")
    parser.add_argument("--draft", help="Optional draft translation JSON to use as hint")
    parser.add_argument("--locale", help="Target locale code (overrides env)")
    parser.add_argument(
        "--glossary",
        help="Path to a glossary file (YAML/JSON); defaults to glossary/<locale>.yml",
    )
    parser.add_argument("--system-prompt", help="Path to the system prompt template")
    parser.add_argument("--fewshot", help="Path to few-shot examples JSON")
    parser.add_argument(
        "--batch-size",
        type=int,
        help="Number of keys per LLM request (25–50 recommended)",
    )
    parser.add_argument(
        "--batch-max-attempts",
        type=int,
        help="Retry attempts if the model misses keys in a batch",
    )
    parser.add_argument(
        "--min-delay",
        type=float,
        help="Seconds to wait between successful batch calls",
    )
    parser.add_argument(
        "--retry-delay",
        type=float,
        help="Seconds to wait before retrying a failed/incomplete batch",
    )
    parser.add_argument("--no-progress", action="store_true", help="Disable progress bar output")
    parser.add_argument(
        "--cache-file",
        help="Path to translation cache file (default: .translation_cache.json)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable translation cache",
    )
    parser.add_argument(
        "--single-reference-mode",
        action="store_true",
        help="Use only English reference (for initial EN→RU translation)",
    )
    return parser


def create_pipeline_config(args: argparse.Namespace, settings: "AppSettings") -> "PipelineConfig":
    locale = args.locale or settings.pipeline.locale
    glossary_path = Path(args.glossary) if args.glossary else settings.pipeline.glossary_path
    if glossary_path is None:
        locale_glossary = Path("glossary") / f"{locale}.yml"
        default_glossary = Path("glossary") / "default.yml"
        if locale_glossary.exists():
            glossary_path = locale_glossary
        elif default_glossary.exists():
            glossary_path = default_glossary
    system_prompt_path = (
        Path(args.system_prompt)
        if args.system_prompt
        else settings.pipeline.system_prompt_path or Path("prompts/system.txt")
    )
    fewshot_path = Path(args.fewshot) if args.fewshot else settings.pipeline.fewshot_path
    if fewshot_path is None:
        locale_fewshot = Path("prompts") / "fewshot" / f"{locale}.json"
        default_fewshot = Path("prompts/fewshot.json")
        fewshot_path = locale_fewshot if locale_fewshot.exists() else default_fewshot
    batch_size = args.batch_size or settings.pipeline.batch_size
    batch_max_attempts = args.batch_max_attempts or settings.pipeline.batch_max_attempts
    min_delay = (
        args.min_delay if args.min_delay is not None else settings.pipeline.min_delay_seconds
    )
    retry_delay = (
        args.retry_delay if args.retry_delay is not None else settings.pipeline.retry_delay_seconds
    )

    # Cache configuration
    cache_file = Path(args.cache_file) if args.cache_file else Path(".translation_cache.json")
    use_cache = not args.no_cache
    single_reference_mode = getattr(args, "single_reference_mode", False)

    return PipelineConfig(
        locale=locale,
        batch_size=batch_size,
        batch_max_attempts=batch_max_attempts,
        min_delay_seconds=min_delay,
        retry_delay_seconds=retry_delay,
        glossary_path=glossary_path,
        system_prompt_path=system_prompt_path,
        fewshot_path=fewshot_path,
        show_progress=not args.no_progress,
        cache_file=cache_file,
        use_cache=use_cache,
        single_reference_mode=single_reference_mode,
    )


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    settings = AppSettings.load()
    pipeline_config = create_pipeline_config(args, settings)
    client = create_client(settings.openai)
    pipeline = TranslationPipeline(client, pipeline_config)

    # Handle source paths (backward compatibility with --src)
    single_ref_mode = getattr(args, "single_reference_mode", False)

    if args.source_en and args.source_ru:
        source_en_path = Path(args.source_en)
        source_ru_path = Path(args.source_ru)
    elif args.source_en and single_ref_mode:
        # Single-reference mode: only English is required
        source_en_path = Path(args.source_en)
        source_ru_path = None
        print("[info] Single-reference mode enabled: using only English reference")
    elif args.src:
        # Legacy mode: assume --src is English, try to find Russian automatically
        source_en_path = Path(args.src)
        # Try to find Russian file automatically (TTM_RU.json if TTM_EN.json provided)
        src_name = source_en_path.name
        if "EN" in src_name.upper():
            source_ru_path = source_en_path.parent / src_name.replace("EN", "RU").replace(
                "en", "ru"
            )
        else:
            source_ru_path = source_en_path.parent / "TTM_RU.json"

        if not source_ru_path.exists():
            if single_ref_mode:
                source_ru_path = None
                print(
                    "[info] Single-reference mode: Russian file not found, proceeding with EN only"
                )
            else:
                print("[error] --src is deprecated. Please use --source-en and --source-ru.")
                print(f"[error] Could not auto-detect Russian reference file at {source_ru_path}")
                return 1
        else:
            print(
                f"[warn] --src is deprecated. Using --source-en={source_en_path} "
                f"and --source-ru={source_ru_path}"
            )
    else:
        print(
            "[error] Must provide either --source-en and --source-ru, "
            "or --source-en with --single-reference-mode"
        )
        return 1

    dst_path = Path(args.dst)
    draft_path = Path(args.draft) if args.draft else None

    try:
        pipeline.run(source_en_path, source_ru_path, dst_path, draft_path)
    except RuntimeError as exc:
        print(f"[error] {exc}")
        return 2
    print(f"[ok] wrote {dst_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
