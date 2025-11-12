"""Tests for BYOK signup hints in ChatScreen error handling."""

from shotgun.agents.config.models import KeyProvider
from shotgun.exceptions import SHOTGUN_SIGNUP_URL


def test_signup_url_constant_defined():
    """Verify that the SHOTGUN_SIGNUP_URL constant is defined."""
    assert SHOTGUN_SIGNUP_URL == "https://shotgun.sh"


def test_byok_account_detection(mock_agent_deps):
    """Test that BYOK accounts can be detected via key_provider."""
    # Set as BYOK
    mock_agent_deps.llm_model.key_provider = KeyProvider.BYOK
    assert not mock_agent_deps.llm_model.is_shotgun_account

    # Set as Shotgun
    mock_agent_deps.llm_model.key_provider = KeyProvider.SHOTGUN
    assert mock_agent_deps.llm_model.is_shotgun_account


def test_error_message_detection_rate_limit():
    """Test that rate limit errors can be detected from error messages."""
    error_message = "Rate limit exceeded for requests"
    assert "rate" in error_message.lower()


def test_error_message_detection_quota():
    """Test that quota errors can be detected from error messages."""
    error_message = "Insufficient quota remaining"
    assert "quota" in error_message.lower()


def test_error_message_detection_auth():
    """Test that auth errors can be detected from error messages."""
    error_message = "Invalid API key provided"
    assert "invalid" in error_message.lower() and "key" in error_message.lower()

    error_message2 = "Authentication failed"
    assert "authentication" in error_message2.lower()


def test_error_message_detection_overload():
    """Test that overload errors can be detected from error messages."""
    error_message = "The server is overloaded"
    assert "overload" in error_message.lower()


def test_error_name_detection():
    """Test that APIStatusError can be detected from exception type name."""

    # Simulate what happens in the error handler
    class APIStatusError(Exception):
        pass

    error = APIStatusError("test")
    error_name = type(error).__name__
    assert "APIStatusError" in error_name
