"""Real token counting for all supported providers.

This module provides accurate token counting using each provider's official
APIs and libraries, eliminating the need for rough character-based estimation.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from pydantic_ai.messages import ModelMessage

from shotgun.agents.config.models import ModelConfig, ProviderType
from shotgun.logging_config import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

# Global cache for token counter instances (singleton pattern)
_token_counter_cache: dict[tuple[str, str, str], "TokenCounter"] = {}


class TokenCounter(ABC):
    """Abstract base class for provider-specific token counting."""

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Count tokens in text using provider-specific method.

        Args:
            text: Text to count tokens for

        Returns:
            Exact token count as determined by the provider

        Raises:
            RuntimeError: If token counting fails
        """

    @abstractmethod
    def count_message_tokens(self, messages: list[ModelMessage]) -> int:
        """Count tokens in PydanticAI message structures.

        Args:
            messages: List of messages to count tokens for

        Returns:
            Total token count across all messages

        Raises:
            RuntimeError: If token counting fails
        """


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

    def count_tokens(self, text: str) -> int:
        """Count tokens using tiktoken.

        Args:
            text: Text to count tokens for

        Returns:
            Exact token count using tiktoken

        Raises:
            RuntimeError: If token counting fails
        """
        try:
            return len(self.encoding.encode(text))
        except Exception as e:
            raise RuntimeError(
                f"Failed to count tokens for OpenAI model {self.model_name}"
            ) from e

    def count_message_tokens(self, messages: list[ModelMessage]) -> int:
        """Count tokens across all messages using tiktoken.

        Args:
            messages: List of PydanticAI messages

        Returns:
            Total token count for all messages

        Raises:
            RuntimeError: If token counting fails
        """
        total_text = self._extract_text_from_messages(messages)
        return self.count_tokens(total_text)

    def _extract_text_from_messages(self, messages: list[ModelMessage]) -> str:
        """Extract all text content from messages for token counting."""
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


class AnthropicTokenCounter(TokenCounter):
    """Token counter for Anthropic models using official client."""

    def __init__(self, model_name: str, api_key: str):
        """Initialize Anthropic token counter.

        Args:
            model_name: Anthropic model name for token counting
            api_key: Anthropic API key

        Raises:
            RuntimeError: If client initialization fails
        """
        self.model_name = model_name
        import anthropic

        try:
            self.client = anthropic.Anthropic(api_key=api_key)
            logger.debug(f"Initialized Anthropic token counter for {model_name}")
        except Exception as e:
            raise RuntimeError("Failed to initialize Anthropic client") from e

    def count_tokens(self, text: str) -> int:
        """Count tokens using Anthropic's official API.

        Args:
            text: Text to count tokens for

        Returns:
            Exact token count from Anthropic API

        Raises:
            RuntimeError: If API call fails
        """
        try:
            # Anthropic API expects messages format and model parameter
            result = self.client.messages.count_tokens(
                messages=[{"role": "user", "content": text}], model=self.model_name
            )
            return result.input_tokens
        except Exception as e:
            raise RuntimeError(
                f"Anthropic token counting API failed for {self.model_name}"
            ) from e

    def count_message_tokens(self, messages: list[ModelMessage]) -> int:
        """Count tokens across all messages using Anthropic API.

        Args:
            messages: List of PydanticAI messages

        Returns:
            Total token count for all messages

        Raises:
            RuntimeError: If token counting fails
        """
        total_text = self._extract_text_from_messages(messages)
        return self.count_tokens(total_text)

    def _extract_text_from_messages(self, messages: list[ModelMessage]) -> str:
        """Extract all text content from messages for token counting."""
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


