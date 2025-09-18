"""Observability setup for Logfire."""

import logging
import os

logger = logging.getLogger(__name__)


def setup_logfire_observability() -> bool:
    """Set up Logfire observability if enabled.

    Returns:
        True if Logfire was successfully set up, False otherwise
    """
    # Check if Logfire observability is enabled
    if os.getenv("LOGFIRE_ENABLED", "false").lower() not in ("true", "1", "yes"):
        logger.debug("Logfire observability disabled via LOGFIRE_ENABLED env var")
        return False

    try:
        import logfire

        # Check for Logfire token
        logfire_token = os.getenv("LOGFIRE_TOKEN")
        if not logfire_token:
            logger.warning("LOGFIRE_TOKEN not set, Logfire observability disabled")
            return False

        # Configure Logfire
        logfire.configure(token=logfire_token)

        # Instrument Pydantic AI for better observability
        logfire.instrument_pydantic_ai()

        logger.debug("Logfire observability configured successfully")
        logger.debug("Token configured: %s", "Yes" if logfire_token else "No")
        return True

    except ImportError as e:
        logger.warning("Logfire not available: %s", e)
        return False
    except Exception as e:
        logger.warning("Failed to setup Logfire observability: %s", e)
        return False
