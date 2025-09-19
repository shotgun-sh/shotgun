"""Auto-update functionality for shotgun-sh CLI."""

import json
import subprocess
import sys
import threading
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from packaging import version
from pydantic import BaseModel, Field, ValidationError

from shotgun import __version__
from shotgun.logging_config import get_logger
from shotgun.utils.file_system_utils import get_shotgun_home

logger = get_logger(__name__)

# Configuration constants
UPDATE_CHECK_INTERVAL = timedelta(hours=24)
PYPI_API_URL = "https://pypi.org/pypi/shotgun-sh/json"
REQUEST_TIMEOUT = 5.0  # seconds


def get_cache_file() -> Path:
    """Get the path to the update cache file.

    Returns:
        Path to the cache file in the shotgun home directory.
    """
    return get_shotgun_home() / "check-update.json"


class UpdateCache(BaseModel):
    """Model for update check cache data."""

    last_check: datetime = Field(description="Last time update check was performed")
    latest_version: str = Field(description="Latest version available on PyPI")
    current_version: str = Field(description="Current installed version at check time")
    update_available: bool = Field(
        default=False, description="Whether an update is available"
    )


def is_dev_version(version_str: str | None = None) -> bool:
    """Check if the current or given version is a development version.

    Args:
        version_str: Version string to check. If None, uses current version.

    Returns:
        True if version contains 'dev', False otherwise.
    """
    check_version = version_str or __version__
    return "dev" in check_version.lower()


def load_cache() -> UpdateCache | None:
    """Load the update check cache from disk.

    Returns:
        UpdateCache model if cache exists and is valid, None otherwise.
    """
    cache_file = get_cache_file()
    if not cache_file.exists():
        return None

    try:
        with open(cache_file) as f:
            data = json.load(f)
            return UpdateCache.model_validate(data)
    except (json.JSONDecodeError, OSError, PermissionError, ValidationError) as e:
        logger.debug(f"Failed to load cache: {e}")
        return None


def save_cache(cache_data: UpdateCache) -> None:
    """Save update check cache to disk.

    Args:
        cache_data: UpdateCache model containing cache data to save.
    """
    cache_file = get_cache_file()

    try:
        # Ensure the parent directory exists
        cache_file.parent.mkdir(parents=True, exist_ok=True)

        with open(cache_file, "w") as f:
            json.dump(cache_data.model_dump(mode="json"), f, indent=2, default=str)
    except (OSError, PermissionError) as e:
        logger.debug(f"Failed to save cache: {e}")


def should_check_for_updates(no_update_check: bool = False) -> bool:
    """Determine if we should check for updates.

    Args:
        no_update_check: If True, skip update checks.

    Returns:
        True if update check should be performed, False otherwise.
    """
    # Skip if explicitly disabled
    if no_update_check:
        return False

    # Skip if development version
    if is_dev_version():
        logger.debug("Skipping update check for development version")
        return False

    # Check cache to see if enough time has passed
    cache = load_cache()
    if not cache:
        return True

    now = datetime.now(timezone.utc)
    time_since_check = now - cache.last_check
    return time_since_check >= UPDATE_CHECK_INTERVAL


def get_latest_version() -> str | None:
    """Fetch the latest version from PyPI.

    Returns:
        Latest version string if successful, None otherwise.
    """
    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
            response = client.get(PYPI_API_URL)
            response.raise_for_status()

            data = response.json()
            latest = data.get("info", {}).get("version")

            if latest:
                logger.debug(f"Latest version from PyPI: {latest}")
                return str(latest)

    except (httpx.RequestError, httpx.HTTPStatusError, json.JSONDecodeError) as e:
        logger.debug(f"Failed to fetch latest version: {e}")

    return None


def compare_versions(current: str, latest: str) -> bool:
    """Compare version strings to determine if update is available.

    Args:
        current: Current version string.
        latest: Latest available version string.

    Returns:
        True if latest version is newer than current, False otherwise.
    """
    try:
        current_v = version.parse(current)
        latest_v = version.parse(latest)
        return latest_v > current_v
    except Exception as e:
        logger.debug(f"Error comparing versions: {e}")
        return False


def detect_installation_method() -> str:
    """Detect how shotgun-sh was installed.

    Returns:
        Installation method: 'pipx', 'pip', 'venv', or 'unknown'.
    """
    # Check for pipx installation
    try:
        result = subprocess.run(
            ["pipx", "list", "--short"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=30,  # noqa: S603
        )
        if "shotgun-sh" in result.stdout:
            logger.debug("Detected pipx installation")
            return "pipx"
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    # Check if we're in a virtual environment
    if hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    ):
        logger.debug("Detected virtual environment installation")
        return "venv"

    # Check for user installation
    import site

    user_site = site.getusersitepackages()
    if user_site and Path(user_site).exists():
        shotgun_path = Path(user_site) / "shotgun"
        if shotgun_path.exists() or any(
            p.exists() for p in Path(user_site).glob("shotgun_sh*")
        ):
            logger.debug("Detected pip --user installation")
            return "pip"

    # Default to pip if we can't determine
    logger.debug("Could not detect installation method, defaulting to pip")
    return "pip"


