"""OpenAI token counting using tiktoken."""

from pydantic_ai.messages import ModelMessage

from shotgun.logging_config import get_logger

from .base import TokenCounter, extract_text_from_messages

logger = get_logger(__name__)


class OpenAITokenCounter(TokenCounter):
    """Token counter for OpenAI models using tiktoken."""

    # Official encoding mappings for OpenAI models
    ENCODING_MAP = {
        "gpt-5": "o200k_base",
        "gpt-4o": "o200k_base",
        "gpt-4": "cl100k_base",
        "gpt-3.5-turbo": "cl100k_base",
    }

    def __init__(self, model_name: str):
        """Initialize OpenAI token counter.

        Args:
            model_name: OpenAI model name to get correct encoding for

        Raises:
            RuntimeError: If encoding initialization fails
        """
        self.model_name = model_name

        import tiktoken

        try:
            # Get the appropriate encoding for this model
            encoding_name = self.ENCODING_MAP.get(model_name, "o200k_base")
            self.encoding = tiktoken.get_encoding(encoding_name)
            logger.debug(
                f"Initialized OpenAI token counter with {encoding_name} encoding"
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to initialize tiktoken encoding for {model_name}"
            ) from e

    async def count_tokens(self, text: str) -> int:
        """Count tokens using tiktoken (async).

        Args:
            text: Text to count tokens for

        Returns:
            Exact token count using tiktoken

        Raises:
            RuntimeError: If token counting fails
        """
        # Handle empty text to avoid unnecessary encoding
        if not text or not text.strip():
            return 0

        try:
            return len(self.encoding.encode(text))
        except Exception as e:
            raise RuntimeError(
                f"Failed to count tokens for OpenAI model {self.model_name}"
            ) from e

    async def count_message_tokens(self, messages: list[ModelMessage]) -> int:
        """Count tokens across all messages using tiktoken (async).

        Args:
            messages: List of PydanticAI messages

        Returns:
            Total token count for all messages

        Raises:
            RuntimeError: If token counting fails
        """
        # Handle empty message list early
        if not messages:
            return 0

        total_text = extract_text_from_messages(messages)
        return await self.count_tokens(total_text)
