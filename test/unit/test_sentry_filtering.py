"""Unit tests for Sentry error filtering."""

from unittest.mock import patch

import pytest

from shotgun.exceptions import ContextSizeLimitExceeded, ErrorNotPickedUpBySentry


@pytest.fixture
def mock_settings():
    """Mock settings with Sentry DSN."""
    with patch("shotgun.sentry_telemetry.settings") as mock:
        mock.telemetry.sentry_dsn = "https://fake@sentry.io/123"
        yield mock


def test_before_send_filters_error_not_picked_up_by_sentry(mock_settings):
    """before_send should filter out ErrorNotPickedUpBySentry exceptions."""
    from shotgun.sentry_telemetry import setup_sentry_observability

    # Mock sentry_sdk inside the function
    with (
        patch("sentry_sdk.is_initialized", return_value=False),
        patch("sentry_sdk.init") as mock_init,
        patch("sentry_sdk.set_user"),
    ):
        # Setup Sentry
        setup_sentry_observability()

        # Get the before_send function that was passed to sentry_sdk.init
        init_call = mock_init.call_args
        before_send = init_call.kwargs["before_send"]

        # Create a mock event and hint with ErrorNotPickedUpBySentry
        event = {"exception": {"values": [{"type": "ErrorNotPickedUpBySentry"}]}}
        error = ErrorNotPickedUpBySentry("test error")
        hint = {"exc_info": (type(error), error, None)}

        # Call before_send
        result = before_send(event, hint)

        # Should return None to filter out the event
        assert result is None


def test_before_send_filters_context_size_limit_exceeded(mock_settings):
    """before_send should filter out ContextSizeLimitExceeded exceptions."""
    from shotgun.sentry_telemetry import setup_sentry_observability

    with (
        patch("sentry_sdk.is_initialized", return_value=False),
        patch("sentry_sdk.init") as mock_init,
        patch("sentry_sdk.set_user"),
    ):
        # Setup Sentry
        setup_sentry_observability()

        # Get the before_send function
        init_call = mock_init.call_args
        before_send = init_call.kwargs["before_send"]

        # Create a mock event and hint with ContextSizeLimitExceeded
        event = {"exception": {"values": [{"type": "ContextSizeLimitExceeded"}]}}
        error = ContextSizeLimitExceeded(model_name="test-model", max_tokens=1000)
        hint = {"exc_info": (type(error), error, None)}

        # Call before_send
        result = before_send(event, hint)

        # Should return None to filter out the event
        assert result is None


def test_before_send_allows_other_exceptions(mock_settings):
    """before_send should allow other exceptions through."""
    from shotgun.sentry_telemetry import setup_sentry_observability

    with (
        patch("sentry_sdk.is_initialized", return_value=False),
        patch("sentry_sdk.init") as mock_init,
        patch("sentry_sdk.set_user"),
    ):
        # Setup Sentry
        setup_sentry_observability()

        # Get the before_send function
        init_call = mock_init.call_args
        before_send = init_call.kwargs["before_send"]

        # Create a mock event and hint with a regular exception
        event = {"exception": {"values": [{"type": "ValueError"}]}}
        error = ValueError("test error")
        hint = {"exc_info": (type(error), error, None)}

        # Call before_send
        result = before_send(event, hint)

        # Should return the event (not filtered)
        assert result == event


def test_before_send_handles_missing_exc_info(mock_settings):
    """before_send should handle hints without exc_info."""
    from shotgun.sentry_telemetry import setup_sentry_observability

    with (
        patch("sentry_sdk.is_initialized", return_value=False),
        patch("sentry_sdk.init") as mock_init,
        patch("sentry_sdk.set_user"),
    ):
        # Setup Sentry
        setup_sentry_observability()

        # Get the before_send function
        init_call = mock_init.call_args
        before_send = init_call.kwargs["before_send"]

        # Create a mock event and hint without exc_info
        event = {"exception": {"values": [{"type": "Exception"}]}}
        hint = {}  # No exc_info

        # Call before_send
        result = before_send(event, hint)

        # Should return the event (not filtered)
        assert result == event


def test_before_send_is_configured(mock_settings):
    """Sentry should be initialized with before_send hook."""
    from shotgun.sentry_telemetry import setup_sentry_observability

    with (
        patch("sentry_sdk.is_initialized", return_value=False),
        patch("sentry_sdk.init") as mock_init,
        patch("sentry_sdk.set_user"),
    ):
        # Setup Sentry
        setup_sentry_observability()

        # Verify sentry_sdk.init was called with before_send
        mock_init.assert_called_once()
        init_call = mock_init.call_args
        assert "before_send" in init_call.kwargs
        assert callable(init_call.kwargs["before_send"])
