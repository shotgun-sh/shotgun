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
