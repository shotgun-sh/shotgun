"""Unit tests for context size exception classes."""

from shotgun.exceptions import ContextSizeLimitExceeded, UserActionableError


def test_user_actionable_error_is_exception():
    """UserActionableError should be an Exception."""
    error = UserActionableError("test message")
    assert isinstance(error, Exception)
    assert str(error) == "test message"


def test_context_size_limit_exceeded_inheritance():
    """ContextSizeLimitExceeded should inherit from UserActionableError."""
    error = ContextSizeLimitExceeded(model_name="test-model", max_tokens=1000)
    assert isinstance(error, UserActionableError)
    assert isinstance(error, Exception)


def test_context_size_limit_exceeded_attributes():
    """ContextSizeLimitExceeded should store model_name and max_tokens."""
    error = ContextSizeLimitExceeded(model_name="claude-sonnet-4.5", max_tokens=200000)

    assert error.model_name == "claude-sonnet-4.5"
    assert error.max_tokens == 200000


def test_context_size_limit_exceeded_message_formatting():
    """ContextSizeLimitExceeded should format message with commas."""
    error = ContextSizeLimitExceeded(model_name="gpt-5", max_tokens=400000)

    message = str(error)
    assert "gpt-5" in message
    assert "400,000" in message  # Should have comma formatting
    assert "limit" in message.lower()


def test_context_size_limit_exceeded_message_small_number():
    """ContextSizeLimitExceeded should format message correctly for small numbers."""
    error = ContextSizeLimitExceeded(model_name="test-model", max_tokens=999)

    message = str(error)
    assert "test-model" in message
    assert "999" in message  # No comma for numbers < 1000
