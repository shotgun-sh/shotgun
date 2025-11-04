"""Sentry observability setup for Shotgun."""

from shotgun import __version__
from shotgun.logging_config import get_early_logger
from shotgun.settings import settings

# Use early logger to prevent automatic StreamHandler creation
logger = get_early_logger(__name__)


def setup_sentry_observability() -> bool:
    """Set up Sentry observability for error tracking.

    Returns:
        True if Sentry was successfully set up, False otherwise
    """
    try:
        import sentry_sdk

        # Check if Sentry is already initialized
        if sentry_sdk.is_initialized():
            logger.debug("Sentry is already initialized, skipping")
            return True

        # Get DSN from settings (handles build constants + env vars automatically)
        dsn = settings.telemetry.sentry_dsn

        if not dsn:
            logger.debug("No Sentry DSN configured, skipping Sentry initialization")
            return False

        logger.debug("Using Sentry DSN from settings, proceeding with setup")

        # Determine environment based on version
        # Dev versions contain "dev", "rc", "alpha", or "beta"
        if any(marker in __version__ for marker in ["dev", "rc", "alpha", "beta"]):
            environment = "development"
        else:
            environment = "production"

        # Initialize Sentry
        sentry_sdk.init(
            dsn=dsn,
            release=f"shotgun-sh@{__version__}",
            environment=environment,
            send_default_pii=False,  # Privacy-first: never send PII
            traces_sample_rate=0.1 if environment == "production" else 1.0,
            profiles_sample_rate=0.1 if environment == "production" else 1.0,
        )

        # Set user context with anonymous shotgun instance ID from config
        try:
            import asyncio

            from shotgun.agents.config import get_config_manager

            config_manager = get_config_manager()
            shotgun_instance_id = asyncio.run(config_manager.get_shotgun_instance_id())
            sentry_sdk.set_user({"id": shotgun_instance_id})
            logger.debug("Sentry user context set with anonymous ID")
        except Exception as e:
            logger.warning("Failed to set Sentry user context: %s", e)

        logger.debug(
            "Sentry observability configured successfully (environment: %s, version: %s)",
            environment,
            __version__,
        )
        return True

    except ImportError as e:
        logger.error("Sentry SDK not available: %s", e)
        return False
    except Exception as e:
        logger.warning("Failed to setup Sentry observability: %s", e)
        return False