class GoogleTokenCounter(TokenCounter):
    """Token counter for Google models using genai API."""

    def __init__(self, model_name: str, api_key: str):
        """Initialize Google token counter.

        Args:
            model_name: Google model name
            api_key: Google API key

        Raises:
            RuntimeError: If configuration fails
        """
        self.model_name = model_name

        import google.generativeai as genai

        try:
            genai.configure(api_key=api_key)  # type: ignore[attr-defined]
            self.model = genai.GenerativeModel(model_name)  # type: ignore[attr-defined]
            logger.debug(f"Initialized Google token counter for {model_name}")
        except Exception as e:
            raise RuntimeError(
                f"Failed to configure Google genai client for {model_name}"
            ) from e

    def count_tokens(self, text: str) -> int:
        """Count tokens using Google's genai API.

        Args:
            text: Text to count tokens for

        Returns:
            Exact token count from Google API

        Raises:
            RuntimeError: If API call fails
        """
        try:
            result = self.model.count_tokens(text)
            return result.total_tokens
        except Exception as e:
            raise RuntimeError(
                f"Google token counting API failed for {self.model_name}"
            ) from e

    def count_message_tokens(self, messages: list[ModelMessage]) -> int:
        """Count tokens across all messages using Google API.

        Args:
            messages: List of PydanticAI messages

        Returns:
            Total token count for all messages

        Raises:
            RuntimeError: If token counting fails
        """
        total_text = self._extract_text_from_messages(messages)
        return self.count_tokens(total_text)

    def _extract_text_from_messages(self, messages: list[ModelMessage]) -> str:
        """Extract all text content from messages for token counting."""
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


def get_token_counter(model_config: ModelConfig) -> TokenCounter:
    """Get appropriate token counter for the model provider (cached singleton).

    This function ensures that every provider has a proper token counting
    implementation without any fallbacks to estimation. Token counters are
    cached to avoid repeated initialization overhead.

    Args:
        model_config: Model configuration with provider and credentials

    Returns:
        Cached provider-specific token counter

    Raises:
        ValueError: If provider is not supported for token counting
        RuntimeError: If token counter initialization fails
    """
    # Create cache key from provider, model name, and API key
    cache_key = (
        model_config.provider.value,
        model_config.name,
        model_config.api_key[:10]
        if model_config.api_key
        else "no-key",  # Partial key for cache
    )

    # Return cached instance if available
    if cache_key in _token_counter_cache:
        logger.debug(
            f"Reusing cached token counter for {model_config.provider.value}:{model_config.name}"
        )
        return _token_counter_cache[cache_key]

    # Create new instance and cache it
    logger.debug(
        f"Creating new token counter for {model_config.provider.value}:{model_config.name}"
    )

    counter: TokenCounter
    if model_config.provider == ProviderType.OPENAI:
        counter = OpenAITokenCounter(model_config.name)
    elif model_config.provider == ProviderType.ANTHROPIC:
        counter = AnthropicTokenCounter(model_config.name, model_config.api_key)
    elif model_config.provider == ProviderType.GOOGLE:
        counter = GoogleTokenCounter(model_config.name, model_config.api_key)
    else:
        raise ValueError(
            f"Unsupported provider for token counting: {model_config.provider}. "
            f"Supported providers: {[p.value for p in ProviderType]}"
        )

    # Cache the instance
    _token_counter_cache[cache_key] = counter
    logger.debug(
        f"Cached token counter for {model_config.provider.value}:{model_config.name}"
    )

    return counter


def count_tokens_from_messages(
    messages: list[ModelMessage], model_config: ModelConfig
) -> int:
    """Count actual tokens from messages using provider-specific methods.

    This replaces the old estimation approach with accurate token counting
    using each provider's official APIs and libraries.

    Args:
        messages: List of messages to count tokens for
        model_config: Model configuration with provider info

    Returns:
        Exact token count for the messages

    Raises:
        ValueError: If provider is not supported
        RuntimeError: If token counting fails
    """
    counter = get_token_counter(model_config)
    return counter.count_message_tokens(messages)


def count_post_summary_tokens(
    messages: list[ModelMessage], summary_index: int, model_config: ModelConfig
) -> int:
    """Count actual tokens from summary onwards for incremental compaction decisions.

    Args:
        messages: Full message history
        summary_index: Index of the last summary message
        model_config: Model configuration with provider info

    Returns:
        Exact token count from summary onwards

    Raises:
        ValueError: If provider is not supported
        RuntimeError: If token counting fails
    """
    if summary_index >= len(messages):
        return 0

    post_summary_messages = messages[summary_index:]
    return count_tokens_from_messages(post_summary_messages, model_config)


def count_tokens_from_message_parts(
    messages: list[ModelMessage], model_config: ModelConfig
) -> int:
    """Count actual tokens from message parts for summarization requests.

    Args:
        messages: List of messages to count tokens for
        model_config: Model configuration with provider info

    Returns:
        Exact token count from message parts

    Raises:
        ValueError: If provider is not supported
        RuntimeError: If token counting fails
    """
    # For now, use the same logic as count_tokens_from_messages
    # This can be optimized later if needed for different counting strategies
    return count_tokens_from_messages(messages, model_config)
