"""Error classification for agent execution failures.

This module provides utilities to classify and handle errors that occur during
agent execution, making error handling consistent across TUI and CLI interfaces.
"""

import asyncio
from dataclasses import dataclass
from enum import Enum

from anthropic import APIStatusError as AnthropicAPIStatusError
from openai import APIStatusError as OpenAIAPIStatusError
from pydantic_ai.exceptions import ModelHTTPError

from shotgun.agents.models import AgentType
from shotgun.exceptions import ContextSizeLimitExceeded


class ErrorType(str, Enum):
    """Enumeration of error types that can occur during agent execution."""

    CANCELLED = "cancelled"
    CONTEXT_SIZE_EXCEEDED = "context_size_exceeded"
    BUDGET_EXCEEDED = "budget_exceeded"
    BYOK_RATE_LIMIT = "byok_rate_limit"
    BYOK_QUOTA_BILLING = "byok_quota_billing"
    BYOK_AUTHENTICATION = "byok_authentication"
    BYOK_SERVICE_OVERLOAD = "byok_service_overload"
    BYOK_GENERIC_API = "byok_generic_api"
    SHOTGUN_SERVICE_OVERLOAD = "shotgun_service_overload"
    SHOTGUN_RATE_LIMIT = "shotgun_rate_limit"
    GENERIC_API_STATUS = "generic_api_status"
    UNKNOWN = "unknown"


@dataclass
class AgentErrorContext:
    """Context information needed to classify and handle agent errors.

    Attributes:
        exception: The exception that was raised
        is_shotgun_account: Whether the user is using a Shotgun Account
        model_name: Name of the model being used
        agent_mode: Current agent type (research, tasks, etc.)
    """

    exception: Exception
    is_shotgun_account: bool
    model_name: str
    agent_mode: AgentType


class AgentErrorClassifier:
    """Classifier for agent execution errors.

    This class provides methods to classify exceptions that occur during agent
    execution into well-defined error types, enabling consistent error handling
    across different interfaces (TUI, CLI).
    """

    @staticmethod
    def classify(context: AgentErrorContext) -> ErrorType:
        """Classify an exception into a specific error type.

        Args:
            context: Context information about the error

        Returns:
            The classified error type
        """
        exception = context.exception
        error_name = type(exception).__name__
        error_message = str(exception)

        # Check for cancellation
        if isinstance(exception, asyncio.CancelledError):
            return ErrorType.CANCELLED

        # Check for context size limit exceeded
        if isinstance(exception, ContextSizeLimitExceeded):
            return ErrorType.CONTEXT_SIZE_EXCEEDED

        # Check for budget exceeded (Shotgun Account only)
        if (
            context.is_shotgun_account
            and "apistatuserror" in error_name.lower()
            and "budget" in error_message.lower()
            and "exceeded" in error_message.lower()
        ):
            return ErrorType.BUDGET_EXCEEDED

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
            return AgentErrorClassifier._classify_byok_api_error(error_message)

        # Shotgun Account specific errors
        if "APIStatusError" in error_name:
            if "overload" in error_message.lower():
                return ErrorType.SHOTGUN_SERVICE_OVERLOAD
            elif "rate" in error_message.lower():
                return ErrorType.SHOTGUN_RATE_LIMIT
            else:
                return ErrorType.GENERIC_API_STATUS

        # Unknown error
        return ErrorType.UNKNOWN

    @staticmethod
    def _classify_byok_api_error(error_message: str) -> ErrorType:
        """Classify API errors for BYOK users into specific types.

        Args:
            error_message: The error message from the API

        Returns:
            Specific BYOK error type
        """
        error_lower = error_message.lower()

        if "rate" in error_lower:
            return ErrorType.BYOK_RATE_LIMIT
        elif "quota" in error_lower or "billing" in error_lower:
            return ErrorType.BYOK_QUOTA_BILLING
        elif "authentication" in error_lower or (
            "invalid" in error_lower and "key" in error_lower
        ):
            return ErrorType.BYOK_AUTHENTICATION
        elif "overload" in error_lower:
            return ErrorType.BYOK_SERVICE_OVERLOAD
        else:
            return ErrorType.BYOK_GENERIC_API
