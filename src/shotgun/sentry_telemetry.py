"""Sentry observability setup for Shotgun."""

from pathlib import Path
from typing import Any

from shotgun import __version__
from shotgun.logging_config import get_early_logger
from shotgun.settings import settings

# Use early logger to prevent automatic StreamHandler creation
logger = get_early_logger(__name__)


def _scrub_path(path: str) -> str:
    """Scrub sensitive information from file paths.

    Removes home directory and current working directory prefixes to prevent
    leaking usernames that might be part of the path.

    Args:
        path: The file path to scrub

    Returns:
        The scrubbed path with sensitive prefixes removed
    """
    if not path:
        return path

    try:
        # Get home and cwd as Path objects for comparison
        home = Path.home()
        cwd = Path.cwd()

        # Convert path to Path object
        path_obj = Path(path)

        # Try to make path relative to cwd first (most common case)
        try:
            relative_to_cwd = path_obj.relative_to(cwd)
            return str(relative_to_cwd)
        except ValueError:
            pass

        # Try to replace home directory with ~
        try:
            relative_to_home = path_obj.relative_to(home)
            return f"~/{relative_to_home}"
        except ValueError:
            pass

        # If path is absolute but not under cwd or home, just return filename
        if path_obj.is_absolute():
            return path_obj.name

        # Return as-is if already relative
        return path

    except Exception:
        # If anything goes wrong, return the original path
        # Better to leak a path than break error reporting
        return path


def _scrub_sensitive_paths(event: dict[str, Any]) -> None:
    """Scrub sensitive paths from Sentry event data.

    Modifies the event in-place to remove:
    - Home directory paths (might contain usernames)
    - Current working directory paths (might contain usernames)
    - Server name/hostname
    - Paths in sys.argv

    Args:
        event: The Sentry event dictionary to scrub
    """
    extra = event.get("extra", {})
    if "sys.argv" in extra:
        argv = extra["sys.argv"]
        if isinstance(argv, list):
            extra["sys.argv"] = [
                _scrub_path(arg) if isinstance(arg, str) else arg for arg in argv
            ]

    # Scrub server name if present
    if "server_name" in event:
        event["server_name"] = ""

    # Scrub contexts that might contain paths
    if "contexts" in event:
        contexts = event["contexts"]
        # Remove runtime context if it has CWD
        if "runtime" in contexts:
            if "cwd" in contexts["runtime"]:
                del contexts["runtime"]["cwd"]
            # Scrub sys.argv to remove paths
            if "sys.argv" in contexts["runtime"]:
                argv = contexts["runtime"]["sys.argv"]
                if isinstance(argv, list):
                    contexts["runtime"]["sys.argv"] = [
                        _scrub_path(arg) if isinstance(arg, str) else arg
                        for arg in argv
                    ]

    # Scrub exception stack traces
    if "exception" in event and "values" in event["exception"]:
        for exception in event["exception"]["values"]:
            if "stacktrace" in exception and "frames" in exception["stacktrace"]:
                for frame in exception["stacktrace"]["frames"]:
                    # Scrub file paths
                    if "abs_path" in frame:
                        frame["abs_path"] = _scrub_path(frame["abs_path"])
                    if "filename" in frame:
                        frame["filename"] = _scrub_path(frame["filename"])

                    # Scrub local variables that might contain paths
                    if "vars" in frame:
                        for var_name, var_value in frame["vars"].items():
                            if isinstance(var_value, str):
                                frame["vars"][var_name] = _scrub_path(var_value)

    # Scrub breadcrumbs that might contain paths
    if "breadcrumbs" in event and "values" in event["breadcrumbs"]:
        for breadcrumb in event["breadcrumbs"]["values"]:
            if "data" in breadcrumb:
                for key, value in breadcrumb["data"].items():
                    if isinstance(value, str):
                        breadcrumb["data"][key] = _scrub_path(value)


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
        # Dev versions contain "dev", "rc", "alpha", "beta"
        if any(marker in __version__ for marker in ["dev", "rc", "alpha", "beta"]):
            environment = "development"
        else:
            environment = "production"

        def before_send(event: Any, hint: dict[str, Any]) -> Any:
            """Filter out user-actionable errors and scrub sensitive paths.

            User-actionable errors (like context size limits) are expected conditions
            that users need to resolve, not bugs that need tracking.

            Also scrubs sensitive information like usernames from file paths and
            working directories to protect user privacy.
            """

            log_record = hint.get("log_record")
            if log_record:
                # Scrub pathname using the helper function
                log_record.pathname = _scrub_path(log_record.pathname)

                # Scrub traceback text if it exists
                if hasattr(log_record, "exc_text") and isinstance(
                    log_record.exc_text, str
                ):
                    # Replace home directory in traceback text
                    home = Path.home()
                    log_record.exc_text = log_record.exc_text.replace(str(home), "~")

            if "exc_info" in hint:
                _, exc_value, _ = hint["exc_info"]
                from shotgun.exceptions import ErrorNotPickedUpBySentry

                if isinstance(exc_value, ErrorNotPickedUpBySentry):
                    # Don't send to Sentry - this is user-actionable, not a bug
                    return None

            # Scrub sensitive paths from the event
            _scrub_sensitive_paths(event)
            return event

        # Initialize Sentry
        sentry_sdk.init(
            dsn=dsn,
            release=f"shotgun-sh@{__version__}",
            environment=environment,
            send_default_pii=False,  # Privacy-first: never send PII
            server_name="",  # Privacy: don't send hostname (may contain username)
            traces_sample_rate=0.1 if environment == "production" else 1.0,
            profiles_sample_rate=0.1 if environment == "production" else 1.0,
            before_send=before_send,
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
