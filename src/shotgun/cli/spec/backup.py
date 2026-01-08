"""Backup utility for .shotgun/ directory before pulling specs."""

import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from shotgun.logging_config import get_logger
from shotgun.utils import get_shotgun_home

logger = get_logger(__name__)

# Backup directory location
BACKUP_DIR = get_shotgun_home() / "backups"


async def create_backup(shotgun_dir: Path) -> str | None:
    """Create a zip backup of the .shotgun/ directory.

    Creates a timestamped backup at ~/.shotgun-sh/backups/{YYYYMMDD_HHMMSS}.zip.
    Only creates backup if the directory exists and has content.

    Args:
        shotgun_dir: Path to the .shotgun/ directory to backup

    Returns:
        Path to the backup file as string, or None if no backup was created
        (e.g., directory doesn't exist or is empty)

    Raises:
        Exception: If backup creation fails (caller should handle)
    """
    # Check if directory exists and has content
    if not shotgun_dir.exists():
        logger.debug("No .shotgun/ directory to backup")
        return None

    files_to_backup = list(shotgun_dir.rglob("*"))
    if not any(f.is_file() for f in files_to_backup):
        logger.debug(".shotgun/ directory is empty, skipping backup")
        return None

    # Create backup directory if needed
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    # Generate timestamp-based filename
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"{timestamp}.zip"

    logger.info("Creating backup of .shotgun/ at %s", backup_path)

    # Create zip file
    with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for file_path in files_to_backup:
            if file_path.is_file():
                # Store with path relative to shotgun_dir
                arcname = file_path.relative_to(shotgun_dir)
                zipf.write(file_path, arcname)
                logger.debug("Added to backup: %s", arcname)

    logger.info("Backup created successfully: %s", backup_path)
    return str(backup_path)


def clear_shotgun_dir(shotgun_dir: Path) -> None:
    """Clear all contents of the .shotgun/ directory.

    Removes all files and subdirectories but keeps the .shotgun/ directory itself.

    Args:
        shotgun_dir: Path to the .shotgun/ directory to clear
    """
    if not shotgun_dir.exists():
        return

    for item in shotgun_dir.iterdir():
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()

    logger.debug("Cleared contents of %s", shotgun_dir)
