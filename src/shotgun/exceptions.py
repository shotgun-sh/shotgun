"""General exceptions for Shotgun application."""

from shotgun.utils import get_shotgun_home

# Shotgun Account signup URL for BYOK users
SHOTGUN_SIGNUP_URL = "https://shotgun.sh"
SHOTGUN_CONTACT_EMAIL = "contact@shotgun.sh"


class ErrorNotPickedUpBySentry(Exception):  # noqa: N818
    """Base for user-actionable errors that shouldn't be sent to Sentry.

    These errors represent expected user conditions requiring action
    rather than bugs that need tracking.

    All subclasses should implement to_markdown() and to_plain_text() methods
    for consistent error message formatting.
    """

    def to_markdown(self) -> str:
        """Generate markdown-formatted error message for TUI.

        Subclasses should override this method.
        """
        return f"⚠️ {str(self)}"

    def to_plain_text(self) -> str:
        """Generate plain text error message for CLI.

        Subclasses should override this method.
        """
        return f"⚠️  {str(self)}"


# ============================================================================
# User Action Required Errors
# ============================================================================


class AgentCancelledException(ErrorNotPickedUpBySentry):
    """Raised when user cancels an agent operation."""

    def __init__(self) -> None:
        """Initialize the exception."""
        super().__init__("Operation cancelled by user")

    def to_markdown(self) -> str:
        """Generate markdown-formatted error message for TUI."""
        return "⚠️ Operation cancelled by user"

    def to_plain_text(self) -> str:
        """Generate plain text error message for CLI."""
        return "⚠️  Operation cancelled by user"


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

    def to_markdown(self) -> str:
        """Generate markdown-formatted error message for TUI."""
        return (
            f"⚠️ **Context too large for {self.model_name}**\n\n"
            f"Your conversation history exceeds this model's limit ({self.max_tokens:,} tokens).\n\n"
            f"**Choose an action:**\n\n"
            f"1. Switch to a larger model (`/` → Change Model)\n"
            f"2. Switch to a larger model, compact (`/compact`), then switch back to {self.model_name}\n"
            f"3. Clear conversation (`/clear`)\n"
        )

    def to_plain_text(self) -> str:
        """Generate plain text error message for CLI."""
        return (
            f"⚠️  Context too large for {self.model_name}\n\n"
            f"Your conversation history exceeds this model's limit ({self.max_tokens:,} tokens).\n\n"
            f"Choose an action:\n"
            f"1. Switch to a larger model\n"
            f"2. Switch to a larger model, compact, then switch back to {self.model_name}\n"
            f"3. Clear conversation\n"
        )


# ============================================================================
# Shotgun Account Errors (show contact email in TUI)
# ============================================================================


class ShotgunAccountException(ErrorNotPickedUpBySentry):
    """Base class for Shotgun Account service errors.

    TUI will check isinstance() of this class to show contact email UI.
    """


class BudgetExceededException(ShotgunAccountException):
    """Raised when Shotgun Account budget has been exceeded.

    This is a user-actionable error - they need to contact support
    to increase their budget limit. This is a temporary exception
    until self-service budget increases are implemented.
    """

    def __init__(
        self,
        current_cost: float | None = None,
        max_budget: float | None = None,
        message: str | None = None,
    ):
        """Initialize the exception.

        Args:
            current_cost: Current total spend/cost (optional)
            max_budget: Maximum budget limit (optional)
            message: Optional custom error message from API
        """
        self.current_cost = current_cost
        self.max_budget = max_budget
        self.api_message = message

        if message:
            error_msg = message
        elif current_cost is not None and max_budget is not None:
            error_msg = f"Budget exceeded: ${current_cost:.2f} / ${max_budget:.2f}"
        else:
            error_msg = "Budget exceeded"

        super().__init__(error_msg)

    def to_markdown(self) -> str:
        """Generate markdown-formatted error message for TUI.

        Note: TUI will detect ShotgunAccountException and automatically
        show email contact UI component.
        """
        return (
            "⚠️ **Your Shotgun Account budget has been exceeded!**\n\n"
            "Your account has reached its spending limit and cannot process more requests.\n\n"
            "**Action Required:** Top up your account to continue using Shotgun.\n\n"
            "👉 **[Top Up Now at https://app.shotgun.sh/dashboard](https://app.shotgun.sh/dashboard)**\n\n"
            "**Need help?** Contact us if you have questions about your budget.\n\n"
            f"_Error details: {str(self)}_"
        )

    def to_plain_text(self) -> str:
        """Generate plain text error message for CLI."""
        return (
            "⚠️  Your Shotgun Account budget has been exceeded!\n\n"
            "Your account has reached its spending limit and cannot process more requests.\n\n"
            "Action Required: Top up your account to continue using Shotgun.\n\n"
            "→ Top Up Now: https://app.shotgun.sh/dashboard\n\n"
            f"Need help? Contact: {SHOTGUN_CONTACT_EMAIL}\n\n"
            f"Error details: {str(self)}"
        )


