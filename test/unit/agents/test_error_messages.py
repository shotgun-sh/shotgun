"""Unit tests for exception message formatting."""

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


def test_cancelled_exception_markdown():
    """Test AgentCancelledException markdown formatting."""
    exc = AgentCancelledException()
    message = exc.to_markdown()
    assert "Operation cancelled by user" in message
    assert message.startswith("⚠️")


def test_cancelled_exception_plain_text():
    """Test AgentCancelledException plain text formatting."""
    exc = AgentCancelledException()
    message = exc.to_plain_text()
    assert "Operation cancelled by user" in message
    assert "⚠️" in message


def test_context_size_exceeded_markdown():
    """Test ContextSizeLimitExceeded markdown formatting."""
    exc = ContextSizeLimitExceeded(model_name="gpt-4", max_tokens=8000)
    message = exc.to_markdown()
    assert "Context too large" in message
    assert "gpt-4" in message
    assert "8,000 tokens" in message
    assert "Switch to a larger model" in message
    assert "`/compact`" in message  # Markdown code formatting


def test_context_size_exceeded_plain_text():
    """Test ContextSizeLimitExceeded plain text formatting."""
    exc = ContextSizeLimitExceeded(model_name="gpt-4", max_tokens=8000)
    message = exc.to_plain_text()
    assert "Context too large" in message
    assert "gpt-4" in message
    assert "8,000 tokens" in message
    assert "Switch to a larger model" in message
    assert "`" not in message  # No markdown in plain text


def test_budget_exceeded_markdown():
    """Test BudgetExceededException markdown formatting."""
    exc = BudgetExceededException(message="Budget exceeded error details")
    message = exc.to_markdown()
    assert "budget has been exceeded" in message
    assert "spending limit" in message
    assert "Budget exceeded error details" in message


def test_budget_exceeded_plain_text():
    """Test BudgetExceededException plain text formatting."""
    exc = BudgetExceededException(message="Budget exceeded error details")
    message = exc.to_plain_text()
    assert "budget has been exceeded" in message
    assert "contact@shotgun.sh" in message


def test_byok_rate_limit():
    """Test BYOKRateLimitException formatting."""
    exc = BYOKRateLimitException("Rate limit exceeded")
    markdown = exc.to_markdown()
    plain = exc.to_plain_text()

    assert "Rate limit reached" in markdown
    assert "Rate limit exceeded" in markdown
    assert "Shotgun Account" in markdown
    assert "https://shotgun.sh" in markdown

    assert "Rate limit reached" in plain
    assert "Shotgun Account" in plain


def test_byok_quota_billing():
    """Test BYOKQuotaBillingException formatting."""
    exc = BYOKQuotaBillingException("Quota exceeded")
    markdown = exc.to_markdown()

    assert "Quota or billing issue" in markdown
    assert "Shotgun Account" in markdown


def test_byok_authentication():
    """Test BYOKAuthenticationException formatting."""
    exc = BYOKAuthenticationException("Invalid API key")
    markdown = exc.to_markdown()

    assert "Authentication error" in markdown
    assert "Shotgun Account" in markdown


def test_byok_service_overload():
    """Test BYOKServiceOverloadException formatting."""
    exc = BYOKServiceOverloadException("Service overloaded")
    markdown = exc.to_markdown()

    assert "Service overloaded" in markdown
    assert "Shotgun Account" in markdown


def test_byok_generic_api():
    """Test BYOKGenericAPIException formatting."""
    exc = BYOKGenericAPIException("API error")
    markdown = exc.to_markdown()

    assert "API error" in markdown
    assert "Shotgun Account" in markdown


def test_shotgun_service_overload():
    """Test ShotgunServiceOverloadException formatting."""
    exc = ShotgunServiceOverloadException()
    markdown = exc.to_markdown()
    plain = exc.to_plain_text()

    assert "temporarily overloaded" in markdown
    assert "wait a moment" in markdown
    assert "temporarily overloaded" in plain


def test_shotgun_rate_limit():
    """Test ShotgunRateLimitException formatting."""
    exc = ShotgunRateLimitException()
    markdown = exc.to_markdown()

    assert "Rate limit reached" in markdown
    assert "wait before trying again" in markdown


def test_generic_api_status():
    """Test GenericAPIStatusException formatting."""
    exc = GenericAPIStatusException("Some API error")
    markdown = exc.to_markdown()
    plain = exc.to_plain_text()

    assert "AI service error" in markdown
    assert "Some API error" in markdown
    assert "AI service error" in plain


def test_unknown_agent_exception():
    """Test UnknownAgentException formatting."""
    original = ValueError("Unknown error")
    exc = UnknownAgentException(original)
    markdown = exc.to_markdown()
    plain = exc.to_plain_text()

    assert "An error occurred" in markdown
    assert "Unknown error" in markdown
    assert "logs" in markdown.lower()
    assert "shotgun.log" in markdown

    assert "An error occurred" in plain
    assert "Unknown error" in plain


def test_all_exceptions_have_formatting_methods():
    """Test that all exception classes have required formatting methods."""
    exceptions = [
        AgentCancelledException(),
        ContextSizeLimitExceeded("gpt-4", 8000),
        BudgetExceededException(),
        BYOKRateLimitException("test"),
        BYOKQuotaBillingException("test"),
        BYOKAuthenticationException("test"),
        BYOKServiceOverloadException("test"),
        BYOKGenericAPIException("test"),
        ShotgunServiceOverloadException(),
        ShotgunRateLimitException(),
        GenericAPIStatusException("test"),
        UnknownAgentException(ValueError("test")),
    ]

    for exc in exceptions:
        # All should have both methods
        assert hasattr(exc, "to_markdown")
        assert hasattr(exc, "to_plain_text")

        # Both should return non-empty strings
        markdown = exc.to_markdown()
        plain = exc.to_plain_text()

        assert isinstance(markdown, str)
        assert isinstance(plain, str)
        assert len(markdown) > 0
        assert len(plain) > 0
