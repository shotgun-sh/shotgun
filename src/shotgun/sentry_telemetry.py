"""Sentry observability setup for Shotgun."""

import logging
import os

logger = logging.getLogger(__name__)


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

        # Try to get DSN from build constants first (production builds)
        dsn = None
        try:
            from shotgun import build_constants

            dsn = build_constants.SENTRY_DSN
            logger.debug("Using Sentry DSN from build constants")
        except ImportError:
            # Fallback to environment variable (development)
            dsn = os.getenv("SENTRY_DSN", "")
            if dsn:
                logger.debug("Using Sentry DSN from environment variable")

        if not dsn:
            logger.debug("No Sentry DSN configured, skipping Sentry initialization")
            return False

        logger.debug("Found DSN, proceeding with Sentry setup")

        # Get version for release tracking
        from shotgun import __version__

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

        # Set user context with anonymous user ID from config
        try:
            from shotgun.agents.config import get_config_manager

            config_manager = get_config_manager()
            user_id = config_manager.get_user_id()
            sentry_sdk.set_user({"id": user_id})
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
