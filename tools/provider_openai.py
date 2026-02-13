"""OpenAI chat completions client implementation."""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Iterable, Mapping, cast

import openai
from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    PermissionDeniedError,
    RateLimitError,
)

from tools.config import OpenAISettings

Message = Mapping[str, str]


class OpenAIChatClient:
    """Thin wrapper around the OpenAI chat completions API."""

    def __init__(self, settings: OpenAISettings) -> None:
        self._settings = settings
        self._client = openai.OpenAI(api_key=settings.api_key)

    @property
    def model(self) -> str:
        return self._settings.model

    def complete(self, messages: Iterable[Message]) -> Dict[str, Any]:  # noqa: PLR0912
        """Execute completion with comprehensive error handling.

        Note: Multiple branches are intentional for detailed error handling.
        """
        delay = 1.0
        last_attempt = self._settings.max_retries - 1
        for attempt in range(self._settings.max_retries):
            try:
                client = cast(Any, self._client.chat.completions)
                payload = {
                    "model": self._settings.model,
                    "messages": list(messages),
                    "response_format": {"type": "json_object"},
                    "timeout": self._settings.timeout_seconds,
                }
                if self._settings.temperature is not None:
                    payload["temperature"] = self._settings.temperature
                response = client.create(**payload)
                content = response.choices[0].message.content or "{}"
                parsed = json.loads(content)
                if not isinstance(parsed, dict):
                    raise RuntimeError("LLM response is not a JSON object")
                return parsed
            except RateLimitError as exc:
                message = (
                    "OpenAI rate limit or quota exceeded. "
                    "Check billing settings or slow down requests."
                )
                raise RuntimeError(message) from exc
            except AuthenticationError as exc:
                raise RuntimeError(
                    "OpenAI authentication failed. Verify API key and organization."
                ) from exc
            except PermissionDeniedError as exc:
                raise RuntimeError(
                    "OpenAI permission denied. Ensure the key has access to the project."
                ) from exc
            except BadRequestError as exc:
                raise RuntimeError(f"OpenAI rejected the request: {exc}") from exc
            except (APIConnectionError, APITimeoutError) as exc:
                if attempt == last_attempt:
                    raise RuntimeError(
                        "Failed to connect to OpenAI after multiple retries."
                    ) from exc
            except APIError as exc:
                if attempt == last_attempt:
                    raise RuntimeError("OpenAI API error persisted after retries.") from exc
            except Exception:  # noqa: BLE001
                if attempt == last_attempt:
                    raise
            time.sleep(delay)
            delay *= 1.8
        raise RuntimeError("OpenAI client exceeded maximum retries")


def create_client(settings: OpenAISettings) -> OpenAIChatClient:
    return OpenAIChatClient(settings)


__all__ = ["OpenAIChatClient", "create_client"]
