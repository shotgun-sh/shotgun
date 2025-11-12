"""CLI-specific error handler implementation.

This module provides an error handler that displays errors in the CLI
by printing formatted messages to the console.
"""

import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from rich.console import Console

from shotgun.agents.error_classifier import (
    AgentErrorClassifier,
    AgentErrorContext,
    ErrorType,
)
from shotgun.agents.error_messages import ErrorMessage, ErrorMessageGenerator
from shotgun.agents.models import AgentDeps, AgentType
from shotgun.exceptions import ContextSizeLimitExceeded

console = Console(stderr=True)
logger = logging.getLogger(__name__)

T = TypeVar("T")


class CLIErrorHandler:
    """Error handler for CLI interface.

    This handler implements the AgentErrorHandler protocol and displays
    errors as formatted console output with rich formatting for better
    readability.
    """

    def handle_cancellation(self) -> None:
        """Handle operation cancellation by printing a message."""
        console.print("⚠️  Operation cancelled by user", style="yellow")

    def handle_error(
        self, error_type: ErrorType, error_message: ErrorMessage
    ) -> None:
        """Handle an agent execution error by printing to console.

        Args:
            error_type: The classified error type
            error_message: Formatted error message (plain text for CLI)
        """
        # Print the error message with yellow styling
        console.print(error_message.message, style="yellow")

        # If there's email context, print it separately
        if error_message.email_context:
            console.print(error_message.email_context, style="yellow dim")

    def handle_success(self) -> None:
        """Handle successful agent execution.

        For CLI, this is a no-op as success is indicated by the agent's output.
        """


async def run_with_error_handling(
    func: Callable[..., Awaitable[T]],
    deps: AgentDeps,
    agent_type: AgentType,
    *args: Any,
    **kwargs: Any,
) -> T | None:
    """Run an async function with sophisticated error handling.

    This helper function wraps CLI agent execution to provide the same
    sophisticated error handling as the TUI, including error classification,
    user-friendly messages, and proper logging.

    Args:
        func: The async function to execute (e.g., run_research_agent)
        deps: Agent dependencies for error context
        agent_type: The type of agent being run
        *args: Positional arguments to pass to func
        **kwargs: Keyword arguments to pass to func

    Returns:
        The result of func, or None if an error occurred

    Example:
        >>> result = await run_with_error_handling(
        ...     run_research_agent,
        ...     deps,
        ...     AgentType.RESEARCH,
        ...     agent,
        ...     query,
        ...     deps
        ... )
    """
    try:
        return await func(*args, **kwargs)
    except ContextSizeLimitExceeded as e:
        # Log for debugging
        logger.info(
            "Context size limit exceeded",
            extra={
                "max_tokens": e.max_tokens,
                "model_name": e.model_name,
            },
        )

        # Classify and display error
        context = AgentErrorContext(
            exception=e,
            is_shotgun_account=deps.llm_model.is_shotgun_account,
            model_name=deps.llm_model.name,
            agent_mode=agent_type,
        )
        error_type = AgentErrorClassifier.classify(context)
        error_message = ErrorMessageGenerator.generate(
            error_type, context, use_markdown=False
        )
        handler = CLIErrorHandler()
        handler.handle_error(error_type, error_message)
        return None
    except Exception as e:
        # Log with full stack trace
        logger.exception(
            "Agent run failed",
            extra={
                "agent_mode": agent_type.value,
                "error_type": type(e).__name__,
            },
        )

        # Classify and display error
        context = AgentErrorContext(
            exception=e,
            is_shotgun_account=deps.llm_model.is_shotgun_account,
            model_name=deps.llm_model.name,
            agent_mode=agent_type,
        )
        error_type = AgentErrorClassifier.classify(context)
        error_message = ErrorMessageGenerator.generate(
            error_type, context, use_markdown=False
        )
        handler = CLIErrorHandler()
        handler.handle_error(error_type, error_message)
        return None
