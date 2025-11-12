"""Unit tests for error classification logic."""

import asyncio

from anthropic import APIStatusError as AnthropicAPIStatusError
from openai import APIStatusError as OpenAIAPIStatusError
from pydantic_ai.exceptions import ModelHTTPError

from shotgun.agents.error import (
    AgentErrorClassifier,
    AgentErrorContext,
    ErrorType,
)
from shotgun.agents.models import AgentType
from shotgun.exceptions import ContextSizeLimitExceeded


def test_classify_cancelled_error():
    """Test classification of asyncio.CancelledError."""
    context = AgentErrorContext(
        exception=asyncio.CancelledError(),
        is_shotgun_account=False,
        model_name="gpt-4",
        agent_mode=AgentType.RESEARCH,
    )

    result = AgentErrorClassifier.classify(context)
    assert result == ErrorType.CANCELLED


def test_classify_context_size_exceeded():
    """Test classification of ContextSizeLimitExceeded."""
    context = AgentErrorContext(
        exception=ContextSizeLimitExceeded(model_name="gpt-4", max_tokens=8000),
        is_shotgun_account=False,
        model_name="gpt-4",
        agent_mode=AgentType.RESEARCH,
    )

    result = AgentErrorClassifier.classify(context)
    assert result == ErrorType.CONTEXT_SIZE_EXCEEDED


def test_classify_budget_exceeded_shotgun_account():
    """Test classification of budget exceeded for Shotgun Account."""

    # Create a mock APIStatusError
    class MockAPIStatusError(Exception):
        def __init__(self, message: str):
            self.message = message
            super().__init__(message)

        def __str__(self) -> str:
            return self.message

    MockAPIStatusError.__name__ = "APIStatusError"

    context = AgentErrorContext(
        exception=MockAPIStatusError("Your budget has been exceeded"),
        is_shotgun_account=True,
        model_name="gpt-4",
        agent_mode=AgentType.RESEARCH,
    )

    result = AgentErrorClassifier.classify(context)
    assert result == ErrorType.BUDGET_EXCEEDED


def test_classify_budget_exceeded_byok_not_detected():
    """Test that budget exceeded is not detected for BYOK users."""

    class MockAPIStatusError(Exception):
        def __init__(self, message: str):
            self.message = message
            super().__init__(message)

        def __str__(self) -> str:
            return self.message

    MockAPIStatusError.__name__ = "APIStatusError"

    context = AgentErrorContext(
        exception=MockAPIStatusError("Your budget has been exceeded"),
        is_shotgun_account=False,  # BYOK user
        model_name="gpt-4",
        agent_mode=AgentType.RESEARCH,
    )

    result = AgentErrorClassifier.classify(context)
    # Should not be classified as budget exceeded for BYOK
    assert result != ErrorType.BUDGET_EXCEEDED


def test_classify_byok_rate_limit():
    """Test classification of rate limit error for BYOK users."""

    # Mock OpenAI rate limit error
    class MockOpenAIError(OpenAIAPIStatusError):
        def __init__(self):
            self.message = "Rate limit exceeded"
            self.status_code = 429

        def __str__(self) -> str:
            return self.message

    context = AgentErrorContext(
        exception=MockOpenAIError(),
        is_shotgun_account=False,  # BYOK
        model_name="gpt-4",
        agent_mode=AgentType.RESEARCH,
    )

    result = AgentErrorClassifier.classify(context)
    assert result == ErrorType.BYOK_RATE_LIMIT


def test_classify_byok_quota_billing():
    """Test classification of quota/billing errors for BYOK users."""

    class MockOpenAIError(OpenAIAPIStatusError):
        def __init__(self):
            self.message = "You exceeded your quota for API calls"
            self.status_code = 429

        def __str__(self) -> str:
            return self.message

    context = AgentErrorContext(
        exception=MockOpenAIError(),
        is_shotgun_account=False,  # BYOK
        model_name="gpt-4",
        agent_mode=AgentType.RESEARCH,
    )

    result = AgentErrorClassifier.classify(context)
    assert result == ErrorType.BYOK_QUOTA_BILLING


def test_classify_byok_authentication():
    """Test classification of authentication errors for BYOK users."""

    class MockAnthropicError(AnthropicAPIStatusError):
        def __init__(self):
            self.message = "Invalid API key provided"
            self.status_code = 401

        def __str__(self) -> str:
            return self.message

    context = AgentErrorContext(
        exception=MockAnthropicError(),
        is_shotgun_account=False,  # BYOK
        model_name="claude-3-opus",
        agent_mode=AgentType.RESEARCH,
    )

    result = AgentErrorClassifier.classify(context)
    assert result == ErrorType.BYOK_AUTHENTICATION


