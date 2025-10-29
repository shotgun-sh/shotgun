"""Simple auto-update functionality for shotgun-sh CLI."""

import subprocess
import sys
import threading
from pathlib import Path

import httpx
from packaging import version

from shotgun import __version__
from shotgun.logging_config import get_logger
from shotgun.settings import settings

logger = get_logger(__name__)


def detect_installation_method() -> str:
    """Detect how shotgun-sh was installed.

    Returns:
        Installation method: 'uvx', 'uv-tool', 'pipx', 'pip', 'venv', or 'unknown'.
    """
    # Check for simulation environment variable (for testing)
    if settings.dev.pipx_simulate:
        logger.debug("SHOTGUN_PIPX_SIMULATE enabled, simulating pipx installation")
        return "pipx"

    # Check for uvx (ephemeral execution) by looking at executable path
    # uvx runs from a temporary cache directory
    executable = Path(sys.executable)
    if ".cache/uv" in str(executable) or "uv/cache" in str(executable):
        logger.debug("Detected uvx (ephemeral) execution")
        return "uvx"

    # Check for uv tool installation
    try:
        result = subprocess.run(
            ["uv", "tool", "list"],  # noqa: S607, S603
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and "shotgun-sh" in result.stdout:
            logger.debug("Detected uv tool installation")
            return "uv-tool"
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    # Check for pipx installation
    try:
        result = subprocess.run(
            ["pipx", "list", "--short"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=5,  # noqa: S603
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


def perform_auto_update(no_update_check: bool = False) -> None:
    """Perform automatic update if installed via pipx or uv tool.

    Args:
        no_update_check: If True, skip the update.
    """
    if no_update_check:
        return

    try:
        method = detect_installation_method()

        # Skip auto-update for ephemeral uvx executions
        if method == "uvx":
            logger.debug("uvx (ephemeral) execution, skipping auto-update")
            return

        # Only auto-update for pipx and uv-tool installations
        if method not in ["pipx", "uv-tool"]:
            logger.debug(f"Installation method '{method}', skipping auto-update")
            return

        # Determine the appropriate upgrade command
        if method == "pipx":
            command = ["pipx", "upgrade", "shotgun-sh", "--quiet"]
            logger.debug("Running pipx upgrade shotgun-sh --quiet")
        elif method == "uv-tool":
            command = ["uv", "tool", "upgrade", "shotgun-sh"]
            logger.debug("Running uv tool upgrade shotgun-sh")
        else:
            return

        # Run upgrade command
        result = subprocess.run(  # noqa: S603, S607
            command,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            # Check if there was an actual update
            output = result.stdout.lower()
            if "upgraded" in output or "updated" in output:
                logger.info("Shotgun-sh has been updated to the latest version")
        else:
            # Only log errors at debug level to not annoy users
            logger.debug(f"Auto-update check failed: {result.stderr or result.stdout}")

    except subprocess.TimeoutExpired:
        logger.debug("Auto-update timed out")
    except Exception as e:
        logger.debug(f"Auto-update error: {e}")


def perform_auto_update_async(no_update_check: bool = False) -> threading.Thread:
    """Run auto-update in a background thread.

    Args:
        no_update_check: If True, skip the update.

    Returns:
        The thread object that was started.
    """

    def _run_update() -> None:
        perform_auto_update(no_update_check)

    thread = threading.Thread(target=_run_update, daemon=True)
    thread.start()
    return thread


def is_dev_version(version_str: str | None = None) -> bool:
    """Check if the current or given version is a development version.

    Args:
        version_str: Version string to check. If None, uses current version.

    Returns:
        True if version contains 'dev', False otherwise.
    """
    check_version = version_str or __version__
    return "dev" in check_version.lower()


def get_latest_version() -> str | None:
    """Fetch the latest version from PyPI.

    Returns:
        Latest version string if successful, None otherwise.
    """
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get("https://pypi.org/pypi/shotgun-sh/json")
            response.raise_for_status()
            data = response.json()
            latest = data.get("info", {}).get("version")
            if latest:
                logger.debug(f"Latest version from PyPI: {latest}")
                return str(latest)
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
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


def get_update_command(method: str) -> list[str] | None:
    """Get the appropriate update command based on installation method.

    Args:
        method: Installation method ('uvx', 'uv-tool', 'pipx', 'pip', 'venv', or 'unknown').

    Returns:
        Command list to execute for updating, or None for uvx (ephemeral).
    """
    commands = {
        "uvx": None,  # uvx is ephemeral, no update command
        "uv-tool": ["uv", "tool", "upgrade", "shotgun-sh"],
        "pipx": ["pipx", "upgrade", "shotgun-sh"],
        "pip": [sys.executable, "-m", "pip", "install", "--upgrade", "shotgun-sh"],
        "venv": [sys.executable, "-m", "pip", "install", "--upgrade", "shotgun-sh"],
        "unknown": [sys.executable, "-m", "pip", "install", "--upgrade", "shotgun-sh"],
    }
    return commands.get(method, commands["unknown"])


def perform_update(force: bool = False) -> tuple[bool, str]:
    """Perform manual update of shotgun-sh (for CLI command).

    Args:
        force: If True, update even if it's a dev version.

    Returns:
        Tuple of (success, message).
    """
    # Check if dev version and not forced
    if is_dev_version() and not force:
        return False, "Cannot update development version. Use --force to override."

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

    # Handle uvx (ephemeral) installations
    if method == "uvx" or command is None:
        return (
            False,
            "You're running shotgun-sh via uvx (ephemeral mode). "
            "To get the latest version, simply run 'uvx shotgun-sh' again, "
            "or install permanently with 'uv tool install shotgun-sh'.",
        )

    # Perform update
    try:
        logger.info(f"Updating shotgun-sh using {method}...")
        logger.debug(f"Running command: {' '.join(command)}")

        result = subprocess.run(command, capture_output=True, text=True, timeout=60)  # noqa: S603

        if result.returncode == 0:
            message = f"Successfully updated from {__version__} to {latest}"
            logger.info(message)
            return True, message
        else:
            error_msg = f"Update failed: {result.stderr or result.stdout}"
            logger.error(error_msg)
            return False, error_msg

    except subprocess.TimeoutExpired:
        return False, "Update command timed out"
    except Exception as e:
        return False, f"Update failed: {e}"


__all__ = [
    "detect_installation_method",
    "perform_auto_update",
    "perform_auto_update_async",
    "is_dev_version",
    "get_latest_version",
    "compare_versions",
    "get_update_command",
    "perform_update",
]
