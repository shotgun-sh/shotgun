"""File system utility functions."""

import logging
import os
from pathlib import Path
from typing import Any

import aiofiles

from shotgun.settings import settings

logger = logging.getLogger(__name__)

# Module-level override for the spec directory (set via --spec-dir CLI flag)
_spec_dir_override: Path | None = None


def set_spec_dir(spec_dir: str | None) -> None:
    """Set a custom spec directory override.

    When set, get_shotgun_base_path() will return this path instead of .shotgun/ in CWD.
    Relative paths are resolved to absolute paths.

    Args:
        spec_dir: Path to custom spec directory, or None to clear the override.
    """
    global _spec_dir_override
    if spec_dir:
        _spec_dir_override = Path(spec_dir).resolve()
        logger.info("Spec directory override set to: %s", _spec_dir_override)
    else:
        _spec_dir_override = None


def get_spec_dir_override() -> str | None:
    """Get the current spec directory override, if set.

    Returns:
        The override path as a string, or None if no override is active.
    """
    return str(_spec_dir_override) if _spec_dir_override is not None else None


def get_shotgun_base_path() -> Path:
    """Get the absolute path to the .shotgun directory."""
    if _spec_dir_override is not None:
        return _spec_dir_override
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

    # Use os.path.join for explicit path separator handling on Windows
    # This avoids potential edge cases with pathlib's / operator
    return Path(os.path.join(os.path.expanduser("~"), ".shotgun-sh"))


def ensure_shotgun_directory_exists() -> Path:
    """Ensure the .shotgun directory exists and return its path.

    Returns:
        Path: The path to the .shotgun directory.
    """
    shotgun_dir = get_shotgun_base_path()
    shotgun_dir.mkdir(exist_ok=True)
    # Note: Removed logger to avoid circular dependency with logging_config
    return shotgun_dir


def aiofiles_open_text(
    path: str | Path, mode: str = "r", **kwargs: Any
) -> aiofiles.base.AiofilesContextManager:  # type: ignore[type-arg]
    """Open a text file with aiofiles, defaulting to UTF-8 encoding.

    Use this instead of calling aiofiles.open() directly for text-mode I/O
    to ensure UTF-8 encoding is always applied (prevents Windows encoding crashes).

    Args:
        path: File path to open
        mode: File mode (default "r")
        **kwargs: Additional arguments passed to aiofiles.open()

    Returns:
        An async file context manager
    """
    return aiofiles.open(  # type: ignore[call-overload, no-any-return]
        path, mode=mode, encoding=kwargs.pop("encoding", "utf-8"), **kwargs
    )


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
