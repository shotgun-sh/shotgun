"""File system utility functions."""

from pathlib import Path

import aiofiles

from shotgun.settings import settings


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
    if custom_home := settings.dev.home:
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


async def async_copy_file(src: Path, dst: Path) -> None:
    """Asynchronously copy a file from src to dst.

    Args:
        src: Source file path
        dst: Destination file path

    Raises:
        FileNotFoundError: If source file doesn't exist
        OSError: If copy operation fails
    """
    async with aiofiles.open(src, "rb") as src_file:
        content = await src_file.read()
    async with aiofiles.open(dst, "wb") as dst_file:
        await dst_file.write(content)
