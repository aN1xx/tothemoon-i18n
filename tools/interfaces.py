"""Core interfaces for dependency inversion."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping, Protocol

Message = Mapping[str, str]


class LLMClient(Protocol):
    """Protocol for language model clients used by the translation pipeline.

    This protocol defines the interface that all LLM providers must implement.
    It allows for easy swapping between different providers (OpenAI, Anthropic, etc.)
    without changing the core translation pipeline logic.
    """

    @property
    def model(self) -> str:
        """Return the model identifier (e.g., 'gpt-4o-mini', 'claude-3-sonnet')."""
        ...

    def complete(self, messages: Iterable[Message]) -> Dict[str, Any]:
        """Execute a chat completion request and return a JSON object payload.

        Args:
            messages: Iterable of message mappings with 'role' and 'content' keys

        Returns:
            Dictionary with LLM response data (can contain nested structures)

        Raises:
            RuntimeError: If the API call fails after retries
        """
        ...


__all__ = ["LLMClient", "Message"]
