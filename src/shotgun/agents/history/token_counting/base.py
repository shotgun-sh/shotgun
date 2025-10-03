"""Base classes and shared utilities for token counting."""

from abc import ABC, abstractmethod

from pydantic_ai.messages import ModelMessage


class TokenCounter(ABC):
    """Abstract base class for provider-specific token counting.

    All methods are async to support non-blocking operations like
    downloading tokenizer models or making API calls.
    """

    @abstractmethod
    async def count_tokens(self, text: str) -> int:
        """Count tokens in text using provider-specific method (async).

        Args:
            text: Text to count tokens for

        Returns:
            Exact token count as determined by the provider

        Raises:
            RuntimeError: If token counting fails
        """

    @abstractmethod
    async def count_message_tokens(self, messages: list[ModelMessage]) -> int:
        """Count tokens in PydanticAI message structures (async).

        Args:
            messages: List of messages to count tokens for

        Returns:
            Total token count across all messages

        Raises:
            RuntimeError: If token counting fails
        """


def extract_text_from_messages(messages: list[ModelMessage]) -> str:
    """Extract all text content from messages for token counting.

    Args:
        messages: List of PydanticAI messages

    Returns:
        Combined text content from all messages
    """
    text_parts = []

    for message in messages:
        if hasattr(message, "parts"):
            for part in message.parts:
                if hasattr(part, "content") and isinstance(part.content, str):
                    text_parts.append(part.content)
                else:
                    # Handle non-text parts (tool calls, etc.)
                    text_parts.append(str(part))
        else:
            # Handle messages without parts
            text_parts.append(str(message))

    return "\n".join(text_parts)
