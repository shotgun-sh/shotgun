"""Context window validation utilities for model switching."""

from pydantic_ai.messages import ModelMessage

from shotgun.agents.config.models import ModelConfig

from .constants import TOKEN_LIMIT_RATIO
from .token_estimation import estimate_tokens_from_messages


class ContextValidationResult:
    """Result of context window validation."""

    def __init__(self, is_valid: bool, current_tokens: int, max_tokens: int):
        """Initialize validation result.

        Args:
            is_valid: Whether the conversation fits within the model's context
            current_tokens: Current token count of the conversation
            max_tokens: Maximum allowed tokens (after applying TOKEN_LIMIT_RATIO)
        """
        self.is_valid = is_valid
        self.current_tokens = current_tokens
        self.max_tokens = max_tokens

    @property
    def current_tokens_k(self) -> int:
        """Get current tokens in thousands (K)."""
        return self.current_tokens // 1000

    @property
    def max_tokens_k(self) -> int:
        """Get max tokens in thousands (K)."""
        return self.max_tokens // 1000

    @property
    def overflow_tokens(self) -> int:
        """Get number of tokens over the limit (0 if valid)."""
        return max(0, self.current_tokens - self.max_tokens)


async def validate_context_for_model(
    messages: list[ModelMessage], model_config: ModelConfig
) -> ContextValidationResult:
    """Validate that conversation fits within model's context window.

    This checks if the current conversation size exceeds the target model's
    maximum input token limit (using 80% threshold via TOKEN_LIMIT_RATIO).

    Args:
        messages: Current conversation messages to validate
        model_config: Target model configuration to validate against

    Returns:
        ContextValidationResult with validation status and token counts

    Raises:
        ValueError: If provider is not supported for token counting
        RuntimeError: If token counting fails
    """
    # Calculate current conversation size
    current_tokens = await estimate_tokens_from_messages(messages, model_config)

    # Calculate max allowed tokens (80% of model's input limit)
    model_max_tokens = model_config.max_input_tokens
    max_allowed_tokens = int(model_max_tokens * TOKEN_LIMIT_RATIO)

    # Check if conversation fits
    is_valid = current_tokens < max_allowed_tokens

    return ContextValidationResult(
        is_valid=is_valid,
        current_tokens=current_tokens,
        max_tokens=max_allowed_tokens,
    )