def test_classify_byok_service_overload():
    """Test classification of service overload for BYOK users."""

    class MockOpenAIError(OpenAIAPIStatusError):
        def __init__(self):
            self.message = "The service is currently overloaded"
            self.status_code = 503

        def __str__(self) -> str:
            return self.message

    context = AgentErrorContext(
        exception=MockOpenAIError(),
        is_shotgun_account=False,  # BYOK
        model_name="gpt-4",
        agent_mode=AgentType.RESEARCH,
    )

    result = AgentErrorClassifier.classify(context)
    assert result == ErrorType.BYOK_SERVICE_OVERLOAD


def test_classify_byok_generic_api():
    """Test classification of generic API error for BYOK users."""

    class MockOpenAIError(OpenAIAPIStatusError):
        def __init__(self):
            self.message = "Something went wrong with the API"
            self.status_code = 500

        def __str__(self) -> str:
            return self.message

    context = AgentErrorContext(
        exception=MockOpenAIError(),
        is_shotgun_account=False,  # BYOK
        model_name="gpt-4",
        agent_mode=AgentType.RESEARCH,
    )

    result = AgentErrorClassifier.classify(context)
    assert result == ErrorType.BYOK_GENERIC_API


def test_classify_model_http_error_4xx():
    """Test classification of ModelHTTPError with 4xx status code."""

    class MockModelHTTPError(ModelHTTPError):
        def __init__(self):
            self.message = "Bad request"
            self.status_code = 400

        def __str__(self) -> str:
            return self.message

    context = AgentErrorContext(
        exception=MockModelHTTPError(),
        is_shotgun_account=False,  # BYOK
        model_name="gpt-4",
        agent_mode=AgentType.RESEARCH,
    )

    result = AgentErrorClassifier.classify(context)
    # Should be classified as BYOK API error
    assert result == ErrorType.BYOK_GENERIC_API


def test_classify_model_http_error_5xx_not_api_error():
    """Test that ModelHTTPError with 5xx is not treated as API error for classification."""

    class MockModelHTTPError(ModelHTTPError):
        def __init__(self):
            self.message = "Internal server error"
            self.status_code = 500

        def __str__(self) -> str:
            return self.message

    context = AgentErrorContext(
        exception=MockModelHTTPError(),
        is_shotgun_account=False,  # BYOK
        model_name="gpt-4",
        agent_mode=AgentType.RESEARCH,
    )

    result = AgentErrorClassifier.classify(context)
    # 5xx should not be classified as API error (only 4xx)
    assert result == ErrorType.UNKNOWN


def test_classify_shotgun_service_overload():
    """Test classification of service overload for Shotgun Account."""

    class MockAPIStatusError(Exception):
        def __init__(self, message: str):
            self.message = message
            super().__init__(message)

        def __str__(self) -> str:
            return self.message

    MockAPIStatusError.__name__ = "APIStatusError"

    context = AgentErrorContext(
        exception=MockAPIStatusError("The service is currently overloaded"),
        is_shotgun_account=True,
        model_name="gpt-4",
        agent_mode=AgentType.RESEARCH,
    )

    result = AgentErrorClassifier.classify(context)
    assert result == ErrorType.SHOTGUN_SERVICE_OVERLOAD


def test_classify_shotgun_rate_limit():
    """Test classification of rate limit for Shotgun Account."""

    class MockAPIStatusError(Exception):
        def __init__(self, message: str):
            self.message = message
            super().__init__(message)

        def __str__(self) -> str:
            return self.message

    MockAPIStatusError.__name__ = "APIStatusError"

    context = AgentErrorContext(
        exception=MockAPIStatusError("Rate limit has been reached"),
        is_shotgun_account=True,
        model_name="gpt-4",
        agent_mode=AgentType.RESEARCH,
    )

    result = AgentErrorClassifier.classify(context)
    assert result == ErrorType.SHOTGUN_RATE_LIMIT


def test_classify_generic_api_status():
    """Test classification of generic APIStatusError."""

    class MockAPIStatusError(Exception):
        def __init__(self, message: str):
            self.message = message
            super().__init__(message)

        def __str__(self) -> str:
            return self.message

    MockAPIStatusError.__name__ = "APIStatusError"

    context = AgentErrorContext(
        exception=MockAPIStatusError("Some other API error"),
        is_shotgun_account=True,
        model_name="gpt-4",
        agent_mode=AgentType.RESEARCH,
    )

    result = AgentErrorClassifier.classify(context)
    assert result == ErrorType.GENERIC_API_STATUS


def test_classify_unknown_error():
    """Test classification of unknown exceptions."""
    context = AgentErrorContext(
        exception=ValueError("Some random error"),
        is_shotgun_account=False,
        model_name="gpt-4",
        agent_mode=AgentType.RESEARCH,
    )

    result = AgentErrorClassifier.classify(context)
    assert result == ErrorType.UNKNOWN
