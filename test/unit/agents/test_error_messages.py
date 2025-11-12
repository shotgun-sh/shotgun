"""Unit tests for error message generation."""

from shotgun.agents.error import (
    AgentErrorContext,
    ErrorMessageGenerator,
    ErrorType,
)
from shotgun.agents.models import AgentType
from shotgun.exceptions import ContextSizeLimitExceeded


def test_generate_cancelled_message_markdown():
    """Test generation of cancellation message with markdown."""
    context = AgentErrorContext(
        exception=Exception("test"),
        is_shotgun_account=False,
        model_name="gpt-4",
        agent_mode=AgentType.RESEARCH,
    )

    result = ErrorMessageGenerator.generate(
        ErrorType.CANCELLED, context, use_markdown=True
    )

    assert "Operation cancelled by user" in result.message
    assert result.requires_email_component is False


def test_generate_cancelled_message_plain_text():
    """Test generation of cancellation message without markdown."""
    context = AgentErrorContext(
        exception=Exception("test"),
        is_shotgun_account=False,
        model_name="gpt-4",
        agent_mode=AgentType.RESEARCH,
    )

    result = ErrorMessageGenerator.generate(
        ErrorType.CANCELLED, context, use_markdown=False
    )

    assert "Operation cancelled by user" in result.message
    assert result.requires_email_component is False


def test_generate_context_size_exceeded_markdown():
    """Test generation of context size exceeded message with markdown."""
    exc = ContextSizeLimitExceeded(model_name="gpt-4", max_tokens=8000)
    context = AgentErrorContext(
        exception=exc,
        is_shotgun_account=False,
        model_name="gpt-4",
        agent_mode=AgentType.RESEARCH,
    )

    result = ErrorMessageGenerator.generate(
        ErrorType.CONTEXT_SIZE_EXCEEDED, context, use_markdown=True
    )

    assert "Context too large" in result.message
    assert "gpt-4" in result.message
    assert "8,000 tokens" in result.message
    assert "Switch to a larger model" in result.message
    assert "`/compact`" in result.message  # Markdown code formatting
    assert result.requires_email_component is False


def test_generate_context_size_exceeded_plain_text():
    """Test generation of context size exceeded message without markdown."""
    exc = ContextSizeLimitExceeded(model_name="gpt-4", max_tokens=8000)
    context = AgentErrorContext(
        exception=exc,
        is_shotgun_account=False,
        model_name="gpt-4",
        agent_mode=AgentType.RESEARCH,
    )

    result = ErrorMessageGenerator.generate(
        ErrorType.CONTEXT_SIZE_EXCEEDED, context, use_markdown=False
    )

    assert "Context too large" in result.message
    assert "gpt-4" in result.message
    assert "8,000 tokens" in result.message
    assert "Switch to a larger model" in result.message
    assert "`/compact`" not in result.message  # No markdown in plain text
    assert result.requires_email_component is False


def test_generate_budget_exceeded_markdown():
    """Test generation of budget exceeded message with markdown."""
    context = AgentErrorContext(
        exception=Exception("Budget exceeded error details"),
        is_shotgun_account=True,
        model_name="gpt-4",
        agent_mode=AgentType.RESEARCH,
    )

    result = ErrorMessageGenerator.generate(
        ErrorType.BUDGET_EXCEEDED, context, use_markdown=True
    )

    assert "budget has been exceeded" in result.message
    assert "spending limit" in result.message
    assert result.requires_email_component is True
    assert result.email == "contact@shotgun.sh"
    assert result.email_context is not None
    assert "Self-service budget increases" in result.email_context
    assert "Budget exceeded error details" in result.email_context


def test_generate_budget_exceeded_plain_text():
    """Test generation of budget exceeded message without markdown."""
    context = AgentErrorContext(
        exception=Exception("Budget exceeded error details"),
        is_shotgun_account=True,
        model_name="gpt-4",
        agent_mode=AgentType.RESEARCH,
    )

    result = ErrorMessageGenerator.generate(
        ErrorType.BUDGET_EXCEEDED, context, use_markdown=False
    )

    assert "budget has been exceeded" in result.message
    assert "contact@shotgun.sh" in result.message
    assert result.requires_email_component is False  # Plain text uses inline email


def test_generate_byok_rate_limit_markdown():
    """Test generation of BYOK rate limit message with markdown."""
    context = AgentErrorContext(
        exception=Exception("Rate limit exceeded"),
        is_shotgun_account=False,
        model_name="gpt-4",
        agent_mode=AgentType.RESEARCH,
    )

    result = ErrorMessageGenerator.generate(
        ErrorType.BYOK_RATE_LIMIT, context, use_markdown=True
    )

    assert "Rate limit reached" in result.message
    assert "Rate limit exceeded" in result.message
    assert "Shotgun Account" in result.message
    assert "https://shotgun.sh" in result.message
    assert result.requires_email_component is False


