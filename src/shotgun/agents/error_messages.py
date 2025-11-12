"""User-friendly error message generation for agent failures.

This module provides utilities to generate clear, actionable error messages
for different types of agent execution failures.
"""

from dataclasses import dataclass

from shotgun.agents.error_classifier import AgentErrorContext, ErrorType
from shotgun.utils import get_shotgun_home

# Shotgun Account signup URL for BYOK users
SHOTGUN_SIGNUP_URL = "https://shotgun.sh"


@dataclass
class ErrorMessage:
    """Container for error message components.

    Attributes:
        message: The main error message (markdown or plain text)
        requires_email_component: Whether this error needs an email contact component
        email: Optional email address for contact (if requires_email_component is True)
        email_context: Additional context to show after email component
    """

    message: str
    requires_email_component: bool = False
    email: str | None = None
    email_context: str | None = None


class ErrorMessageGenerator:
    """Generator for user-friendly error messages.

    This class creates clear, actionable error messages for different error types,
    with support for both markdown (TUI) and plain text (CLI) formatting.
    """

    @staticmethod
    def generate(
        error_type: ErrorType,
        context: AgentErrorContext,
        use_markdown: bool = True,
    ) -> ErrorMessage:
        """Generate a user-friendly error message.

        Args:
            error_type: The classified error type
            context: Context information about the error
            use_markdown: Whether to use markdown formatting (TUI) or plain text (CLI)

        Returns:
            ErrorMessage with appropriate formatting and content
        """
        if error_type == ErrorType.CANCELLED:
            return ErrorMessageGenerator._cancelled_message(use_markdown)
        elif error_type == ErrorType.CONTEXT_SIZE_EXCEEDED:
            return ErrorMessageGenerator._context_size_exceeded_message(
                context, use_markdown
            )
        elif error_type == ErrorType.BUDGET_EXCEEDED:
            return ErrorMessageGenerator._budget_exceeded_message(context, use_markdown)
        elif error_type in [
            ErrorType.BYOK_RATE_LIMIT,
            ErrorType.BYOK_QUOTA_BILLING,
            ErrorType.BYOK_AUTHENTICATION,
            ErrorType.BYOK_SERVICE_OVERLOAD,
            ErrorType.BYOK_GENERIC_API,
        ]:
            return ErrorMessageGenerator._byok_api_error_message(
                error_type, context, use_markdown
            )
        elif error_type == ErrorType.SHOTGUN_SERVICE_OVERLOAD:
            return ErrorMessageGenerator._shotgun_service_overload_message(use_markdown)
        elif error_type == ErrorType.SHOTGUN_RATE_LIMIT:
            return ErrorMessageGenerator._shotgun_rate_limit_message(use_markdown)
        elif error_type == ErrorType.GENERIC_API_STATUS:
            return ErrorMessageGenerator._generic_api_status_message(
                context, use_markdown
            )
        else:  # ErrorType.UNKNOWN
            return ErrorMessageGenerator._unknown_error_message(context, use_markdown)

    @staticmethod
    def _cancelled_message(use_markdown: bool) -> ErrorMessage:
        """Generate message for cancelled operations."""
        if use_markdown:
            message = "⚠️ Operation cancelled by user"
        else:
            message = "⚠️  Operation cancelled by user"
        return ErrorMessage(message=message)

    @staticmethod
    def _context_size_exceeded_message(
        context: AgentErrorContext, use_markdown: bool
    ) -> ErrorMessage:
        """Generate message for context size limit exceeded."""
        from shotgun.exceptions import ContextSizeLimitExceeded

        exc = context.exception
        if not isinstance(exc, ContextSizeLimitExceeded):
            # Fallback if wrong exception type
            return ErrorMessage(message="⚠️ Context size limit exceeded")

        if use_markdown:
            message = (
                f"⚠️ **Context too large for {exc.model_name}**\n\n"
                f"Your conversation history exceeds this model's limit ({exc.max_tokens:,} tokens).\n\n"
                f"**Choose an action:**\n\n"
                f"1. Switch to a larger model (`Ctrl+P` → Change Model)\n"
                f"2. Switch to a larger model, compact (`/compact`), then switch back to {exc.model_name}\n"
                f"3. Clear conversation (`/clear`)\n"
            )
        else:
            message = (
                f"⚠️  Context too large for {exc.model_name}\n\n"
                f"Your conversation history exceeds this model's limit ({exc.max_tokens:,} tokens).\n\n"
                f"Choose an action:\n"
                f"1. Switch to a larger model\n"
                f"2. Switch to a larger model, compact, then switch back to {exc.model_name}\n"
                f"3. Clear conversation\n"
            )

        return ErrorMessage(message=message)

    @staticmethod
    def _budget_exceeded_message(
        context: AgentErrorContext, use_markdown: bool
    ) -> ErrorMessage:
        """Generate message for budget exceeded error (Shotgun Account)."""
        error_message = str(context.exception)

        if use_markdown:
            markdown_before = (
                "⚠️ **Your Shotgun Account budget has been exceeded!**\n\n"
                "Your account has reached its spending limit and cannot process more requests.\n\n"
                "**Need help?**"
            )

            markdown_after = (
                "\n\n• Self-service budget increases are coming soon!\n\n"
                f"_Error details: {error_message}_"
            )

            return ErrorMessage(
                message=markdown_before,
                requires_email_component=True,
                email="contact@shotgun.sh",
                email_context=markdown_after,
            )
        else:
            message = (
                "⚠️  Your Shotgun Account budget has been exceeded!\n\n"
                "Your account has reached its spending limit and cannot process more requests.\n\n"
                "Need help? Contact: contact@shotgun.sh\n\n"
                "• Self-service budget increases are coming soon!\n\n"
                f"Error details: {error_message}"
            )
            return ErrorMessage(message=message)

    @staticmethod
    def _byok_api_error_message(
        error_type: ErrorType, context: AgentErrorContext, use_markdown: bool
    ) -> ErrorMessage:
        """Generate message for BYOK API errors with suggestion to use Shotgun Account."""
        error_message = str(context.exception)

        # Determine specific error label
        if error_type == ErrorType.BYOK_RATE_LIMIT:
            specific_error = "Rate limit reached"
        elif error_type == ErrorType.BYOK_QUOTA_BILLING:
            specific_error = "Quota or billing issue"
        elif error_type == ErrorType.BYOK_AUTHENTICATION:
            specific_error = "Authentication error"
        elif error_type == ErrorType.BYOK_SERVICE_OVERLOAD:
            specific_error = "Service overloaded"
        else:
            specific_error = "API error"

        if use_markdown:
            message = (
                f"⚠️ **{specific_error}**: {error_message}\n\n"
                f"_This could be avoided with a [Shotgun Account]({SHOTGUN_SIGNUP_URL})._"
            )
        else:
            message = (
                f"⚠️  {specific_error}: {error_message}\n\n"
                f"This could be avoided with a Shotgun Account: {SHOTGUN_SIGNUP_URL}"
            )

        return ErrorMessage(message=message)

    @staticmethod
    def _shotgun_service_overload_message(use_markdown: bool) -> ErrorMessage:
        """Generate message for Shotgun Account service overload."""
        if use_markdown:
            message = "⚠️ The AI service is temporarily overloaded. Please wait a moment and try again."
        else:
            message = "⚠️  The AI service is temporarily overloaded. Please wait a moment and try again."
        return ErrorMessage(message=message)

    @staticmethod
    def _shotgun_rate_limit_message(use_markdown: bool) -> ErrorMessage:
        """Generate message for Shotgun Account rate limit."""
        if use_markdown:
            message = "⚠️ Rate limit reached. Please wait before trying again."
        else:
            message = "⚠️  Rate limit reached. Please wait before trying again."
        return ErrorMessage(message=message)

    @staticmethod
    def _generic_api_status_message(
        context: AgentErrorContext, use_markdown: bool
    ) -> ErrorMessage:
        """Generate message for generic API status errors."""
        error_message = str(context.exception)

        if use_markdown:
            message = f"⚠️ AI service error: {error_message}"
        else:
            message = f"⚠️  AI service error: {error_message}"

        return ErrorMessage(message=message)

    @staticmethod
    def _unknown_error_message(
        context: AgentErrorContext, use_markdown: bool
    ) -> ErrorMessage:
        """Generate message for unknown errors."""
        error_message = str(context.exception)
        log_path = get_shotgun_home() / "logs" / "shotgun.log"

        if use_markdown:
            message = (
                f"⚠️ An error occurred: {error_message}\n\nCheck logs at {log_path}"
            )
        else:
            message = (
                f"⚠️  An error occurred: {error_message}\n\nCheck logs at {log_path}"
            )

        return ErrorMessage(message=message)
