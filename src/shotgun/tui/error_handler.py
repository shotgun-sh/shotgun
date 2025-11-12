"""TUI-specific error handler implementation.

This module provides an error handler that displays errors in the TUI
using hint messages in the chat interface.
"""

from typing import TYPE_CHECKING

from shotgun.agents.error import ErrorMessage, ErrorType

if TYPE_CHECKING:
    from shotgun.tui.screens.chat.chat_screen import ChatScreen


class TUIErrorHandler:
    """Error handler for TUI interface.

    This handler implements the AgentErrorHandler protocol and displays
    errors as hint messages in the chat interface, preserving all existing
    TUI behavior including email components and markdown formatting.
    """

    def __init__(self, chat_screen: "ChatScreen"):
        """Initialize the TUI error handler.

        Args:
            chat_screen: The chat screen instance for displaying hints
        """
        self.chat_screen = chat_screen

    def handle_cancellation(self) -> None:
        """Handle operation cancellation by displaying a hint message."""
        self.chat_screen.mount_hint("⚠️ Operation cancelled by user")

    def handle_error(self, error_type: ErrorType, error_message: ErrorMessage) -> None:
        """Handle an agent execution error by displaying a hint message.

        Args:
            error_type: The classified error type
            error_message: Formatted error message with optional email component
        """
        if error_message.requires_email_component and error_message.email:
            # Use special email hint for budget exceeded errors
            self.chat_screen.mount_hint_with_email(
                markdown_before=error_message.message,
                email=error_message.email,
                markdown_after=error_message.email_context or "",
            )
        else:
            # Regular hint message
            self.chat_screen.mount_hint(error_message.message)

    def handle_success(self) -> None:
        """Handle successful agent execution.

        For TUI, this is a no-op as success is handled by the message stream.
        """
