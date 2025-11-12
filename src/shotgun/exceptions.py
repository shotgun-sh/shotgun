"""General exceptions for Shotgun application."""


class ErrorNotPickedUpBySentry(Exception):  # noqa: N818
    """Base for user-actionable errors that shouldn't be sent to Sentry.

    These errors represent expected user conditions requiring action
    rather than bugs that need tracking.
    """


class ContextSizeLimitExceeded(ErrorNotPickedUpBySentry):
    """Raised when conversation context exceeds the model's limits.

    This is a user-actionable error - they need to either:
    1. Switch to a larger context model
    2. Switch to a larger model, compact their conversation, then switch back
    3. Clear the conversation and start fresh
    """

    def __init__(self, model_name: str, max_tokens: int):
        """Initialize the exception.

        Args:
            model_name: Name of the model whose limit was exceeded
            max_tokens: Maximum tokens allowed by the model
        """
        self.model_name = model_name
        self.max_tokens = max_tokens
        super().__init__(
            f"Context too large for {model_name} (limit: {max_tokens:,} tokens)"
        )


class BudgetExceededException(ErrorNotPickedUpBySentry):
    """Raised when Shotgun Account budget has been exceeded.

    This is a user-actionable error - they need to contact support
    to increase their budget limit. This is a temporary exception
    until self-service budget increases are implemented.
    """

    def __init__(self, current_cost: float, max_budget: float, message: str | None = None):
        """Initialize the exception.

        Args:
            current_cost: Current total spend/cost
            max_budget: Maximum budget limit
            message: Optional custom error message from API
        """
        self.current_cost = current_cost
        self.max_budget = max_budget
        self.api_message = message

        error_msg = (
            message
            if message
            else f"Budget exceeded: ${current_cost:.2f} / ${max_budget:.2f}"
        )
        super().__init__(error_msg)
