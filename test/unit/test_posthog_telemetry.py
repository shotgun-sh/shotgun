"""Tests for PostHog telemetry module."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

from shotgun import posthog_telemetry
from shotgun.posthog_telemetry import Feedback, FeedbackKind


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
    """Test that setup returns False when no API key is available."""
    # Reset the global client
    original_client = posthog_telemetry._posthog_client
    posthog_telemetry._posthog_client = None

    try:
        with patch.dict(os.environ, {}, clear=True):
            with patch("shotgun.build_constants.POSTHOG_API_KEY", ""):
                # PostHog should not initialize without API key
                result = posthog_telemetry.setup_posthog_observability()
                assert result is False
    finally:
        posthog_telemetry._posthog_client = original_client


def test_setup_posthog_with_build_constants():
    """Test setup with API key from settings (via build constants or env vars)."""
    # Reset the global client
    original_client = posthog_telemetry._posthog_client
    posthog_telemetry._posthog_client = None

    try:
        with patch("posthog.api_key", None):
            with patch("posthog.host", None):
                with patch("posthog.disabled", True):
                    with patch("shotgun.posthog_telemetry.settings") as mock_settings:
                        # Mock the settings to return an API key
                        mock_settings.telemetry.posthog_api_key = "test_api_key"

                        with patch(
                            "shotgun.posthog_telemetry.get_config_manager"
                        ) as mock_get_config:
                            mock_config = MagicMock()
                            mock_config.get_shotgun_instance_id = AsyncMock(
                                return_value="test-shotgun-instance-id"
                            )
                            mock_get_config.return_value = mock_config

                            result = posthog_telemetry.setup_posthog_observability()

                            assert result is True
                            # The global client should be set to posthog module
                            assert posthog_telemetry._posthog_client is not None
    finally:
        posthog_telemetry._posthog_client = original_client


def test_setup_posthog_with_env_vars():
    """Test setup with API key from environment variables via settings."""
    # Reset the global client
    original_client = posthog_telemetry._posthog_client
    posthog_telemetry._posthog_client = None

    try:
        with patch("posthog.api_key", None):
            with patch("posthog.host", None):
                with patch("posthog.disabled", True):
                    with patch("shotgun.posthog_telemetry.settings") as mock_settings:
                        # Mock the settings to return an API key from env
                        mock_settings.telemetry.posthog_api_key = "env_api_key"

                        with patch(
                            "shotgun.posthog_telemetry.get_config_manager"
                        ) as mock_get_config:
                            mock_config = MagicMock()
                            mock_config.get_shotgun_instance_id = AsyncMock(
                                return_value="test-shotgun-instance-id"
                            )
                            mock_get_config.return_value = mock_config

                            result = posthog_telemetry.setup_posthog_observability()

                            assert result is True
                            assert posthog_telemetry._posthog_client is not None
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
        with patch("shotgun.posthog_telemetry.get_config_manager") as mock_get_config:
            mock_config = MagicMock()
            mock_config.get_shotgun_instance_id = AsyncMock(
                return_value="test-shotgun-instance-id"
            )
            mock_get_config.return_value = mock_config

            with patch("shotgun.posthog_telemetry.__version__", "1.0.0"):
                posthog_telemetry.track_event("test_event", {"custom": "property"})

                mock_client.capture.assert_called_once_with(
                    distinct_id="test-shotgun-instance-id",
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
        with patch("shotgun.posthog_telemetry.get_config_manager") as mock_get_config:
            mock_config = MagicMock()
            mock_config.get_shotgun_instance_id = AsyncMock(
                return_value="test-shotgun-instance-id"
            )
            mock_get_config.return_value = mock_config

            with patch("shotgun.posthog_telemetry.__version__", "1.0.0.dev1"):
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
            "shotgun.posthog_telemetry.get_config_manager",
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


def test_submit_feedback_survey_not_initialized():
    """Test that submit_feedback_survey handles uninitialized PostHog client."""
    original_client = posthog_telemetry._posthog_client
    posthog_telemetry._posthog_client = None

    try:
        feedback = Feedback(
            kind=FeedbackKind.BUG,
            description="Test bug report",
            shotgun_instance_id="test-shotgun-instance-id",
        )

        # Should not raise an exception
        posthog_telemetry.submit_feedback_survey(feedback)
    finally:
        posthog_telemetry._posthog_client = original_client


@patch("shotgun.posthog_telemetry.track_event")
@patch("shotgun.posthog_telemetry.get_config_manager")
@patch("shotgun.posthog_telemetry.ConversationManager")
def test_submit_feedback_survey_bug_report(
    mock_conversation_manager_class, mock_get_config_manager, mock_track_event
):
    """Test submitting a bug report feedback."""
    # Setup mocks
    mock_config_manager = MagicMock()
    mock_config = MagicMock()
    mock_config.selected_model.value = "gpt-5"
    mock_config.config_version = "1.0.0"
    mock_config_manager.load = AsyncMock(return_value=mock_config)
    mock_get_config_manager.return_value = mock_config_manager

    mock_conversation_manager = MagicMock()
    mock_conversation = MagicMock()
    mock_conversation.get_agent_messages.return_value = [
        {"role": "user", "content": "Test message 1"},
        {"role": "assistant", "content": "Test response 1"},
    ]
    mock_conversation_manager.load = AsyncMock(return_value=mock_conversation)
    mock_conversation_manager_class.return_value = mock_conversation_manager

    # Set up a mock PostHog client
    original_client = posthog_telemetry._posthog_client
    mock_posthog_client = MagicMock()
    posthog_telemetry._posthog_client = mock_posthog_client

    try:
        feedback = Feedback(
            kind=FeedbackKind.BUG,
            description="Application crashes on startup",
            shotgun_instance_id="test-shotgun-instance-id",
        )

        posthog_telemetry.submit_feedback_survey(feedback)

        # Verify track_event was called with correct parameters
        mock_track_event.assert_called_once()
        call_args = mock_track_event.call_args

        assert call_args[0][0] == "survey sent"
        properties = call_args[1]["properties"]

        # Verify survey structure
        assert "$survey_id" in properties
        assert "$survey_questions" in properties
        assert len(properties["$survey_questions"]) == 2

        # Verify feedback content
        assert (
            properties["$survey_response_aaa5fcc3-88ba-4c24-bcf5-1481fd5efc2b"]
            == FeedbackKind.BUG
        )
        assert (
            properties["$survey_response_a0ed6283-5d4b-452c-9160-6768d879db8a"]
            == "Application crashes on startup"
        )

        # Verify config metadata
        assert properties["selected_model"] == "gpt-5"
        assert properties["config_version"] == "1.0.0"

        # Verify conversation messages
        assert "last_10_messages" in properties
        assert len(properties["last_10_messages"]) == 2
    finally:
        posthog_telemetry._posthog_client = original_client


@patch("shotgun.posthog_telemetry.track_event")
@patch("shotgun.posthog_telemetry.get_config_manager")
@patch("shotgun.posthog_telemetry.ConversationManager")
def test_submit_feedback_survey_feature_request(
    mock_conversation_manager_class, mock_get_config_manager, mock_track_event
):
    """Test submitting a feature request feedback."""
    # Setup mocks
    mock_config_manager = MagicMock()
    mock_config = MagicMock()
    mock_config.selected_model.value = "claude-opus-4-1"
    mock_config.config_version = "2.0.0"
    mock_config_manager.load = AsyncMock(return_value=mock_config)
    mock_get_config_manager.return_value = mock_config_manager

    mock_conversation_manager = MagicMock()
    mock_conversation_manager.load = AsyncMock(return_value=None)
    mock_conversation_manager_class.return_value = mock_conversation_manager

    # Set up a mock PostHog client
    original_client = posthog_telemetry._posthog_client
    mock_posthog_client = MagicMock()
    posthog_telemetry._posthog_client = mock_posthog_client

    try:
        feedback = Feedback(
            kind=FeedbackKind.FEATURE,
            description="Add support for dark mode",
            shotgun_instance_id="test-shotgun-instance-id",
        )

        posthog_telemetry.submit_feedback_survey(feedback)

        # Verify track_event was called
        mock_track_event.assert_called_once()
        call_args = mock_track_event.call_args
        properties = call_args[1]["properties"]

        # Verify feature request content
        assert (
            properties["$survey_response_aaa5fcc3-88ba-4c24-bcf5-1481fd5efc2b"]
            == FeedbackKind.FEATURE
        )
        assert (
            properties["$survey_response_a0ed6283-5d4b-452c-9160-6768d879db8a"]
            == "Add support for dark mode"
        )

        # Verify empty conversation is handled
        assert properties["last_10_messages"] == []
    finally:
        posthog_telemetry._posthog_client = original_client


@patch("shotgun.posthog_telemetry.track_event")
@patch("shotgun.posthog_telemetry.get_config_manager")
@patch("shotgun.posthog_telemetry.ConversationManager")
def test_submit_feedback_survey_other_feedback(
    mock_conversation_manager_class, mock_get_config_manager, mock_track_event
):
    """Test submitting other type of feedback."""
    # Setup mocks
    mock_config_manager = MagicMock()
    mock_config = MagicMock()
    mock_config.selected_model.value = "gemini-2.5-pro"
    mock_config.config_version = "1.5.0"
    mock_config_manager.load = AsyncMock(return_value=mock_config)
    mock_get_config_manager.return_value = mock_config_manager

    mock_conversation_manager = MagicMock()
    mock_conversation = MagicMock()
    # Simulate more than 10 messages
    mock_conversation.get_agent_messages.return_value = [
        {"role": "user", "content": f"Message {i}"} for i in range(15)
    ]
    mock_conversation_manager.load = AsyncMock(return_value=mock_conversation)
    mock_conversation_manager_class.return_value = mock_conversation_manager

    # Set up a mock PostHog client
    original_client = posthog_telemetry._posthog_client
    mock_posthog_client = MagicMock()
    posthog_telemetry._posthog_client = mock_posthog_client

    try:
        feedback = Feedback(
            kind=FeedbackKind.OTHER,
            description="Great tool, thanks!",
            shotgun_instance_id="test-shotgun-instance-id",
        )

        posthog_telemetry.submit_feedback_survey(feedback)

        # Verify track_event was called
        mock_track_event.assert_called_once()
        call_args = mock_track_event.call_args
        properties = call_args[1]["properties"]

        # Verify other feedback content
        assert (
            properties["$survey_response_aaa5fcc3-88ba-4c24-bcf5-1481fd5efc2b"]
            == FeedbackKind.OTHER
        )
        assert (
            properties["$survey_response_a0ed6283-5d4b-452c-9160-6768d879db8a"]
            == "Great tool, thanks!"
        )

        # Verify only first 10 messages are included
        assert len(properties["last_10_messages"]) == 10
    finally:
        posthog_telemetry._posthog_client = original_client
