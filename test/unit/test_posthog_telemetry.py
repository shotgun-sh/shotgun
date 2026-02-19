"""Tests for PostHog telemetry module."""

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
        with patch.object(posthog_telemetry.settings.telemetry, "posthog_api_key", ""):
            # PostHog should not initialize without API key
            result = posthog_telemetry.setup_posthog_observability()
            assert result is False
    finally:
        posthog_telemetry._posthog_client = original_client


def test_setup_posthog_with_build_constants():
    """Test setup with API key from settings (via build constants or env vars)."""
    # Reset the global client and instance ID
    original_client = posthog_telemetry._posthog_client
    original_instance_id = posthog_telemetry._shotgun_instance_id
    original_user_context = posthog_telemetry._user_context.copy()
    posthog_telemetry._posthog_client = None
    posthog_telemetry._shotgun_instance_id = None
    posthog_telemetry._user_context = {}

    try:
        with patch("shotgun.posthog_telemetry.settings") as mock_settings:
            # Mock the settings to return an API key
            mock_settings.telemetry.posthog_api_key = "test_api_key"

            with patch("shotgun.posthog_telemetry.Posthog") as mock_posthog_class:
                mock_posthog_instance = MagicMock()
                mock_posthog_class.return_value = mock_posthog_instance

                with patch(
                    "shotgun.posthog_telemetry.get_config_manager"
                ) as mock_get_config:
                    # Mock config manager
                    mock_config_manager = MagicMock()
                    mock_config_manager.get_shotgun_instance_id = AsyncMock(
                        return_value="test-shotgun-instance-id"
                    )

                    # Mock the loaded config
                    mock_loaded_config = MagicMock()
                    mock_loaded_config.shotgun.has_valid_account = True
                    mock_loaded_config.selected_model = MagicMock(value="claude-sonnet")
                    mock_config_manager.load = AsyncMock(
                        return_value=mock_loaded_config
                    )

                    mock_get_config.return_value = mock_config_manager

                    result = posthog_telemetry.setup_posthog_observability()

                    assert result is True
                    # The global client should be set to the Posthog instance
                    assert posthog_telemetry._posthog_client is not None

                    # Verify Posthog class was instantiated with correct args
                    mock_posthog_class.assert_called_once()
                    call_kwargs = mock_posthog_class.call_args[1]
                    assert call_kwargs["project_api_key"] == "test_api_key"
                    assert call_kwargs["host"] == "https://us.i.posthog.com"

                    # Verify capture was called with $identify event
                    mock_posthog_instance.capture.assert_called_once()
    finally:
        posthog_telemetry._posthog_client = original_client
        posthog_telemetry._shotgun_instance_id = original_instance_id
        posthog_telemetry._user_context = original_user_context


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
    original_instance_id = posthog_telemetry._shotgun_instance_id
    posthog_telemetry._posthog_client = mock_client
    posthog_telemetry._shotgun_instance_id = "test-shotgun-instance-id"

    try:
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
        posthog_telemetry._shotgun_instance_id = original_instance_id


def test_track_event_dev_version():
    """Test that dev versions are marked with development environment."""
    mock_client = MagicMock()
    original_client = posthog_telemetry._posthog_client
    original_instance_id = posthog_telemetry._shotgun_instance_id
    posthog_telemetry._posthog_client = mock_client
    posthog_telemetry._shotgun_instance_id = "test-shotgun-instance-id"

    try:
        with patch("shotgun.posthog_telemetry.__version__", "1.0.0.dev1"):
            posthog_telemetry.track_event("test_event", None)

            mock_client.capture.assert_called_once()
            call_args = mock_client.capture.call_args[1]
            assert call_args["properties"]["environment"] == "development"
    finally:
        posthog_telemetry._posthog_client = original_client
        posthog_telemetry._shotgun_instance_id = original_instance_id


