"""Unified agent execution with consistent error handling.

This module provides a reusable agent runner that wraps agent execution exceptions
in user-friendly custom exceptions that can be caught and displayed by TUI or CLI.
"""

import asyncio
import logging
from typing import TYPE_CHECKING, NoReturn

from anthropic import APIStatusError as AnthropicAPIStatusError
from openai import APIStatusError as OpenAIAPIStatusError
from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior

from shotgun.agents.error.models import AgentErrorContext
from shotgun.exceptions import (
    AgentCancelledException,
    BudgetExceededException,
    BYOKAuthenticationException,
    BYOKGenericAPIException,
    BYOKQuotaBillingException,
    BYOKRateLimitException,
    BYOKServiceOverloadException,
    ContextSizeLimitExceeded,
    GenericAPIStatusException,
    ShotgunRateLimitException,
    ShotgunServiceOverloadException,
    UnknownAgentException,
)

if TYPE_CHECKING:
    from shotgun.agents.agent_manager import AgentManager

logger = logging.getLogger(__name__)


class AgentRunner:
    """Unified agent execution wrapper with consistent error handling.

    This class wraps agent execution and converts any exceptions into
    user-friendly custom exceptions that can be caught and displayed by the
    calling interface (TUI or CLI).

    The runner:
    - Executes the agent
    - Logs errors for debugging
    - Wraps exceptions in custom exception types (AgentCancelledException,
      BYOKRateLimitException, etc.)
    - Lets exceptions propagate to caller for display

    Example:
        >>> runner = AgentRunner(agent_manager)
        >>> try:
        >>>     await runner.run("Write a hello world function")
        >>> except ContextSizeLimitExceeded as e:
        >>>     print(e.to_markdown())
        >>> except BYOKRateLimitException as e:
        >>>     print(e.to_plain_text())
    """

    def __init__(self, agent_manager: "AgentManager"):
        """Initialize the agent runner.

        Args:
            agent_manager: The agent manager to execute
        """
        self.agent_manager = agent_manager

    async def run(self, prompt: str) -> None:
        """Run the agent with the given prompt.

        Args:
            prompt: The user's prompt/query

        Raises:
            Custom exceptions for different error types:
            - AgentCancelledException: User cancelled the operation
            - ContextSizeLimitExceeded: Context too large for model
            - BudgetExceededException: Shotgun Account budget exceeded
            - BYOKRateLimitException: BYOK rate limit hit
            - BYOKQuotaBillingException: BYOK quota/billing issue
            - BYOKAuthenticationException: BYOK authentication failed
            - BYOKServiceOverloadException: BYOK service overloaded
            - BYOKGenericAPIException: Generic BYOK API error
            - ShotgunServiceOverloadException: Shotgun service overloaded
            - ShotgunRateLimitException: Shotgun rate limit hit
            - GenericAPIStatusException: Generic API error
            - UnknownAgentException: Unknown/unclassified error
        """
        try:
            await self.agent_manager.run(prompt=prompt)

        except asyncio.CancelledError as e:
            # User cancelled - wrap and re-raise as our custom exception
            context = self._create_error_context(e)
            self._classify_and_raise(context)

        except ContextSizeLimitExceeded as e:
            # Already a custom exception - log and re-raise
            logger.info(
                "Context size limit exceeded",
                extra={
                    "max_tokens": e.max_tokens,
                    "model_name": e.model_name,
                },
            )
            raise

        except Exception as e:
            # Log with full stack trace to shotgun.log
            logger.exception(
                "Agent run failed",
                extra={
                    "agent_mode": self.agent_manager._current_agent_type.value,
                    "error_type": type(e).__name__,
                },
            )

            # Create error context and wrap/raise custom exception
            context = self._create_error_context(e)
            self._classify_and_raise(context)

    def _create_error_context(self, exception: BaseException) -> AgentErrorContext:
        """Create error context from exception and agent state.

        Args:
            exception: The exception that was raised

        Returns:
            AgentErrorContext with all necessary information for classification
        """
        return AgentErrorContext(
            exception=exception,
            is_shotgun_account=self.agent_manager.deps.llm_model.is_shotgun_account,
        )

    def _classify_and_raise(self, context: AgentErrorContext) -> NoReturn:
        """Classify an exception and raise the appropriate custom exception.

        Args:
            context: Context information about the error

        Raises:
            Custom exception based on the error type
        """
        exception = context.exception
        error_name = type(exception).__name__
        error_message = str(exception)

        # Check for cancellation
        if isinstance(exception, asyncio.CancelledError):
            raise AgentCancelledException() from exception

        # Check for context size limit exceeded
        if isinstance(exception, ContextSizeLimitExceeded):
            # Already the right exception type, re-raise it
            raise exception

        # Check for budget exceeded (Shotgun Account only)
        if (
            context.is_shotgun_account
            and "apistatuserror" in error_name.lower()
            and "budget" in error_message.lower()
            and "exceeded" in error_message.lower()
        ):
            raise BudgetExceededException(message=error_message) from exception

        # Check for empty model response (e.g., model unavailable or misconfigured)
        if isinstance(exception, UnexpectedModelBehavior):
            raise GenericAPIStatusException(
                "The model returned an empty response. This may indicate:\n"
                "- The model is unavailable or misconfigured\n"
                "- A temporary service issue\n\n"
                "Try switching to a different model or try again later."
            ) from exception

        # Detect API errors
        is_api_error = False
        if isinstance(exception, OpenAIAPIStatusError):
            is_api_error = True
        elif isinstance(exception, AnthropicAPIStatusError):
            is_api_error = True
        elif isinstance(exception, ModelHTTPError):
            # pydantic_ai wraps API errors in ModelHTTPError
            # Check for HTTP error status codes (4xx client errors)
            if 400 <= exception.status_code < 500:
                is_api_error = True

        # BYOK user API errors
        if not context.is_shotgun_account and is_api_error:
            self._raise_byok_api_error(error_message, exception)

        # Shotgun Account specific errors
        if "APIStatusError" in error_name:
            if "overload" in error_message.lower():
                raise ShotgunServiceOverloadException(error_message) from exception
            elif "rate" in error_message.lower():
                raise ShotgunRateLimitException(error_message) from exception
            else:
                raise GenericAPIStatusException(error_message) from exception

        # Unknown error - wrap in our custom exception
        raise UnknownAgentException(exception) from exception

    def _raise_byok_api_error(
        self, error_message: str, original_exception: Exception
    ) -> NoReturn:
        """Classify and raise API errors for BYOK users into specific types.

        Args:
            error_message: The error message from the API
            original_exception: The original exception

        Raises:
            Specific BYOK exception type
        """
        error_lower = error_message.lower()

        if "rate" in error_lower:
            raise BYOKRateLimitException(error_message) from original_exception
        elif "quota" in error_lower or "billing" in error_lower:
            raise BYOKQuotaBillingException(error_message) from original_exception
        elif "authentication" in error_lower or (
            "invalid" in error_lower and "key" in error_lower
        ):
            raise BYOKAuthenticationException(error_message) from original_exception
        elif "overload" in error_lower:
            raise BYOKServiceOverloadException(error_message) from original_exception
        else:
            raise BYOKGenericAPIException(error_message) from original_exception
