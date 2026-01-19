"""Base classes and shared utilities for token counting."""

from abc import ABC, abstractmethod

from pydantic_ai.messages import BinaryContent, ModelMessage


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


def _extract_text_from_content(content: object) -> str | None:
    """Extract text from a content object, skipping BinaryContent.

    Args:
        content: A content object (str, BinaryContent, list, etc.)

    Returns:
        Extracted text or None if content is binary/empty
    """
    if isinstance(content, BinaryContent):
        return None
    if isinstance(content, str):
        return content.strip() if content.strip() else None
    if isinstance(content, list):
        # Content can be a list like ['text', BinaryContent(...), 'more text']
        text_items = []
        for item in content:
            extracted = _extract_text_from_content(item)
            if extracted:
                text_items.append(extracted)
        return "\n".join(text_items) if text_items else None
    # For other types, convert to string but skip if it looks like binary
    text = str(content)
    # Skip if it's a BinaryContent repr (contains raw bytes)
    if "BinaryContent(data=b" in text:
        return None
    return text.strip() if text.strip() else None


def extract_text_from_messages(messages: list[ModelMessage]) -> str:
    """Extract all text content from messages for token counting.

    Note: BinaryContent (PDFs, images) is skipped because:
    1. str(BinaryContent) includes raw bytes which tokenize terribly
    2. Claude uses fixed token costs for images/PDFs based on dimensions/pages,
       not raw data size
    3. Including binary data in text token counting causes massive overestimates
       (e.g., 127KB of PDFs -> 267K tokens instead of ~few thousand)

    Args:
        messages: List of PydanticAI messages

    Returns:
        Combined text content from all messages (excluding binary content)
    """
    text_parts = []

    for message in messages:
        if hasattr(message, "parts"):
            for part in message.parts:
                # Skip BinaryContent directly
                if isinstance(part, BinaryContent):
                    continue

                # Check if part has content attribute (UserPromptPart, etc.)
                if hasattr(part, "content"):
                    extracted = _extract_text_from_content(part.content)
                    if extracted:
                        text_parts.append(extracted)
                else:
                    # Handle other parts (tool calls, etc.) - but check for binary
                    part_str = str(part)
                    # Skip if it contains BinaryContent repr
                    if "BinaryContent(data=b" not in part_str and part_str.strip():
                        text_parts.append(part_str)
        else:
            # Handle messages without parts
            msg_str = str(message)
            if "BinaryContent(data=b" not in msg_str and msg_str.strip():
                text_parts.append(msg_str)

    # If no valid text parts found, return a minimal placeholder
    # This ensures we never send completely empty content to APIs
    if not text_parts:
        return "."

    return "\n".join(text_parts)