def test_track_event_exception_handling():
    """Test that track_event handles exceptions gracefully."""
    mock_client = MagicMock()
    mock_client.capture.side_effect = Exception("Network error")
    original_client = posthog_telemetry._posthog_client
    original_instance_id = posthog_telemetry._shotgun_instance_id
    posthog_telemetry._posthog_client = mock_client
    posthog_telemetry._shotgun_instance_id = "test-shotgun-instance-id"

    try:
        # Should not raise exception
        posthog_telemetry.track_event("test_event", {})
    finally:
        posthog_telemetry._posthog_client = original_client
        posthog_telemetry._shotgun_instance_id = original_instance_id


def test_capture_exception_not_initialized():
    """Test that capture_exception does nothing when PostHog is not initialized."""
    original_client = posthog_telemetry._posthog_client
    posthog_telemetry._posthog_client = None

    try:
        # Should not raise any exception
        posthog_telemetry.capture_exception(ValueError("test error"))
    finally:
        posthog_telemetry._posthog_client = original_client


def test_capture_exception_filters_user_actionable_errors():
    """Test that capture_exception filters out UserActionableError exceptions."""
    from shotgun.exceptions import UserActionableError

    mock_client = MagicMock()
    original_client = posthog_telemetry._posthog_client
    original_instance_id = posthog_telemetry._shotgun_instance_id
    posthog_telemetry._posthog_client = mock_client
    posthog_telemetry._shotgun_instance_id = "test-shotgun-instance-id"

    try:
        # UserActionableError should be filtered out
        posthog_telemetry.capture_exception(UserActionableError("test error"))

        # capture_exception should NOT have been called
        mock_client.capture_exception.assert_not_called()
    finally:
        posthog_telemetry._posthog_client = original_client
        posthog_telemetry._shotgun_instance_id = original_instance_id


def test_capture_exception_sends_regular_exceptions():
    """Test that capture_exception sends regular exceptions using the SDK method."""
    mock_client = MagicMock()
    original_client = posthog_telemetry._posthog_client
    original_instance_id = posthog_telemetry._shotgun_instance_id
    posthog_telemetry._posthog_client = mock_client
    posthog_telemetry._shotgun_instance_id = "test-shotgun-instance-id"

    try:
        with patch("shotgun.posthog_telemetry.__version__", "1.0.0"):
            test_exception = ValueError("test error")
            posthog_telemetry.capture_exception(
                test_exception, properties={"extra": "data"}
            )

            # Now uses SDK's capture_exception method
            mock_client.capture_exception.assert_called_once()
            call_args = mock_client.capture_exception.call_args
            # First positional arg is the exception
            assert call_args[0][0] is test_exception
            # Check keyword args
            assert call_args[1]["distinct_id"] == "test-shotgun-instance-id"
            assert call_args[1]["properties"]["version"] == "1.0.0"
            assert call_args[1]["properties"]["extra"] == "data"
    finally:
        posthog_telemetry._posthog_client = original_client
        posthog_telemetry._shotgun_instance_id = original_instance_id


def test_flush_not_initialized():
    """Test flush when PostHog is not initialized."""
    original_client = posthog_telemetry._posthog_client
    posthog_telemetry._posthog_client = None

    try:
        # Should not raise any exception
        posthog_telemetry.flush()
    finally:
        posthog_telemetry._posthog_client = original_client


def test_flush_initialized():
    """Test flush when PostHog is initialized."""
    mock_client = MagicMock()
    original_client = posthog_telemetry._posthog_client
    posthog_telemetry._posthog_client = mock_client

    try:
        posthog_telemetry.flush()
        mock_client.flush.assert_called_once()
    finally:
        posthog_telemetry._posthog_client = original_client


