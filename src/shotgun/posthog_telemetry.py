"""PostHog analytics setup for Shotgun."""

from enum import StrEnum
from typing import Any

from posthog import Posthog
from pydantic import BaseModel

from shotgun import __version__
from shotgun.agents.config import get_config_manager
from shotgun.agents.conversation import ConversationManager
from shotgun.exceptions import UserActionableError
from shotgun.logging_config import get_early_logger
from shotgun.settings import settings

# Use early logger to prevent automatic StreamHandler creation
logger = get_early_logger(__name__)

# Global PostHog client instance
_posthog_client: Posthog | None = None

# Cache the shotgun instance ID to avoid async calls during event tracking
_shotgun_instance_id: str | None = None


def setup_posthog_observability() -> bool:
    """Set up PostHog analytics for usage tracking and exception capture.

    Returns:
        True if PostHog was successfully set up, False otherwise
    """
    global _posthog_client, _shotgun_instance_id

    try:
        # Check if PostHog is already initialized
        if _posthog_client is not None:
            logger.debug("PostHog is already initialized, skipping")
            return True

        # Get API key from settings (handles build constants + env vars automatically)
        api_key = settings.telemetry.posthog_api_key

        # If no API key is available, skip PostHog initialization
        if not api_key:
            logger.debug("No PostHog API key available, skipping initialization")
            return False

        logger.debug("Using PostHog API key from settings")

        # Determine environment based on version
        # Dev versions contain "dev", "rc", "alpha", or "beta"
        if any(marker in __version__ for marker in ["dev", "rc", "alpha", "beta"]):
            environment = "development"
        else:
            environment = "production"

        def on_error(e: Exception, batch: list[dict[str, Any]]) -> None:
            """Handle PostHog errors."""
            logger.warning("PostHog error: %s", e)

        # Initialize PostHog client with exception autocapture
        _posthog_client = Posthog(
            project_api_key=api_key,
            host="https://us.i.posthog.com",
            enable_exception_autocapture=True,
            on_error=on_error,
        )

        # Cache the shotgun instance ID for later use (avoids async issues)
        try:
            import asyncio

            config_manager = get_config_manager()
            _shotgun_instance_id = asyncio.run(config_manager.get_shotgun_instance_id())

            # Set user properties for tracking
            _posthog_client.capture(
                distinct_id=_shotgun_instance_id,
                event="$identify",
                properties={
                    "$set": {
                        "app_version": __version__,
                        "environment": environment,
                    },
                },
            )

            logger.debug(
                "PostHog initialized with shotgun instance ID: %s",
                _shotgun_instance_id,
            )
        except Exception as e:
            logger.warning("Failed to load shotgun instance ID: %s", e)
            # Continue anyway - we'll try to get it during event tracking

        logger.debug(
            "PostHog analytics configured successfully (environment: %s, version: %s)",
            environment,
            __version__,
        )
        return True

    except Exception as e:
        logger.warning("Failed to setup PostHog analytics: %s", e)
        return False


def track_event(event_name: str, properties: dict[str, Any] | None = None) -> None:
    """Track an event in PostHog.

    Args:
        event_name: Name of the event to track
        properties: Optional properties to include with the event
    """
    global _posthog_client, _shotgun_instance_id

    if _posthog_client is None:
        logger.debug("PostHog not initialized, skipping event: %s", event_name)
        return

    try:
        # Use cached instance ID (loaded during setup)
        if _shotgun_instance_id is None:
            logger.warning(
                "Shotgun instance ID not available, skipping event: %s", event_name
            )
            return

        # Add version and environment to properties
        if properties is None:
            properties = {}
        properties["version"] = __version__

        # Determine environment
        if any(marker in __version__ for marker in ["dev", "rc", "alpha", "beta"]):
            properties["environment"] = "development"
        else:
            properties["environment"] = "production"

        # Track the event using PostHog's capture method
        _posthog_client.capture(
            distinct_id=_shotgun_instance_id, event=event_name, properties=properties
        )
        logger.debug("Tracked PostHog event: %s", event_name)
    except Exception as e:
        logger.warning("Failed to track PostHog event '%s': %s", event_name, e)