def test_generate_byok_quota_billing():
    """Test generation of BYOK quota/billing error message."""
    context = AgentErrorContext(
        exception=Exception("Quota exceeded"),
        is_shotgun_account=False,
        model_name="gpt-4",
        agent_mode=AgentType.RESEARCH,
    )

    result = ErrorMessageGenerator.generate(
        ErrorType.BYOK_QUOTA_BILLING, context, use_markdown=True
    )

    assert "Quota or billing issue" in result.message
    assert "Shotgun Account" in result.message


def test_generate_byok_authentication():
    """Test generation of BYOK authentication error message."""
    context = AgentErrorContext(
        exception=Exception("Invalid API key"),
        is_shotgun_account=False,
        model_name="gpt-4",
        agent_mode=AgentType.RESEARCH,
    )

    result = ErrorMessageGenerator.generate(
        ErrorType.BYOK_AUTHENTICATION, context, use_markdown=True
    )

    assert "Authentication error" in result.message
    assert "Shotgun Account" in result.message


def test_generate_byok_service_overload():
    """Test generation of BYOK service overload message."""
    context = AgentErrorContext(
        exception=Exception("Service overloaded"),
        is_shotgun_account=False,
        model_name="gpt-4",
        agent_mode=AgentType.RESEARCH,
    )

    result = ErrorMessageGenerator.generate(
        ErrorType.BYOK_SERVICE_OVERLOAD, context, use_markdown=True
    )

    assert "Service overloaded" in result.message
    assert "Shotgun Account" in result.message


def test_generate_byok_generic_api():
    """Test generation of BYOK generic API error message."""
    context = AgentErrorContext(
        exception=Exception("API error"),
        is_shotgun_account=False,
        model_name="gpt-4",
        agent_mode=AgentType.RESEARCH,
    )

    result = ErrorMessageGenerator.generate(
        ErrorType.BYOK_GENERIC_API, context, use_markdown=True
    )

    assert "API error" in result.message
    assert "Shotgun Account" in result.message


def test_generate_shotgun_service_overload():
    """Test generation of Shotgun Account service overload message."""
    context = AgentErrorContext(
        exception=Exception("Service overloaded"),
        is_shotgun_account=True,
        model_name="gpt-4",
        agent_mode=AgentType.RESEARCH,
    )

    result = ErrorMessageGenerator.generate(
        ErrorType.SHOTGUN_SERVICE_OVERLOAD, context, use_markdown=True
    )

    assert "temporarily overloaded" in result.message
    assert "wait a moment" in result.message


def test_generate_shotgun_rate_limit():
    """Test generation of Shotgun Account rate limit message."""
    context = AgentErrorContext(
        exception=Exception("Rate limit"),
        is_shotgun_account=True,
        model_name="gpt-4",
        agent_mode=AgentType.RESEARCH,
    )

    result = ErrorMessageGenerator.generate(
        ErrorType.SHOTGUN_RATE_LIMIT, context, use_markdown=True
    )

    assert "Rate limit reached" in result.message
    assert "wait before trying again" in result.message


def test_generate_generic_api_status():
    """Test generation of generic API status error message."""
    context = AgentErrorContext(
        exception=Exception("Some API error"),
        is_shotgun_account=True,
        model_name="gpt-4",
        agent_mode=AgentType.RESEARCH,
    )

    result = ErrorMessageGenerator.generate(
        ErrorType.GENERIC_API_STATUS, context, use_markdown=True
    )

    assert "AI service error" in result.message
    assert "Some API error" in result.message


def test_generate_unknown_error():
    """Test generation of unknown error message."""
    context = AgentErrorContext(
        exception=Exception("Unknown error"),
        is_shotgun_account=False,
        model_name="gpt-4",
        agent_mode=AgentType.RESEARCH,
    )

    result = ErrorMessageGenerator.generate(
        ErrorType.UNKNOWN, context, use_markdown=True
    )

    assert "An error occurred" in result.message
    assert "Unknown error" in result.message
    assert "logs" in result.message.lower()
    assert "shotgun.log" in result.message


def test_message_format_consistency():
    """Test that all error types generate valid ErrorMessage objects."""
    context = AgentErrorContext(
        exception=Exception("test"),
        is_shotgun_account=False,
        model_name="gpt-4",
        agent_mode=AgentType.RESEARCH,
    )

    # Test all error types
    error_types = [
        ErrorType.CANCELLED,
        ErrorType.SHOTGUN_SERVICE_OVERLOAD,
        ErrorType.SHOTGUN_RATE_LIMIT,
        ErrorType.GENERIC_API_STATUS,
        ErrorType.UNKNOWN,
    ]

    for error_type in error_types:
        result = ErrorMessageGenerator.generate(error_type, context, use_markdown=True)
        assert isinstance(result.message, str)
        assert len(result.message) > 0
        assert isinstance(result.requires_email_component, bool)
