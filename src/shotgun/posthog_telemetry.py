"""PostHog analytics setup for Shotgun."""

from typing import Any

import posthog

from shotgun import __version__
from shotgun.agents.config import get_config_manager
from shotgun.logging_config import get_early_logger

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

        # Hardcoded PostHog configuration
        api_key = "phc_KKnChzZUKeNqZDOTJ6soCBWNQSx3vjiULdwTR9H5Mcr"

        logger.debug("Using hardcoded PostHog configuration")

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

        # Set user context with anonymous user ID from config
        try:
            config_manager = get_config_manager()
            user_id = config_manager.get_user_id()

            # Identify the user in PostHog
            posthog.identify(  # type: ignore[attr-defined]
                distinct_id=user_id,
                properties={
                    "version": __version__,
                    "environment": environment,
                },
            )

            # Set default properties for all events
            posthog.disabled = False
            posthog.personal_api_key = None  # Not needed for event tracking

            logger.debug("PostHog user identified with anonymous ID: %s", user_id)
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
        # Get user ID for tracking
        config_manager = get_config_manager()
        user_id = config_manager.get_user_id()

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
            distinct_id=user_id, event=event_name, properties=properties
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