def capture_exception(
    exception: Exception,
    properties: dict[str, Any] | None = None,
) -> None:
    """Manually capture an exception in PostHog.

    This is used for reporting exceptions that should be tracked but may not
    be caught by automatic exception capture.

    Note: UserActionableError exceptions are filtered out as they represent
    expected user conditions, not bugs.

    Args:
        exception: The exception to capture
        properties: Optional additional properties
    """
    global _posthog_client, _shotgun_instance_id

    if _posthog_client is None:
        logger.debug("PostHog not initialized, skipping exception capture")
        return

    # Filter out user-actionable errors - these are expected conditions
    if isinstance(exception, UserActionableError):
        logger.debug(
            "Skipping UserActionableError in PostHog exception capture: %s",
            type(exception).__name__,
        )
        return

    try:
        if _shotgun_instance_id is None:
            logger.warning(
                "Shotgun instance ID not available, skipping exception capture"
            )
            return

        # Build exception properties
        event_properties: dict[str, Any] = {
            "version": __version__,
            "$exception_type": type(exception).__name__,
            "$exception_message": str(exception),
        }

        # Determine environment
        if any(marker in __version__ for marker in ["dev", "rc", "alpha", "beta"]):
            event_properties["environment"] = "development"
        else:
            event_properties["environment"] = "production"

        # Add custom properties
        if properties:
            event_properties.update(properties)

        # Track as exception event
        _posthog_client.capture(
            distinct_id=_shotgun_instance_id,
            event="$exception",
            properties=event_properties,
        )
        logger.debug("Captured exception in PostHog: %s", type(exception).__name__)
    except Exception as e:
        logger.warning("Failed to capture exception in PostHog: %s", e)


def shutdown() -> None:
    """Shutdown PostHog client and flush any pending events."""
    global _posthog_client

    if _posthog_client is not None:
        try:
            _posthog_client.shutdown()  # type: ignore[no-untyped-call]
            logger.debug("PostHog client shutdown successfully")
        except Exception as e:
            logger.warning("Error shutting down PostHog: %s", e)
        finally:
            _posthog_client = None


class FeedbackKind(StrEnum):
    BUG = "bug"
    FEATURE = "feature"
    OTHER = "other"


class Feedback(BaseModel):
    kind: FeedbackKind
    description: str
    shotgun_instance_id: str


SURVEY_ID = "01999f81-9486-0000-4fa6-9632959f92f3"
Q_KIND_ID = "aaa5fcc3-88ba-4c24-bcf5-1481fd5efc2b"
Q_DESCRIPTION_ID = "a0ed6283-5d4b-452c-9160-6768d879db8a"


def submit_feedback_survey(feedback: Feedback) -> None:
    global _posthog_client
    if _posthog_client is None:
        logger.debug("PostHog not initialized, skipping feedback survey")
        return

    import asyncio

    config_manager = get_config_manager()
    config = asyncio.run(config_manager.load())
    conversation_manager = ConversationManager()
    conversation = None
    try:
        conversation = asyncio.run(conversation_manager.load())
    except Exception as e:
        logger.debug(f"Failed to load conversation history: {e}")
    last_10_messages = []
    if conversation is not None:
        last_10_messages = conversation.get_agent_messages()[:10]

    track_event(
        "survey sent",
        properties={
            "$survey_id": SURVEY_ID,
            "$survey_questions": [
                {"id": Q_KIND_ID, "question": "Feedback type"},
                {"id": Q_DESCRIPTION_ID, "question": "Feedback description"},
            ],
            f"$survey_response_{Q_KIND_ID}": feedback.kind,
            f"$survey_response_{Q_DESCRIPTION_ID}": feedback.description,
            "selected_model": config.selected_model.value
            if config.selected_model
            else None,
            "config_version": config.config_version,
            "last_10_messages": last_10_messages,  # last 10 messages
        },
    )
