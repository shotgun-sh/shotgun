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

        # Configure Logfire (disable console output, only send to website)
        logfire.configure(
            token=logfire_token,
            console=False,  # Disable console output entirely
        )

        # Instrument Pydantic AI for better observability
        logfire.instrument_pydantic_ai()

        # Set user context using baggage for all logs and spans
        try:
            from opentelemetry import baggage, context

            from shotgun.agents.config import get_config_manager

            config_manager = get_config_manager()
            user_id = config_manager.get_user_id()

            # Set user_id as baggage in global context - this will be included in all logs/spans
            ctx = baggage.set_baggage("user_id", user_id)
            context.attach(ctx)
            logger.debug("Logfire user context set with user_id: %s", user_id)
        except Exception as e:
            logger.warning("Failed to set Logfire user context: %s", e)

        logger.debug("Logfire observability configured successfully")
        logger.debug("Token configured: %s", "Yes" if logfire_token else "No")
        return True

    except ImportError as e:
        logger.warning("Logfire not available: %s", e)
        return False
    except Exception as e:
        logger.warning("Failed to setup Logfire observability: %s", e)
        return False
