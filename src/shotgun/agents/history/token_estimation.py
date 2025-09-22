"""Real token counting utilities for history processing.

This module provides accurate token counting using provider-specific APIs
and libraries, replacing the old character-based estimation approach.
"""

from typing import TYPE_CHECKING, Union

from pydantic_ai.messages import ModelMessage

from shotgun.agents.config.models import ModelConfig

if TYPE_CHECKING:
    from pydantic_ai import RunContext

    from shotgun.agents.models import AgentDeps

from .constants import INPUT_BUFFER_TOKENS, MIN_SUMMARY_TOKENS
from .token_counting import count_tokens_from_messages as _count_tokens_from_messages


def estimate_tokens_from_messages(
    messages: list[ModelMessage], model_config: ModelConfig
) -> int:
    """Count actual tokens from current message list.

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
    return _count_tokens_from_messages(messages, model_config)


def estimate_post_summary_tokens(
    messages: list[ModelMessage], summary_index: int, model_config: ModelConfig
) -> int:
    """Count actual tokens from summary onwards for incremental compaction decisions.

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
    return estimate_tokens_from_messages(post_summary_messages, model_config)


def estimate_tokens_from_message_parts(
    messages: list[ModelMessage], model_config: ModelConfig
) -> int:
    """Count actual tokens from message parts for summarization requests.

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
    return _count_tokens_from_messages(messages, model_config)


def calculate_max_summarization_tokens(
    ctx_or_model_config: Union["RunContext[AgentDeps]", ModelConfig],
    request_messages: list[ModelMessage],
) -> int:
    """Calculate maximum tokens available for summarization output.

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
    estimated_input_tokens = estimate_tokens_from_message_parts(
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
