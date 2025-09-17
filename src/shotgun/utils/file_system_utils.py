"""File system utility functions."""

from pathlib import Path

from shotgun.logging_config import get_logger

logger = get_logger(__name__)


def ensure_shotgun_directory_exists() -> Path:
    """Ensure the .shotgun directory exists and return its path.

    Returns:
        Path: The path to the .shotgun directory.
    """
    shotgun_dir = Path.cwd() / ".shotgun"
    shotgun_dir.mkdir(exist_ok=True)
    logger.debug("Ensured .shotgun directory exists: %s", shotgun_dir)
    return shotgun_dir
