"""PostHog analytics setup for Shotgun."""

from enum import StrEnum
from typing import Any

import posthog
from pydantic import BaseModel

from shotgun import __version__
from shotgun.agents.config import get_config_manager
from shotgun.agents.conversation_manager import ConversationManager
from shotgun.logging_config import get_early_logger
from shotgun.settings import settings

# Use early logger to prevent automatic StreamHandler creation
logger = get_early_logger(__name__)

# Global PostHog client instance
_posthog_client = None


def setup_posthog_observability() -> bool:
    """Set up PostHog analytics for usage tracking.

    Returns:
        True if PostHog was successfully set up, False otherwise
    """
    global _posthog_client

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

        # Initialize PostHog client
        posthog.api_key = api_key
        posthog.host = "https://us.i.posthog.com"  # Use US cloud instance

        # Store the client for later use
        _posthog_client = posthog

        # Set user context with anonymous shotgun instance ID from config
        try:
            import asyncio

            config_manager = get_config_manager()
            shotgun_instance_id = asyncio.run(config_manager.get_shotgun_instance_id())

            # Identify the user in PostHog
            posthog.identify(  # type: ignore[attr-defined]
                distinct_id=shotgun_instance_id,
                properties={
                    "version": __version__,
                    "environment": environment,
                },
            )

            # Set default properties for all events
            posthog.disabled = False
            posthog.personal_api_key = None  # Not needed for event tracking

            logger.debug(
                "PostHog user identified with anonymous ID: %s", shotgun_instance_id
            )
        except Exception as e:
            logger.warning("Failed to set user context: %s", e)

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
    global _posthog_client

    if _posthog_client is None:
        logger.debug("PostHog not initialized, skipping event: %s", event_name)
        return

    try:
        import asyncio

        # Get shotgun instance ID for tracking
        config_manager = get_config_manager()
        shotgun_instance_id = asyncio.run(config_manager.get_shotgun_instance_id())

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
            distinct_id=shotgun_instance_id, event=event_name, properties=properties
        )
        logger.debug("Tracked PostHog event: %s", event_name)
    except Exception as e:
        logger.warning("Failed to track PostHog event '%s': %s", event_name, e)


def shutdown() -> None:
    """Shutdown PostHog client and flush any pending events."""
    global _posthog_client

    if _posthog_client is not None:
        try:
            _posthog_client.shutdown()
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