def test_flush_exception_handling():
    """Test flush handles exceptions gracefully."""
    mock_client = MagicMock()
    mock_client.flush.side_effect = Exception("Flush error")
    original_client = posthog_telemetry._posthog_client
    posthog_telemetry._posthog_client = mock_client

    try:
        # Should not raise exception
        posthog_telemetry.flush()
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
def test_submit_feedback_survey_bug_report(mock_get_config_manager, mock_track_event):
    """Test submitting a bug report feedback."""
    mock_config_manager = MagicMock()
    mock_config = MagicMock()
    mock_config.selected_model.value = "gpt-5"
    mock_config.config_version = "1.0.0"
    mock_config_manager.load = AsyncMock(return_value=mock_config)
    mock_get_config_manager.return_value = mock_config_manager

    original_client = posthog_telemetry._posthog_client
    posthog_telemetry._posthog_client = MagicMock()

    try:
        feedback = Feedback(
            kind=FeedbackKind.BUG,
            description="Application crashes on startup",
            shotgun_instance_id="test-shotgun-instance-id",
        )

        posthog_telemetry.submit_feedback_survey(feedback)

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

        # Verify config metadata
        assert properties["selected_model"] == "gpt-5"
        assert properties["config_version"] == "1.0.0"

        # Verify conversation messages are NOT sent (PII protection)
        assert "last_10_messages" not in properties
    finally:
        posthog_telemetry._posthog_client = original_client


@patch("shotgun.posthog_telemetry.track_event")
@patch("shotgun.posthog_telemetry.get_config_manager")
def test_submit_feedback_survey_feature_request(
    mock_get_config_manager, mock_track_event
):
    """Test submitting a feature request feedback."""
    mock_config_manager = MagicMock()
    mock_config = MagicMock()
    mock_config.selected_model.value = "claude-opus-4-1"
    mock_config.config_version = "2.0.0"
    mock_config_manager.load = AsyncMock(return_value=mock_config)
    mock_get_config_manager.return_value = mock_config_manager

    original_client = posthog_telemetry._posthog_client
    posthog_telemetry._posthog_client = MagicMock()

    try:
        feedback = Feedback(
            kind=FeedbackKind.FEATURE,
            description="Add support for dark mode",
            shotgun_instance_id="test-shotgun-instance-id",
        )

        posthog_telemetry.submit_feedback_survey(feedback)

        mock_track_event.assert_called_once()
        call_args = mock_track_event.call_args
        properties = call_args[1]["properties"]

        assert (
            properties["$survey_response_aaa5fcc3-88ba-4c24-bcf5-1481fd5efc2b"]
            == FeedbackKind.FEATURE
        )

        # Verify conversation messages are NOT sent (PII protection)
        assert "last_10_messages" not in properties
    finally:
        posthog_telemetry._posthog_client = original_client


@patch("shotgun.posthog_telemetry.track_event")
@patch("shotgun.posthog_telemetry.get_config_manager")
def test_submit_feedback_survey_other_feedback(
    mock_get_config_manager, mock_track_event
):
    """Test submitting other type of feedback."""
    mock_config_manager = MagicMock()
    mock_config = MagicMock()
    mock_config.selected_model.value = "gemini-3-pro-preview"
    mock_config.config_version = "1.5.0"
    mock_config_manager.load = AsyncMock(return_value=mock_config)
    mock_get_config_manager.return_value = mock_config_manager

    original_client = posthog_telemetry._posthog_client
    posthog_telemetry._posthog_client = MagicMock()

    try:
        feedback = Feedback(
            kind=FeedbackKind.OTHER,
            description="Great tool, thanks!",
            shotgun_instance_id="test-shotgun-instance-id",
        )

        posthog_telemetry.submit_feedback_survey(feedback)

        mock_track_event.assert_called_once()
        call_args = mock_track_event.call_args
        properties = call_args[1]["properties"]

        assert (
            properties["$survey_response_aaa5fcc3-88ba-4c24-bcf5-1481fd5efc2b"]
            == FeedbackKind.OTHER
        )

        # Verify conversation messages are NOT sent (PII protection)
        assert "last_10_messages" not in properties
    finally:
        posthog_telemetry._posthog_client = original_client
