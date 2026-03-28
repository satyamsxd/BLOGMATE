"""
Blogy — Base Provider Interface
Abstract base class that all LLM providers must implement.
"""

from abc import ABC, abstractmethod


class BaseProvider(ABC):
    """
    Unified interface for all LLM providers.
    Every provider must implement chat_completion().
    """

    name: str = "base"
    is_free_tier: bool = False

    @abstractmethod
    def chat_completion(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """
        Send a chat completion request and return the response text.

        Args:
            messages: List of {"role": ..., "content": ...} dicts
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response

        Returns:
            The response text content as a string.

        Raises:
            Exception on failure (will trigger fallback).
        """
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if this provider has a valid API key configured."""
        pass

    def __repr__(self):
        return f"<{self.__class__.__name__} name={self.name} free={self.is_free_tier}>"
