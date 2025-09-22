"""File system utility functions."""

import os
from pathlib import Path


def get_shotgun_base_path() -> Path:
    """Get the absolute path to the .shotgun directory."""
    return Path.cwd() / ".shotgun"


def get_shotgun_home() -> Path:
    """Get the Shotgun home directory path.

    Can be overridden with SHOTGUN_HOME environment variable for testing.

    Returns:
        Path to shotgun home directory (default: ~/.shotgun-sh/)
    """
    # Allow override via environment variable (useful for testing)
    if custom_home := os.environ.get("SHOTGUN_HOME"):
        return Path(custom_home)

    return Path.home() / ".shotgun-sh"


def ensure_shotgun_directory_exists() -> Path:
    """Ensure the .shotgun directory exists and return its path.

    Returns:
        Path: The path to the .shotgun directory.
    """
    shotgun_dir = get_shotgun_base_path()
    shotgun_dir.mkdir(exist_ok=True)
    # Note: Removed logger to avoid circular dependency with logging_config
    return shotgun_dir
