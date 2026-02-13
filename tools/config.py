"""Configuration helpers for the translation toolkit."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

import yaml

try:
    from dotenv import load_dotenv
except ImportError as exc:  # pragma: no cover - import guard
    raise RuntimeError(
        "python-dotenv is required. Install dependencies via 'make install'."
    ) from exc

DEFAULT_LOCALE = "ru"
DEFAULT_BATCH_SIZE = 40
DEFAULT_BATCH_MAX_ATTEMPTS = 2
DEFAULT_MIN_DELAY_SECONDS = 1.5
DEFAULT_RETRY_DELAY_SECONDS = 2.0
DEFAULT_MODEL = "gpt-4.1-mini"
DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_MAX_RETRIES = 5


load_dotenv()


@dataclass(frozen=True)
class OpenAISettings:
    """Settings container for the OpenAI client."""

    api_key: str
    model: str = DEFAULT_MODEL
    max_retries: int = DEFAULT_MAX_RETRIES
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    temperature: Optional[float] = None

    @classmethod
    def from_env(cls) -> "OpenAISettings":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not configured. Set it in the environment or .env file."
            )
        model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
        max_retries = _get_int("OPENAI_MAX_RETRIES", DEFAULT_MAX_RETRIES)
        timeout_seconds = _get_int("OPENAI_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)
        temperature = _get_optional_float("OPENAI_TEMPERATURE")
        return cls(
            api_key=api_key,
            model=model,
            max_retries=max_retries,
            timeout_seconds=timeout_seconds,
            temperature=temperature,
        )


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be an integer, got: {raw}") from exc


def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be a float, got: {raw}") from exc


def _get_optional_float(name: str) -> Optional[float]:
    raw = os.getenv(name)
    if not raw:
        return None
    assert isinstance(raw, str)  # Type guard for mypy
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be a float, got: {raw}") from exc


@dataclass(frozen=True)
class PipelineSettings:
    """Runtime knobs for the translation pipeline."""

    locale: str = DEFAULT_LOCALE
    batch_size: int = DEFAULT_BATCH_SIZE
    batch_max_attempts: int = DEFAULT_BATCH_MAX_ATTEMPTS
    min_delay_seconds: float = DEFAULT_MIN_DELAY_SECONDS
    retry_delay_seconds: float = DEFAULT_RETRY_DELAY_SECONDS
    glossary_path: Optional[Path] = None
    system_prompt_path: Optional[Path] = None
    fewshot_path: Optional[Path] = None

    @classmethod
    def from_env(cls) -> "PipelineSettings":
        locale = os.getenv("TRANSLATION_LOCALE", DEFAULT_LOCALE)
        batch_size = _get_int("TRANSLATION_BATCH_SIZE", DEFAULT_BATCH_SIZE)
        batch_max_attempts = _get_int("TRANSLATION_BATCH_MAX_ATTEMPTS", DEFAULT_BATCH_MAX_ATTEMPTS)
        min_delay = _get_float("TRANSLATION_MIN_DELAY_SECONDS", DEFAULT_MIN_DELAY_SECONDS)
        retry_delay = _get_float("TRANSLATION_RETRY_DELAY_SECONDS", DEFAULT_RETRY_DELAY_SECONDS)
        glossary = _get_path("TRANSLATION_GLOSSARY_PATH")
        system_prompt = _get_path("TRANSLATION_SYSTEM_PROMPT_PATH")
        fewshot = _get_path("TRANSLATION_FEWSHOT_PATH")
        return cls(
            locale=locale,
            batch_size=batch_size,
            batch_max_attempts=batch_max_attempts,
            min_delay_seconds=min_delay,
            retry_delay_seconds=retry_delay,
            glossary_path=glossary,
            system_prompt_path=system_prompt,
            fewshot_path=fewshot,
        )


def _get_path(name: str) -> Optional[Path]:
    raw = os.getenv(name)
    if not raw:
        return None
    return Path(raw)


@dataclass(frozen=True)
class AppSettings:
    """Aggregates configuration needed by the CLI entry points."""

    openai: OpenAISettings
    pipeline: PipelineSettings

    @classmethod
    def load(cls) -> "AppSettings":
        return cls(OpenAISettings.from_env(), PipelineSettings.from_env())


def load_language_names() -> Dict[str, str]:
    """Load language code to name mapping from config/languages.yml."""
    languages_file = Path("config/languages.yml")
    if not languages_file.exists():
        # Fallback to embedded defaults if file doesn't exist
        return {
            "ru": "Russian",
            "en": "English",
            "es": "Spanish",
            "de": "German",
            "fr": "French",
            "pt-br": "Brazilian Portuguese",
            "tr": "Turkish",
            "zh-cn": "Simplified Chinese",
        }

    try:
        data = yaml.safe_load(languages_file.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "languages" not in data:
            raise ValueError("languages.yml must contain a 'languages' mapping")
        return {str(k).lower(): str(v) for k, v in data["languages"].items()}
    except Exception as e:
        raise RuntimeError(f"Failed to load language configuration: {e}") from e


__all__ = ["AppSettings", "OpenAISettings", "PipelineSettings", "load_language_names"]
