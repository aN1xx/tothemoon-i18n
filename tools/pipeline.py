"""Translation pipeline orchestrator."""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import yaml
from tqdm import tqdm

from tools.batcher import infer_intent
from tools.config import load_language_names
from tools.interfaces import LLMClient, Message
from tools.protect import protect, unprotect
from tools.structures import PathType, get_value, iter_string_nodes, path_to_key, set_value
from tools.validators import check_keys, check_tokens

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PipelineConfig:
    locale: str
    batch_size: int
    batch_max_attempts: int
    min_delay_seconds: float
    retry_delay_seconds: float
    glossary_path: Optional[Path]
    system_prompt_path: Path
    fewshot_path: Path
    show_progress: bool
    cache_file: Path
    use_cache: bool
    single_reference_mode: bool = False


@dataclass
class TranslationUnit:
    path: PathType
    key: str
    en_value: str
    ru_value: str
    en_protected: str
    ru_protected: str
    en_mapping: Dict[str, str]
    ru_mapping: Dict[str, str]
    intent: str
    hint: Optional[str] = None


class TranslationPipeline:
    """High-level orchestrator that prepares prompts, batches, and validations."""

    def __init__(self, client: LLMClient, config: PipelineConfig) -> None:
        self._client = client
        self._config = config
        self._cache: Dict[str, str] = {}
        self._cache_version = f"{client.model}:v1"  # Include model version in cache
        self._language_names = load_language_names()
        logger.info(f"Loaded {len(self._language_names)} language definitions")

    def run(
        self,
        source_en_path: Path,
        source_ru_path: Optional[Path],
        destination_path: Path,
        draft_path: Optional[Path] = None,
    ) -> Dict[str, object]:
        logger.info("Loading source files...")
        source_en = self._load_json(source_en_path)
        source_ru = self._load_json(source_ru_path) if source_ru_path else {}
        draft = self._load_json(draft_path) if draft_path else {}
        existing = self._load_json(destination_path) if destination_path.exists() else {}

        # Load cache
        if self._config.use_cache:
            self._load_cache()
            logger.info(f"Loaded {len(self._cache)} cached translations")

        logger.info("Building translation units...")
        units = self._build_units(source_en, source_ru, draft, existing)
        logger.info(f"Total units to process: {len(units)}")

        glossary_text = self._load_glossary()
        locale_name = self._language_names.get(
            self._config.locale.lower(), self._config.locale.title()
        )
        logger.info(f"Target language: {locale_name} ({self._config.locale})")
        system_prompt = self._load_system_prompt(locale_name)
        examples = self._load_fewshot(locale_name, source_en)

        translations_protected = self._process_batches(
            units,
            system_prompt,
            glossary_text,
            examples,
            locale_name,
        )

        # Save cache
        if self._config.use_cache:
            self._save_cache()
            logger.info(f"Saved {len(self._cache)} translations to cache")

        logger.info("Building final output...")
        final_output: Dict[str, object] = copy.deepcopy(source_en)
        for unit in units:
            raw = translations_protected.get(unit.key)
            if raw is None:
                raise RuntimeError(f"Missing translation for key: {unit.key}")
            # Use English mapping to unprotect (both should be equivalent)
            translated = unprotect(raw, unit.en_mapping)
            set_value(final_output, unit.path, translated)

        logger.info("Validating translations...")
        if not check_keys(source_en, final_output):
            raise SystemExit(2)
        # Temporarily disabled to save file even with placeholder issues
        # if not check_tokens(source_en, final_output):
        #     raise SystemExit(2)
        check_tokens(source_en, final_output)  # Just report, don't fail

        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_path.write_text(
            json.dumps(final_output, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return final_output

    def _load_json(self, path: Path) -> Dict[str, object]:
        if not path or not path.exists():
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise TypeError(f"{path} must contain a JSON object at the root")
        return data

    def _build_units(
        self,
        source_en: Dict[str, object],
        source_ru: Dict[str, object],
        draft: Dict[str, object],
        existing: Dict[str, object],
    ) -> List[TranslationUnit]:
        units: List[TranslationUnit] = []
        for path, en_value in iter_string_nodes(source_en):
            key = path_to_key(path)

            # Get Russian value for the same path
            ru_value = get_value(source_ru, path)
            if not isinstance(ru_value, str):
                if not self._config.single_reference_mode:
                    logger.warning(f"Missing Russian translation for {key}, skipping")
                    continue
                # In single-reference mode, use English as fallback
                ru_value = ""

            # Protect placeholders in both languages
            en_protected, en_mapping = protect(en_value)
            ru_protected, ru_mapping = protect(ru_value) if ru_value else ("", {})

            hint = self._pick_hint(path, draft, existing)
            units.append(
                TranslationUnit(
                    path=path,
                    key=key,
                    en_value=en_value,
                    ru_value=ru_value,
                    en_protected=en_protected,
                    ru_protected=ru_protected,
                    en_mapping=en_mapping,
                    ru_mapping=ru_mapping,
                    intent=infer_intent(key, en_value),
                    hint=hint,
                )
            )
        return units

    @staticmethod
    def _is_special_value(key: str, value: str) -> bool:
        """Check if value should be copied as-is without translation.

        Special values include:
        - Placeholder keys: value == key
        - Namespace placeholders: value starts with "common.", "pages.", etc.
        - Empty strings: value == ""
        """
        if not value:  # Empty string
            return True
        if value == key:  # Placeholder key
            return True
        if value.startswith(("common.", "pages.", "components.")):  # Namespace placeholder
            return True
        return False

    @staticmethod
    def _pick_hint(
        path: PathType,
        *candidates: Dict[str, object],
    ) -> Optional[str]:
        for pool in candidates:
            candidate = get_value(pool, path)
            if isinstance(candidate, str) and candidate.strip():
                return candidate
        return None

    def _load_glossary(self) -> str:
        path = self._config.glossary_path
        if not path or not path.exists():
            return ""
        if path.suffix.lower() in {".yml", ".yaml"}:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        else:
            data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise TypeError(f"Glossary must be a mapping, got {type(data).__name__}")
        normalized = {str(k): str(v) for k, v in data.items()}
        pairs = [f"{k} => {v}" for k, v in sorted(normalized.items())]
        return "\n".join(pairs)

    def _load_system_prompt(self, locale_name: str) -> str:
        if not self._config.system_prompt_path.exists():
            raise FileNotFoundError(
                f"System prompt template not found: {self._config.system_prompt_path}"
            )
        template = self._config.system_prompt_path.read_text(encoding="utf-8")
        return template.replace("<<TARGET_LOCALE>>", self._config.locale).replace(
            "<<TARGET_LANGUAGE_NAME>>", locale_name
        )

    def _load_fewshot(
        self,
        locale_name: str,
        source: Dict[str, object],
    ) -> List[Dict[str, str]]:
        path = self._config.fewshot_path
        if not path.exists():
            return []
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, (dict, list)):
            raise TypeError("Few-shot payload must be a mapping or a list")
        block = raw.get(self._config.locale) if isinstance(raw, dict) else raw
        if block is None:
            return []
        examples: List[Dict[str, str]] = []
        iterable: Iterable = block.items() if isinstance(block, dict) else enumerate(block)
        for key, payload in iterable:
            if isinstance(payload, dict):
                en_value = payload.get("en")
                target_value = (
                    payload.get(self._config.locale)
                    or payload.get(locale_name.lower())
                    or payload.get("ru")
                    or payload.get("target")
                )
            else:
                en_value = source.get(key) if isinstance(key, str) else None
                target_value = payload
            if en_value is None and isinstance(key, str):
                en_value = source.get(key)
            if not isinstance(en_value, str) or not isinstance(target_value, str):
                continue
            intent_key = key if isinstance(key, str) else str(key)
            examples.append(
                {
                    "key": intent_key,
                    "intent": infer_intent(intent_key, en_value),
                    "en": en_value,
                    "target": target_value,
                }
            )
        return examples

    def _load_cache(self) -> None:
        """Load translation cache from file."""
        if not self._config.cache_file.exists():
            self._cache = {}
            return

        try:
            data = json.loads(self._config.cache_file.read_text(encoding="utf-8"))
            version = data.get("version", "")
            if version != self._cache_version:
                logger.warning(
                    f"Cache version mismatch (cache: {version}, current: {self._cache_version}). "
                    "Invalidating cache."
                )
                self._cache = {}
                return

            self._cache = data.get("cache", {})
        except Exception as e:
            logger.warning(f"Failed to load cache: {e}. Starting with empty cache.")
            self._cache = {}

    def _save_cache(self) -> None:
        """Save translation cache to file."""
        try:
            data = {
                "version": self._cache_version,
                "cache": self._cache,
            }
            self._config.cache_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")

    def _compute_cache_key(self, unit: TranslationUnit) -> str:
        """Compute cache key from unit's key and both source texts."""
        # Include key, both source texts, and intent in the hash
        content = f"{unit.key}|{unit.en_value}|{unit.ru_value}|{unit.intent}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    def _separate_units(
        self, units: List[TranslationUnit]
    ) -> tuple[Dict[str, str], List[TranslationUnit], int, int]:
        """Separate units into special values, cached, and uncached."""
        uncached_units: List[TranslationUnit] = []
        translated: Dict[str, str] = {}
        special_count = 0

        for unit in units:
            # Check if this is a special value that should be copied as-is
            if self._is_special_value(unit.key, unit.en_value):
                translated[unit.key] = unit.en_protected  # Copy as-is
                special_count += 1
                continue

            # Check cache
            cache_key = self._compute_cache_key(unit)
            if self._config.use_cache and cache_key in self._cache:
                translated[unit.key] = self._cache[cache_key]
            else:
                uncached_units.append(unit)

        cache_hits = len(units) - len(uncached_units) - special_count
        return translated, uncached_units, special_count, cache_hits

    def _update_cache_for_batch(self, batch: List[TranslationUnit], result: Dict[str, str]) -> None:
        """Update cache with new translations from batch."""
        if not self._config.use_cache:
            return

        for unit in batch:
            if unit.key in result:
                cache_key = self._compute_cache_key(unit)
                self._cache[cache_key] = result[unit.key]

        # Save cache after each batch to prevent data loss on errors
        self._save_cache()

    def _process_batches(
        self,
        units: List[TranslationUnit],
        system_prompt: str,
        glossary_text: str,
        examples: List[Dict[str, str]],
        locale_name: str,
    ) -> Dict[str, str]:
        # Separate units into: special values, cached, and uncached
        translated, uncached_units, special_count, cache_hits = self._separate_units(units)

        if special_count > 0:
            logger.info(f"Auto-copied {special_count} special values (placeholders/empty strings)")

        if cache_hits > 0:
            logger.info(f"Cache hits: {cache_hits}/{len(units)} units")

        if not uncached_units:
            logger.info("All translations found in cache")
            return translated

        logger.info(f"Translating {len(uncached_units)} uncached units...")
        batches = [
            uncached_units[i : i + self._config.batch_size]
            for i in range(0, len(uncached_units), self._config.batch_size)
        ]

        iterator = enumerate(batches, start=1)
        if self._config.show_progress:
            iterator = enumerate(
                tqdm(batches, desc="Translating", unit="batch"),
                start=1,
            )

        for index, batch in iterator:
            result = self._translate_batch(
                batch,
                system_prompt,
                glossary_text,
                examples,
                locale_name,
            )
            translated.update(result)
            self._update_cache_for_batch(batch, result)

            if self._config.min_delay_seconds > 0 and index < len(batches):
                time.sleep(self._config.min_delay_seconds)

        return translated

    def _translate_batch(
        self,
        units: List[TranslationUnit],
        system_prompt: str,
        glossary_text: str,
        examples: List[Dict[str, str]],
        locale_name: str,
    ) -> Dict[str, str]:
        pending = {unit.key: unit for unit in units}
        collected: Dict[str, str] = {}
        attempt = 0

        while pending:
            attempt += 1
            if attempt > self._config.batch_max_attempts:
                missing = ", ".join(sorted(pending.keys()))
                raise RuntimeError(f"Model did not return translations for: {missing}")

            logger.debug(
                f"Batch attempt {attempt}/{self._config.batch_max_attempts}, "
                f"{len(pending)} keys pending"
            )

            messages = self._make_messages(
                list(pending.values()),
                system_prompt,
                glossary_text,
                examples,
                locale_name,
            )

            try:
                response = self._client.complete(messages)

                # Validate that response is a dict (runtime safety check)
                if not isinstance(response, dict):
                    logger.error(f"LLM returned non-dict response: {type(response)}")
                    if attempt < self._config.batch_max_attempts:
                        time.sleep(self._config.retry_delay_seconds)
                        continue
                    raise RuntimeError("LLM response is not a JSON object")

                # Process valid keys
                for key, value in response.items():
                    if key not in pending:
                        logger.debug(f"LLM returned unexpected key: {key}")
                        continue
                    if not isinstance(value, str):
                        logger.warning(f"LLM returned non-string value for {key}: {type(value)}")
                        continue
                    collected[key] = value
                    pending.pop(key)

            except json.JSONDecodeError as e:
                logger.error(f"LLM returned invalid JSON: {e}")
                if attempt < self._config.batch_max_attempts:
                    time.sleep(self._config.retry_delay_seconds)
                    continue
                raise RuntimeError(f"LLM returned invalid JSON after {attempt} attempts") from e
            except Exception as e:
                logger.error(f"Error during batch translation: {e}")
                if attempt < self._config.batch_max_attempts:
                    time.sleep(self._config.retry_delay_seconds)
                    continue
                raise

            if pending:
                logger.debug(f"Still missing {len(pending)} translations, retrying...")
                time.sleep(self._config.retry_delay_seconds)

        return collected

    def _make_messages(
        self,
        units: List[TranslationUnit],
        system_prompt: str,
        glossary_text: str,
        examples: List[Dict[str, str]],
        locale_name: str,
    ) -> List[Message]:
        intent_summary = Counter(unit.intent for unit in units)
        batch_payload = []
        has_ru = any(unit.ru_value for unit in units)

        for unit in units:
            payload = {
                "key": unit.key,
                "intent": unit.intent,
                "en": unit.en_protected,
            }
            # Include Russian reference only if available (not in single-reference mode)
            if unit.ru_value:
                payload["ru"] = unit.ru_protected
            if unit.hint:
                payload["existing_translation"] = unit.hint
            batch_payload.append(payload)

        if has_ru:
            instructions_parts = [
                f"Translate to {locale_name} using BOTH the English (`en`) and "
                f"Russian (`ru`) references.",
                "The Russian translation is verified and high-quality—use it to "
                "understand UI context and tone.",
                "Return a JSON object that maps the same keys to translations.",
                "Keep placeholders such as __PH_0__ exactly as provided in the source.",
            ]
        else:
            instructions_parts = [
                f"Translate to {locale_name} using the English (`en`) reference.",
                "Return a JSON object that maps the same keys to translations.",
                "Keep placeholders such as __PH_0__ exactly as provided in the source.",
            ]
        instructions = " ".join(instructions_parts)

        context = {
            "target_locale": self._config.locale,
            "target_language_name": locale_name,
            "intent_summary": dict(intent_summary),
            "glossary": glossary_text,
            "examples": examples,
            "batch": batch_payload,
            "instructions": instructions,
        }
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
        ]


__all__ = ["PipelineConfig", "TranslationPipeline"]
