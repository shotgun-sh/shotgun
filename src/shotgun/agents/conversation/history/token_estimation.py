"""Real token counting utilities for history processing.

This module provides accurate token counting using provider-specific APIs
and libraries, replacing the old character-based estimation approach.
"""

from typing import TYPE_CHECKING, Union

from pydantic_ai.messages import ModelMessage, ModelResponse

from shotgun.agents.config.models import ModelConfig

if TYPE_CHECKING:
    from pydantic_ai import RunContext

    from shotgun.agents.models import AgentDeps

from shotgun.logging_config import get_logger

from .constants import INPUT_BUFFER_TOKENS, MIN_SUMMARY_TOKENS
from .token_counting import count_tokens_from_messages as _count_tokens_from_messages

logger = get_logger(__name__)


def get_last_api_token_count(messages: list[ModelMessage]) -> int:
    """Extract the total input token count from the last ModelResponse's usage data.

    API usage data is the most accurate source for token counts because it includes
    message framing, tool schemas, system prompts, and binary content that text-based
    estimation misses.

    Returns 0 if no ModelResponse with nonzero usage data is found.
    """
    for msg in reversed(messages):
        if isinstance(msg, ModelResponse) and msg.usage:
            return msg.usage.input_tokens + msg.usage.cache_read_tokens
    return 0


async def estimate_tokens_from_messages(
    messages: list[ModelMessage], model_config: ModelConfig
) -> int:
    """Count actual tokens from current message list (async).

    This provides accurate token counting for compaction decisions using
    provider-specific token counting methods instead of rough estimation.

    Args:
        messages: List of messages to count tokens for
        model_config: Model configuration with provider info

    Returns:
        Exact token count using provider-specific counting

    Raises:
        ValueError: If provider is not supported
        RuntimeError: If token counting fails
    """
    return await _count_tokens_from_messages(messages, model_config)


async def estimate_tokens_hybrid(
    messages: list[ModelMessage], model_config: ModelConfig
) -> int:
    """Estimate total tokens using API usage data plus delta counting.

    This is more efficient than counting all messages from scratch. It uses the
    last ModelResponse's usage data (which includes framing, schemas, etc.) as
    the base count, then only counts the new messages added since that response.

    Falls back to full counting when no API usage data is available (e.g. first turn).

    Args:
        messages: List of messages to count tokens for
        model_config: Model configuration with provider info

    Returns:
        Estimated token count
    """
    api_count = get_last_api_token_count(messages)

    if api_count == 0:
        # First turn or no usage data — fall back to full counting
        return await estimate_tokens_from_messages(messages, model_config)

    # Find messages after the last ModelResponse (the delta)
    last_response_idx = None
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], ModelResponse):
            last_response_idx = i
            break

    delta_messages = (
        messages[last_response_idx + 1 :] if last_response_idx is not None else []
    )

    if not delta_messages:
        return api_count

    delta_count = await estimate_tokens_from_messages(delta_messages, model_config)

    logger.debug(
        f"Hybrid token estimate: api_count={api_count}, delta_count={delta_count}, "
        f"delta_messages={len(delta_messages)}, total={api_count + delta_count}"
    )

    return api_count + delta_count


async def estimate_post_summary_tokens(
    messages: list[ModelMessage], summary_index: int, model_config: ModelConfig
) -> int:
    """Count actual tokens from summary onwards for incremental compaction decisions (async).

    This treats the summary as a reset point and only counts tokens from the summary
    message onwards. Used to determine if incremental compaction is needed.

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
    return await estimate_tokens_from_messages(post_summary_messages, model_config)


async def estimate_tokens_from_message_parts(
    messages: list[ModelMessage], model_config: ModelConfig
) -> int:
    """Count actual tokens from message parts for summarization requests (async).

    This provides accurate token counting across the codebase using
    provider-specific methods instead of character estimation.

    Args:
        messages: List of messages to count tokens for
        model_config: Model configuration with provider info

    Returns:
        Exact token count from message parts

    Raises:
        ValueError: If provider is not supported
        RuntimeError: If token counting fails
    """
    return await _count_tokens_from_messages(messages, model_config)


async def calculate_max_summarization_tokens(
    ctx_or_model_config: Union["RunContext[AgentDeps]", ModelConfig],
    request_messages: list[ModelMessage],
) -> int:
    """Calculate maximum tokens available for summarization output (async).

    This ensures we use the model's full capacity while leaving room for input tokens.

    Args:
        ctx_or_model_config: RunContext or model configuration with token limits
        request_messages: The messages that will be sent for summarization

    Returns:
        Maximum tokens available for the summarization response
    """
    # Support both RunContext and direct model config
    if hasattr(ctx_or_model_config, "deps"):
        model_config = ctx_or_model_config.deps.llm_model
    else:
        model_config = ctx_or_model_config

    if not model_config:
        return MIN_SUMMARY_TOKENS

    # Count actual input tokens using shared utility
    estimated_input_tokens = await estimate_tokens_from_message_parts(
        request_messages, model_config
    )

    # Add buffer for prompt overhead, system instructions, etc.
    total_estimated_input = estimated_input_tokens + INPUT_BUFFER_TOKENS

    # For models with combined token limits (like GPT), use total limit
    # For models with separate limits (like Claude), use output limit directly
    if hasattr(model_config, "max_total_tokens"):
        # Combined limit model
        available_for_output = (
            int(model_config.max_total_tokens) - total_estimated_input
        )
        max_output = min(available_for_output, int(model_config.max_output_tokens))
    else:
        # Separate limits model - just use max_output_tokens
        max_output = int(model_config.max_output_tokens)

    # Ensure we don't go below a minimum useful amount
    return max(MIN_SUMMARY_TOKENS, max_output)
