"""Unified agent execution with consistent error handling.

This module provides a reusable agent runner that handles execution and error
classification, delegating interface-specific behavior to an error handler protocol.
"""

import asyncio
import logging
from typing import TYPE_CHECKING

from shotgun.agents.error import (
    AgentErrorClassifier,
    AgentErrorContext,
    AgentErrorHandler,
    ErrorMessageGenerator,
)
from shotgun.exceptions import ContextSizeLimitExceeded

if TYPE_CHECKING:
    from shotgun.agents.agent_manager import AgentManager

logger = logging.getLogger(__name__)


class AgentRunner:
    """Unified agent execution wrapper with consistent error handling.

    This class provides a single point of control for agent execution that:
    - Handles all exception types consistently
    - Classifies errors into well-defined types
    - Generates user-friendly error messages
    - Delegates interface-specific handling to error handler protocol

    Example:
        >>> from shotgun.cli.error_handler import CLIErrorHandler
        >>> runner = AgentRunner(agent_manager, CLIErrorHandler())
        >>> await runner.run("Write a hello world function")
    """

    def __init__(self, agent_manager: "AgentManager", error_handler: AgentErrorHandler):
        """Initialize the agent runner.

        Args:
            agent_manager: The agent manager to execute
            error_handler: Handler for interface-specific error display
        """
        self.agent_manager = agent_manager
        self.error_handler = error_handler

    async def run(self, prompt: str, use_markdown: bool = True) -> bool:
        """Run the agent with the given prompt.

        Args:
            prompt: The user's prompt/query
            use_markdown: Whether to generate markdown-formatted messages (TUI)
                         or plain text (CLI). Default: True.

        Returns:
            True if execution succeeded, False if an error occurred
        """
        try:
            await self.agent_manager.run(prompt=prompt)
            self.error_handler.handle_success()
            return True

        except asyncio.CancelledError:
            # Handle cancellation gracefully - DO NOT re-raise
            # The error handler will display the cancellation message
            self.error_handler.handle_cancellation()
            return False

        except ContextSizeLimitExceeded as e:
            # Log for debugging (won't send to Sentry due to ErrorNotPickedUpBySentry)
            logger.info(
                "Context size limit exceeded",
                extra={
                    "max_tokens": e.max_tokens,
                    "model_name": e.model_name,
                },
            )

            # Create error context and classify
            context = AgentErrorContext(
                exception=e,
                is_shotgun_account=self.agent_manager.deps.llm_model.is_shotgun_account,
                model_name=self.agent_manager.deps.llm_model.name,
                agent_mode=self.agent_manager._current_agent_type,
            )

            error_type = AgentErrorClassifier.classify(context)
            error_message = ErrorMessageGenerator.generate(
                error_type, context, use_markdown
            )
            self.error_handler.handle_error(error_type, error_message)
            return False

        except Exception as e:
            # Log with full stack trace to shotgun.log
            logger.exception(
                "Agent run failed",
                extra={
                    "agent_mode": self.agent_manager._current_agent_type.value,
                    "error_type": type(e).__name__,
                },
            )

            # Create error context and classify
            context = AgentErrorContext(
                exception=e,
                is_shotgun_account=self.agent_manager.deps.llm_model.is_shotgun_account,
                model_name=self.agent_manager.deps.llm_model.name,
                agent_mode=self.agent_manager._current_agent_type,
            )

            error_type = AgentErrorClassifier.classify(context)
            error_message = ErrorMessageGenerator.generate(
                error_type, context, use_markdown
            )
            self.error_handler.handle_error(error_type, error_message)
            return False
