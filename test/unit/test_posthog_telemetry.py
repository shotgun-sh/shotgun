"""Tests for PostHog telemetry module."""

import os
from unittest.mock import MagicMock, patch

from shotgun import posthog_telemetry


def test_setup_posthog_already_initialized():
    """Test that setup returns True if already initialized."""
    # Set the global client to simulate already initialized
    original_client = posthog_telemetry._posthog_client
    posthog_telemetry._posthog_client = MagicMock()

    try:
        result = posthog_telemetry.setup_posthog_observability()
        assert result is True
    finally:
        # Reset the global client
        posthog_telemetry._posthog_client = original_client


def test_setup_posthog_no_api_key():
    """Test that setup returns False when no API key is configured."""
    # Reset the global client
    original_client = posthog_telemetry._posthog_client
    posthog_telemetry._posthog_client = None

    try:
        with patch.dict(os.environ, {}, clear=True):
            with patch("shotgun.build_constants.POSTHOG_API_KEY", ""):
                result = posthog_telemetry.setup_posthog_observability()
                assert result is False
    finally:
        posthog_telemetry._posthog_client = original_client


def test_setup_posthog_with_build_constants():
    """Test setup with API key from build constants."""
    # Reset the global client
    original_client = posthog_telemetry._posthog_client
    posthog_telemetry._posthog_client = None

    try:
        with patch("posthog.api_key", None):
            with patch("posthog.host", None):
                with patch("posthog.disabled", True):
                    with patch(
                        "shotgun.build_constants.POSTHOG_API_KEY", "test_api_key"
                    ):
                        with patch(
                            "shotgun.agents.config.get_config_manager"
                        ) as mock_get_config:
                            mock_config = MagicMock()
                            mock_config.get_user_id.return_value = "test-user-id"
                            mock_get_config.return_value = mock_config

                            result = posthog_telemetry.setup_posthog_observability()

                            assert result is True
                            # The global client should be set to posthog module
                            assert posthog_telemetry._posthog_client is not None
    finally:
        posthog_telemetry._posthog_client = original_client


def test_setup_posthog_with_env_vars():
    """Test setup with API key from environment variables."""
    # Reset the global client
    original_client = posthog_telemetry._posthog_client
    posthog_telemetry._posthog_client = None

    try:
        with patch("posthog.api_key", None):
            with patch("posthog.host", None):
                with patch("posthog.disabled", True):
                    with patch.dict(os.environ, {"POSTHOG_API_KEY": "env_api_key"}):
                        with patch("shotgun.build_constants.POSTHOG_API_KEY", ""):
                            with patch(
                                "shotgun.agents.config.get_config_manager"
                            ) as mock_get_config:
                                mock_config = MagicMock()
                                mock_config.get_user_id.return_value = "test-user-id"
                                mock_get_config.return_value = mock_config

                                result = posthog_telemetry.setup_posthog_observability()

                                assert result is True
                                assert posthog_telemetry._posthog_client is not None
    finally:
        posthog_telemetry._posthog_client = original_client


def test_setup_posthog_import_error():
    """Test setup handles ImportError gracefully."""
    original_client = posthog_telemetry._posthog_client
    posthog_telemetry._posthog_client = None

    try:
        # Temporarily hide the posthog module
        import sys

        posthog_module = sys.modules.get("posthog")
        if "posthog" in sys.modules:
            del sys.modules["posthog"]

        # Now importing posthog should fail
        with patch.dict("sys.modules", {"posthog": None}):
            result = posthog_telemetry.setup_posthog_observability()
            assert result is False

        # Restore the module if it existed
        if posthog_module:
            sys.modules["posthog"] = posthog_module
    finally:
        posthog_telemetry._posthog_client = original_client


def test_track_event_not_initialized():
    """Test that track_event does nothing when PostHog is not initialized."""
    original_client = posthog_telemetry._posthog_client
    posthog_telemetry._posthog_client = None

    try:
        # Should not raise any exception
        posthog_telemetry.track_event("test_event", {"key": "value"})
    finally:
        posthog_telemetry._posthog_client = original_client


def test_track_event_initialized():
    """Test tracking events when PostHog is initialized."""
    mock_client = MagicMock()
    original_client = posthog_telemetry._posthog_client
    posthog_telemetry._posthog_client = mock_client

    try:
        with patch("shotgun.agents.config.get_config_manager") as mock_get_config:
            mock_config = MagicMock()
            mock_config.get_user_id.return_value = "test-user-id"
            mock_get_config.return_value = mock_config

            with patch("shotgun.__version__", "1.0.0"):
                posthog_telemetry.track_event("test_event", {"custom": "property"})

                mock_client.capture.assert_called_once_with(
                    distinct_id="test-user-id",
                    event="test_event",
                    properties={
                        "custom": "property",
                        "version": "1.0.0",
                        "environment": "production",
                    },
                )
    finally:
        posthog_telemetry._posthog_client = original_client


def test_track_event_dev_version():
    """Test that dev versions are marked with development environment."""
    mock_client = MagicMock()
    original_client = posthog_telemetry._posthog_client
    posthog_telemetry._posthog_client = mock_client

    try:
        with patch("shotgun.agents.config.get_config_manager") as mock_get_config:
            mock_config = MagicMock()
            mock_config.get_user_id.return_value = "test-user-id"
            mock_get_config.return_value = mock_config

            with patch("shotgun.__version__", "1.0.0.dev1"):
                posthog_telemetry.track_event("test_event", None)

                mock_client.capture.assert_called_once()
                call_args = mock_client.capture.call_args[1]
                assert call_args["properties"]["environment"] == "development"
    finally:
        posthog_telemetry._posthog_client = original_client


def test_track_event_exception_handling():
    """Test that track_event handles exceptions gracefully."""
    mock_client = MagicMock()
    mock_client.capture.side_effect = Exception("Network error")
    original_client = posthog_telemetry._posthog_client
    posthog_telemetry._posthog_client = mock_client

    try:
        with patch(
            "shotgun.agents.config.get_config_manager",
            side_effect=Exception("Config error"),
        ):
            # Should not raise exception
            posthog_telemetry.track_event("test_event", {})
    finally:
        posthog_telemetry._posthog_client = original_client


def test_shutdown_not_initialized():
    """Test shutdown when PostHog is not initialized."""
    original_client = posthog_telemetry._posthog_client
    posthog_telemetry._posthog_client = None

    try:
        # Should not raise any exception
        posthog_telemetry.shutdown()
    finally:
        posthog_telemetry._posthog_client = original_client


def test_shutdown_initialized():
    """Test shutdown when PostHog is initialized."""
    mock_client = MagicMock()
    original_client = posthog_telemetry._posthog_client
    posthog_telemetry._posthog_client = mock_client

    try:
        posthog_telemetry.shutdown()
        mock_client.shutdown.assert_called_once()
        assert posthog_telemetry._posthog_client is None
    finally:
        posthog_telemetry._posthog_client = original_client


def test_shutdown_exception_handling():
    """Test shutdown handles exceptions gracefully."""
    mock_client = MagicMock()
    mock_client.shutdown.side_effect = Exception("Shutdown error")
    original_client = posthog_telemetry._posthog_client
    posthog_telemetry._posthog_client = mock_client

    try:
        # Should not raise exception
        posthog_telemetry.shutdown()
        assert posthog_telemetry._posthog_client is None
    finally:
        posthog_telemetry._posthog_client = original_client