def get_update_command(method: str) -> list[str]:
    """Get the appropriate update command based on installation method.

    Args:
        method: Installation method ('pipx', 'pip', 'venv', or 'unknown').

    Returns:
        Command list to execute for updating.
    """
    commands = {
        "pipx": ["pipx", "upgrade", "shotgun-sh"],
        "pip": [sys.executable, "-m", "pip", "install", "--upgrade", "shotgun-sh"],
        "venv": [sys.executable, "-m", "pip", "install", "--upgrade", "shotgun-sh"],
        "unknown": [sys.executable, "-m", "pip", "install", "--upgrade", "shotgun-sh"],
    }
    return commands.get(method, commands["unknown"])


def perform_update(force: bool = False) -> tuple[bool, str]:
    """Perform the actual update of shotgun-sh.

    Args:
        force: If True, update even if it's a dev version (with confirmation).

    Returns:
        Tuple of (success, message).
    """
    # Check if dev version and not forced
    if is_dev_version() and not force:
        return False, "Cannot auto-update development version. Use --force to override."

    # Get latest version
    latest = get_latest_version()
    if not latest:
        return False, "Failed to fetch latest version from PyPI"

    # Check if update is needed
    if not compare_versions(__version__, latest):
        return False, f"Already at latest version ({__version__})"

    # Detect installation method
    method = detect_installation_method()
    command = get_update_command(method)

    # Perform update
    try:
        logger.info(f"Updating shotgun-sh using {method}...")
        logger.debug(f"Running command: {' '.join(command)}")

        result = subprocess.run(command, capture_output=True, text=True, timeout=60)  # noqa: S603

        if result.returncode == 0:
            message = f"Successfully updated from {__version__} to {latest}"
            logger.info(message)

            # Clear cache to trigger fresh check next time
            cache_file = get_cache_file()
            if cache_file.exists():
                cache_file.unlink()

            return True, message
        else:
            error_msg = f"Update failed: {result.stderr or result.stdout}"
            logger.error(error_msg)
            return False, error_msg

    except subprocess.TimeoutExpired:
        return False, "Update command timed out"
    except Exception as e:
        return False, f"Update failed: {e}"


def format_update_notification(current: str, latest: str) -> str:
    """Format a user-friendly update notification message.

    Args:
        current: Current version.
        latest: Latest available version.

    Returns:
        Formatted notification string.
    """
    return f"Update available: {current} → {latest}. Run 'shotgun update' to upgrade."


def check_for_updates_sync(no_update_check: bool = False) -> str | None:
    """Synchronously check for updates and return notification if available.

    Args:
        no_update_check: If True, skip update checks.

    Returns:
        Update notification string if update available, None otherwise.
    """
    if not should_check_for_updates(no_update_check):
        # Check cache for existing notification
        cache = load_cache()
        if cache and cache.update_available:
            current = cache.current_version
            latest = cache.latest_version
            if compare_versions(current, latest):
                return format_update_notification(current, latest)
        return None

    latest_version = get_latest_version()
    if not latest_version:
        return None
    latest = latest_version  # Type narrowing - we know it's not None here

    # Update cache
    now = datetime.now(timezone.utc)
    update_available = compare_versions(__version__, latest)

    cache_data = UpdateCache(
        last_check=now,
        latest_version=latest,
        current_version=__version__,
        update_available=update_available,
    )
    save_cache(cache_data)

    if update_available:
        return format_update_notification(__version__, latest)

    return None


def check_for_updates_async(
    callback: Callable[[str], None] | None = None, no_update_check: bool = False
) -> threading.Thread:
    """Asynchronously check for updates in a background thread.

    Args:
        callback: Optional callback function to call with notification string.
        no_update_check: If True, skip update checks.

    Returns:
        The thread object that was started.
    """

    def _check_updates() -> None:
        try:
            notification = check_for_updates_sync(no_update_check)
            if notification and callback:
                callback(notification)
        except Exception as e:
            logger.debug(f"Error in async update check: {e}")

    thread = threading.Thread(target=_check_updates, daemon=True)
    thread.start()
    return thread


__all__ = [
    "UpdateCache",
    "is_dev_version",
    "should_check_for_updates",
    "get_latest_version",
    "detect_installation_method",
    "perform_update",
    "check_for_updates_async",
    "check_for_updates_sync",
    "format_update_notification",
]
