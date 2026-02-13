#!/usr/bin/env python3
"""Generate starter glossary and few-shot examples for a new locale."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple, cast

import yaml

from tools.batcher import infer_intent
from tools.config import AppSettings, load_language_names
from tools.provider_openai import create_client
from tools.structures import get_value, iter_string_nodes, path_to_key

DEFAULT_SAMPLES = 12
DEFAULT_OUTPUT_DIR = Path("prompts") / "fewshot"
DEFAULT_GLOSSARY_DIR = Path("glossary")
SYSTEM_PROMPT = (
    "You are a senior localization strategist for cryptocurrency products. "
    "Given a target locale and representative UI strings, propose a starter glossary "
    "with accurate terminology and a handful of high-quality EN→target examples. "
    "Focus on crypto/fintech UI tone, keep placeholders intact, and avoid literal calques. "
    "Respond with a JSON object containing two arrays:\n"
    "- glossary: objects with fields term (English source) and translation (target language).\n"
    "- fewshot: objects with fields key, en, target.\n"
    "Do not include notes or commentary outside the JSON object."
)


def friendly_name(locale: str) -> str:
    """Get friendly language name from locale code."""
    language_names = load_language_names()
    return language_names.get(locale.lower(), locale)


def collect_samples(
    source: Dict[str, Any], sample_size: int, draft: Dict[str, Any]
) -> List[Dict[str, Any]]:
    intent_buckets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    flat_samples: List[Dict[str, Any]] = []
    for path, text in iter_string_nodes(source):
        key = path_to_key(path)
        intent = infer_intent(key, text)
        draft_value = get_value(draft, path)
        sample = {
            "key": key,
            "en": text,
            "intent": intent,
        }
        if isinstance(draft_value, str) and draft_value.strip():
            sample["existing_translation"] = draft_value
        intent_buckets[intent].append(sample)
        flat_samples.append(sample)

    selected: List[Dict[str, Any]] = []
    # Ensure at least one sample per intent if possible
    for bucket in intent_buckets.values():
        if len(selected) >= sample_size:
            break
        selected.append(bucket[0])
    # Fill the rest with remaining samples preserving original order
    if len(selected) < sample_size:
        seen_keys = {item["key"] for item in selected}
        for sample in flat_samples:
            if sample["key"] in seen_keys:
                continue
            selected.append(sample)
            if len(selected) >= sample_size:
                break
    return selected[:sample_size]


def build_messages(
    locale: str, language: str, samples: List[Dict[str, Any]], base_glossary: Dict[str, str]
) -> List[Dict[str, str]]:
    context = {
        "target_locale": locale,
        "target_language": language,
        "samples": samples,
        "existing_glossary": base_glossary,
        "instructions": (
            "Generate 8-15 glossary entries prioritizing recurring crypto/UI terms. "
            "Provide 4-6 few-shot examples covering different intents."
        ),
    }
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
    ]


def normalize_glossary(glossary_data: Any) -> Dict[str, str]:
    glossary: Dict[str, str] = {}
    if isinstance(glossary_data, dict):
        for term, translation in glossary_data.items():
            if isinstance(term, str) and isinstance(translation, str) and translation.strip():
                glossary[term.strip()] = translation.strip()
    elif isinstance(glossary_data, list):
        for item in glossary_data:
            if not isinstance(item, dict):
                continue
            term = item.get("term")
            translation = item.get("translation")
            if isinstance(term, str) and isinstance(translation, str) and translation.strip():
                glossary[term.strip()] = translation.strip()
    return glossary


def normalize_fewshot(fewshot_data: Any) -> List[Dict[str, str]]:
    fewshot: List[Dict[str, str]] = []
    iterator: Iterable[Tuple[Any, Any]]
    if isinstance(fewshot_data, dict):
        iterator = fewshot_data.items()
    elif isinstance(fewshot_data, list):
        iterator = enumerate(fewshot_data)
    else:
        iterator = cast(Iterable[Tuple[Any, Any]], [])
    for key, payload in iterator:
        if isinstance(payload, dict):
            entry = {
                "key": str(payload.get("key", key)),
                "en": str(payload.get("en", "")),
                "target": str(payload.get("target") or payload.get("translation", "")),
            }
        else:
            entry = {
                "key": str(key),
                "en": str(payload),
                "target": str(payload),
            }
        if entry["key"] and entry["en"] and entry["target"]:
            fewshot.append(entry)
    return fewshot


def write_glossary(path: Path, glossary: Dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(glossary, handle, allow_unicode=True, sort_keys=True)


def write_fewshot(path: Path, fewshot: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(fewshot, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bootstrap glossary and few-shot examples for a locale"
    )
    parser.add_argument("--locale", required=True, help="Locale code (e.g. es, de, pt-br)")
    parser.add_argument(
        "--target-language", help="Readable language name (defaults to known mapping)"
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=DEFAULT_SAMPLES,
        help="Number of sample strings to feed the model",
    )
    parser.add_argument("--glossary-out", help="Output path for glossary YAML")
    parser.add_argument("--fewshot-out", help="Output path for few-shot JSON")
    parser.add_argument("--source", default="data/TTM_EN.json", help="Path to source EN JSON")
    parser.add_argument(
        "--draft", help="Optional draft translation JSON to surface existing translations"
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    parser.add_argument(
        "--dry-run", action="store_true", help="Print results without writing files"
    )
    return parser.parse_args()


def load_json_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return data
    raise TypeError(f"Expected JSON object at {path}, got {type(data).__name__}")


def resolve_output_paths(args: argparse.Namespace) -> Tuple[Path, Path]:
    locale = args.locale
    glossary_path = (
        Path(args.glossary_out) if args.glossary_out else DEFAULT_GLOSSARY_DIR / f"{locale}.yml"
    )
    fewshot_path = (
        Path(args.fewshot_out) if args.fewshot_out else DEFAULT_OUTPUT_DIR / f"{locale}.json"
    )
    return glossary_path, fewshot_path


def ensure_writable(glossary_path: Path, fewshot_path: Path, force: bool) -> None:
    if force:
        return
    
    existing_files = []
    if glossary_path.exists():
        existing_files.append(str(glossary_path))
    if fewshot_path.exists():
        existing_files.append(str(fewshot_path))
    
    if existing_files:
        error_msg = (
            "\n\n❌ Files already exist:\n"
            + "\n".join(f"  - {f}" for f in existing_files)
            + "\n\n💡 To regenerate them, use:\n"
            + f"   make bootstrap-locale LOCALE={glossary_path.stem} TARGET_LANG=\"...\" --force\n"
            + "\n   Or add FORCE=1 to the make command:\n"
            + f"   make bootstrap-locale LOCALE={glossary_path.stem} TARGET_LANG=\"...\" FORCE=1\n"
        )
        raise FileExistsError(error_msg)


def load_base_glossary() -> Dict[str, str]:
    base_path = DEFAULT_GLOSSARY_DIR / "default.yml"
    if not base_path.exists():
        return {}
    loaded_glossary = yaml.safe_load(base_path.read_text(encoding="utf-8")) or {}
    if not isinstance(loaded_glossary, dict):
        return {}
    return {
        str(term): str(value)
        for term, value in loaded_glossary.items()
        if isinstance(term, str) and isinstance(value, str)
    }


def output_results(
    glossary: Dict[str, str],
    fewshot: List[Dict[str, str]],
    glossary_path: Path,
    fewshot_path: Path,
    dry_run: bool,
) -> None:
    if dry_run:
        print("# Glossary proposal")
        print(yaml.safe_dump(glossary, allow_unicode=True, sort_keys=True))
        print("# Few-shot proposal")
        print(json.dumps(fewshot, ensure_ascii=False, indent=2))
        return
    write_glossary(glossary_path, glossary)
    write_fewshot(fewshot_path, fewshot)
    print(f"[ok] Wrote glossary → {glossary_path}")
    print(f"[ok] Wrote few-shot → {fewshot_path}")


def main() -> int:
    args = parse_arguments()

    locale = args.locale
    language = args.target_language or friendly_name(locale)

    source_path = Path(args.source)
    source_data = load_json_file(source_path)
    draft_data: Dict[str, Any] = {}
    if args.draft:
        draft_path = Path(args.draft)
        if draft_path.exists():
            draft_data = load_json_file(draft_path)

    samples = collect_samples(source_data, max(3, args.sample_size), draft_data)
    glossary_path, fewshot_path = resolve_output_paths(args)
    ensure_writable(glossary_path, fewshot_path, args.force)
    base_glossary = load_base_glossary()

    settings = AppSettings.load()
    client = create_client(settings.openai)
    messages = build_messages(locale, language, samples, base_glossary)
    response = client.complete(messages)

    glossary = normalize_glossary(response.get("glossary"))
    fewshot = normalize_fewshot(response.get("fewshot"))

    if not glossary:
        raise RuntimeError("Model did not return glossary entries")
    if not fewshot:
        raise RuntimeError("Model did not return few-shot examples")

    output_results(glossary, fewshot, glossary_path, fewshot_path, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