class ShotgunServiceOverloadException(ShotgunAccountException):
    """Raised when Shotgun Account AI service is overloaded."""

    def __init__(self, message: str | None = None):
        """Initialize the exception.

        Args:
            message: Optional custom error message from API
        """
        super().__init__(message or "Service temporarily overloaded")

    def to_markdown(self) -> str:
        """Generate markdown-formatted error message for TUI."""
        return "⚠️ The AI service is temporarily overloaded. Please wait a moment and try again."

    def to_plain_text(self) -> str:
        """Generate plain text error message for CLI."""
        return "⚠️  The AI service is temporarily overloaded. Please wait a moment and try again."


class ShotgunRateLimitException(ShotgunAccountException):
    """Raised when Shotgun Account rate limit is reached."""

    def __init__(self, message: str | None = None):
        """Initialize the exception.

        Args:
            message: Optional custom error message from API
        """
        super().__init__(message or "Rate limit reached")

    def to_markdown(self) -> str:
        """Generate markdown-formatted error message for TUI."""
        return "⚠️ Rate limit reached. Please wait before trying again."

    def to_plain_text(self) -> str:
        """Generate plain text error message for CLI."""
        return "⚠️  Rate limit reached. Please wait before trying again."


# ============================================================================
# BYOK (Bring Your Own Key) API Errors
# ============================================================================


class BYOKAPIException(ErrorNotPickedUpBySentry):
    """Base class for BYOK API errors.

    All BYOK errors suggest using Shotgun Account to avoid the issue.
    """

    def __init__(self, message: str, specific_error: str = "API error"):
        """Initialize the exception.

        Args:
            message: The error message from the API
            specific_error: Human-readable error type label
        """
        self.api_message = message
        self.specific_error = specific_error
        super().__init__(message)

    def to_markdown(self) -> str:
        """Generate markdown-formatted error message for TUI."""
        return (
            f"⚠️ **{self.specific_error}**: {self.api_message}\n\n"
            f"_This could be avoided with a [Shotgun Account]({SHOTGUN_SIGNUP_URL})._"
        )

    def to_plain_text(self) -> str:
        """Generate plain text error message for CLI."""
        return (
            f"⚠️  {self.specific_error}: {self.api_message}\n\n"
            f"This could be avoided with a Shotgun Account: {SHOTGUN_SIGNUP_URL}"
        )


class BYOKRateLimitException(BYOKAPIException):
    """Raised when BYOK user hits rate limit."""

    def __init__(self, message: str):
        """Initialize the exception.

        Args:
            message: The error message from the API
        """
        super().__init__(message, specific_error="Rate limit reached")


class BYOKQuotaBillingException(BYOKAPIException):
    """Raised when BYOK user has quota or billing issues."""

    def __init__(self, message: str):
        """Initialize the exception.

        Args:
            message: The error message from the API
        """
        super().__init__(message, specific_error="Quota or billing issue")


class BYOKAuthenticationException(BYOKAPIException):
    """Raised when BYOK authentication fails."""

    def __init__(self, message: str):
        """Initialize the exception.

        Args:
            message: The error message from the API
        """
        super().__init__(message, specific_error="Authentication error")


class BYOKServiceOverloadException(BYOKAPIException):
    """Raised when BYOK service is overloaded."""

    def __init__(self, message: str):
        """Initialize the exception.

        Args:
            message: The error message from the API
        """
        super().__init__(message, specific_error="Service overloaded")


class BYOKGenericAPIException(BYOKAPIException):
    """Raised for generic BYOK API errors."""

    def __init__(self, message: str):
        """Initialize the exception.

        Args:
            message: The error message from the API
        """
        super().__init__(message, specific_error="API error")


# ============================================================================
# Generic Errors
# ============================================================================


class GenericAPIStatusException(ErrorNotPickedUpBySentry):
    """Raised for generic API status errors that don't fit other categories."""

    def __init__(self, message: str):
        """Initialize the exception.

        Args:
            message: The error message from the API
        """
        self.api_message = message
        super().__init__(message)

    def to_markdown(self) -> str:
        """Generate markdown-formatted error message for TUI."""
        return f"⚠️ AI service error: {self.api_message}"

    def to_plain_text(self) -> str:
        """Generate plain text error message for CLI."""
        return f"⚠️  AI service error: {self.api_message}"


class UnknownAgentException(ErrorNotPickedUpBySentry):
    """Raised for unknown/unclassified agent errors."""

    def __init__(self, original_exception: Exception):
        """Initialize the exception.

        Args:
            original_exception: The original exception that was caught
        """
        self.original_exception = original_exception
        super().__init__(str(original_exception))

    def to_markdown(self) -> str:
        """Generate markdown-formatted error message for TUI."""
        log_path = get_shotgun_home() / "logs" / "shotgun.log"
        return f"⚠️ An error occurred: {str(self.original_exception)}\n\nCheck logs at {log_path}"

    def to_plain_text(self) -> str:
        """Generate plain text error message for CLI."""
        log_path = get_shotgun_home() / "logs" / "shotgun.log"
        return f"⚠️  An error occurred: {str(self.original_exception)}\n\nCheck logs at {log_path}"
