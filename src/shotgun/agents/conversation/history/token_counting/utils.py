"""Utility functions and cache for token counting."""

from pydantic_ai.messages import ModelMessage

from shotgun.agents.config.models import ModelConfig, ProviderType
from shotgun.logging_config import get_logger

from .anthropic import AnthropicTokenCounter
from .base import TokenCounter
from .openai import OpenAITokenCounter
from .sentencepiece_counter import SentencePieceTokenCounter

logger = get_logger(__name__)

# Global cache for token counter instances (singleton pattern)
_token_counter_cache: dict[tuple[str, str, str], TokenCounter] = {}


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
        return _token_counter_cache[cache_key]

    # Create new instance and cache it
    logger.debug(
        f"Creating new token counter for {model_config.provider.value}:{model_config.name}"
    )

    counter: TokenCounter
    if model_config.provider == ProviderType.OPENAI:
        counter = OpenAITokenCounter(model_config.name)
    elif model_config.provider == ProviderType.ANTHROPIC:
        counter = AnthropicTokenCounter(
            model_config.name, model_config.api_key, model_config.key_provider
        )
    elif model_config.provider == ProviderType.GOOGLE:
        # Use local SentencePiece tokenizer (100% accurate, 10-100x faster than API)
        counter = SentencePieceTokenCounter(model_config.name)
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


async def count_tokens_from_messages(
    messages: list[ModelMessage], model_config: ModelConfig
) -> int:
    """Count actual tokens from messages using provider-specific methods (async).

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
    return await counter.count_message_tokens(messages)


async def count_post_summary_tokens(
    messages: list[ModelMessage], summary_index: int, model_config: ModelConfig
) -> int:
    """Count actual tokens from summary onwards for incremental compaction decisions (async).

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
    return await count_tokens_from_messages(post_summary_messages, model_config)


async def count_tokens_from_message_parts(
    messages: list[ModelMessage], model_config: ModelConfig
) -> int:
    """Count actual tokens from message parts for summarization requests (async).

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
    return await count_tokens_from_messages(messages, model_config)
