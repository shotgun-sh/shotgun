"""Utilities for extracting token counts from ModelResponse.usage data."""

from pydantic import BaseModel, Field
from pydantic_ai.messages import ModelMessage, ModelResponse


class UsageTokens(BaseModel):
    """Token counts extracted from ModelResponse.usage data.

    This model provides ground truth token counts from actual API usage data,
    which is more accurate than token estimation. The input_tokens field is
    cumulative (from the last response), while output_tokens is the sum of
    all responses in the conversation.
    """

    input_tokens: int = Field(
        ge=0, description="Cumulative input tokens from last response"
    )
    output_tokens: int = Field(ge=0, description="Sum of all output tokens")
    has_usage_data: bool = Field(
        description="Whether any usage data was found in message history"
    )

    @property
    def total_tokens(self) -> int:
        """Total conversation size for next API call.

        This represents the full context window usage: the input tokens from
        the last response plus all output tokens that will become input in
        the next call.

        Returns:
            Sum of input_tokens and output_tokens
        """
        return self.input_tokens + self.output_tokens


def extract_usage_tokens(messages: list[ModelMessage]) -> UsageTokens:
    """Extract token counts from ModelResponse.usage data.

    This function provides the ground truth token counts by reading actual
    usage data from the API responses. It implements the pattern used
    throughout the codebase for calculating conversation size.

    The algorithm:
    1. Find the LAST ModelResponse with usage data and extract its input_tokens
       (which is cumulative and includes the entire conversation history)
    2. Sum output_tokens across ALL ModelResponse objects
    3. Add cache_read_tokens to input (for prompt caching, currently 0)

    For validation or when usage data is missing, check the has_usage_data
    field and fall back to token estimation if needed.

    Args:
        messages: List of conversation messages (ModelRequest and ModelResponse)

    Returns:
        UsageTokens with extracted counts and has_usage_data flag

    Example:
        >>> usage = extract_usage_tokens(message_history)
        >>> if usage.has_usage_data:
        ...     total = usage.total_tokens
        ... else:
        ...     # Fall back to estimation
        ...     total = await estimate_tokens_from_messages(...)
    """
    # Step 1: Get last response's input tokens (cumulative)
    last_input_tokens = 0
    for msg in reversed(messages):
        if isinstance(msg, ModelResponse) and msg.usage:
            # Note: cache_read_tokens will be 0 until prompt caching is enabled
            last_input_tokens = msg.usage.input_tokens + msg.usage.cache_read_tokens
            break

    # Step 2: Sum all output tokens across all responses
    total_output_tokens = 0
    for msg in messages:
        if isinstance(msg, ModelResponse) and msg.usage:
            total_output_tokens += msg.usage.output_tokens

    # Check if we found any usage data
    has_data = last_input_tokens > 0 or total_output_tokens > 0

    return UsageTokens(
        input_tokens=last_input_tokens,
        output_tokens=total_output_tokens,
        has_usage_data=has_data,
    )
