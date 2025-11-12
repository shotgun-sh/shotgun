"""CLI-specific error handling utilities.

This module provides utilities for displaying agent errors in the CLI
by printing formatted messages to the console.
"""

from rich.console import Console

from shotgun.exceptions import ErrorNotPickedUpBySentry

console = Console(stderr=True)


def print_agent_error(exception: ErrorNotPickedUpBySentry) -> None:
    """Print an agent error to the console in yellow.

    Args:
        exception: The error exception with formatting methods
    """
    # Get plain text version for CLI
    message = exception.to_plain_text()

    # Print with yellow styling
    console.print(message, style="yellow")
