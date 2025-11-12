"""Protocol definitions for agent execution error handling.

This module defines protocols that allow different interfaces (TUI, CLI) to
implement their own error handling strategies while sharing common execution logic.

Following the Protocol-based Dependency Inversion pattern from CLAUDE.md.
"""

from typing import Protocol, runtime_checkable

from shotgun.agents.error.classifier import ErrorType
from shotgun.agents.error.models import ErrorMessage


@runtime_checkable
class AgentErrorHandler(Protocol):
    """Protocol for handling agent execution errors.

    Different implementations can handle errors in interface-specific ways:
    - TUI: Display hints and messages in the chat interface
    - CLI: Print formatted messages to console

    This protocol enables dependency inversion, allowing the agent runner to
    work with any error handler without tight coupling to specific interfaces.
    """

    def handle_cancellation(self) -> None:
        """Handle operation cancellation by user.

        This is called when the user cancels agent execution (e.g., ESC or Ctrl+C).
        """
        ...

    def handle_error(self, error_type: ErrorType, error_message: ErrorMessage) -> None:
        """Handle an agent execution error.

        Args:
            error_type: The classified error type
            error_message: Formatted error message with optional email component
        """
        ...

    def handle_success(self) -> None:
        """Handle successful agent execution.

        This is called after the agent completes successfully, allowing the
        handler to perform any cleanup or success notifications.
        """
        ...
