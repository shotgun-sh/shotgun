"""Observability setup for Logfire."""

from shotgun.logging_config import get_early_logger
from shotgun.settings import settings

# Use early logger to prevent automatic StreamHandler creation
logger = get_early_logger(__name__)


def setup_logfire_observability() -> bool:
    """Set up Logfire observability if enabled.

    Returns:
        True if Logfire was successfully set up, False otherwise
    """
    # Get Logfire configuration from settings (handles build constants + env vars)
    logfire_enabled = settings.telemetry.logfire_enabled
    logfire_token = settings.telemetry.logfire_token

    # Check if Logfire observability is enabled
    if not logfire_enabled:
        logger.debug("Logfire observability disabled")
        return False

    try:
        import logfire

        # Check for Logfire token
        if not logfire_token:
            logger.warning("Logfire token not set, Logfire observability disabled")
            return False

        # Configure Logfire
        # Always disable console output - we only want telemetry sent to the web service
        logfire.configure(
            token=logfire_token,
            console=False,  # Never output to console, only send to Logfire service
        )

        # Instrument Pydantic AI for better observability
        logfire.instrument_pydantic_ai()

        # Add LogfireLoggingHandler to root logger so logfire logs also go to file
        import logging

        root_logger = logging.getLogger()
        logfire_handler = logfire.LogfireLoggingHandler()
        root_logger.addHandler(logfire_handler)
        logger.debug("Added LogfireLoggingHandler to root logger for file integration")

        # Set user context using baggage for all logs and spans
        try:
            import asyncio

            from opentelemetry import baggage, context

            from shotgun.agents.config import get_config_manager

            config_manager = get_config_manager()
            shotgun_instance_id = asyncio.run(config_manager.get_shotgun_instance_id())

            # Set shotgun_instance_id as baggage in global context - this will be included in all logs/spans
            ctx = baggage.set_baggage("shotgun_instance_id", shotgun_instance_id)
            context.attach(ctx)
            logger.debug(
                "Logfire user context set with shotgun_instance_id: %s",
                shotgun_instance_id,
            )
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
