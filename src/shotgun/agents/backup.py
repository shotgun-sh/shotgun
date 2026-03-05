"""Pre-agent backup for .shotgun/ artifacts.

Copies key artifact files before each agent run to prevent data loss
from destructive overwrites (e.g., LLM truncating specification.md).
"""

import shutil
from datetime import datetime, timezone
from pathlib import Path

from shotgun.logging_config import get_logger
from shotgun.utils.file_system_utils import get_shotgun_home

logger = get_logger(__name__)


def _get_backup_base_dir() -> Path:
    """Get the base directory for pre-agent backups."""
    return get_shotgun_home() / "backups" / "pre-agent"


def backup_artifacts(shotgun_dir: Path) -> Path | None:
    """Back up .shotgun/ artifacts before an agent run.

    Copies all files from the shotgun directory to a timestamped backup
    directory under ~/.shotgun-sh/backups/pre-agent/.

    Args:
        shotgun_dir: Path to the .shotgun/ directory.

    Returns:
        Path to the backup directory, or None if no backup was created.
    """
    try:
        if not shotgun_dir.exists() or not shotgun_dir.is_dir():
            return None

        # Check if there are any files to back up
        files = [f for f in shotgun_dir.rglob("*") if f.is_file()]
        if not files:
            return None

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_dir = _get_backup_base_dir() / timestamp
        backup_dir.mkdir(parents=True, exist_ok=True)

        for file_path in files:
            relative = file_path.relative_to(shotgun_dir)
            dest = backup_dir / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file_path, dest)

        logger.debug(f"Backed up {len(files)} artifact(s) to {backup_dir}")
        return backup_dir

    except Exception:
        logger.warning("Failed to back up artifacts", exc_info=True)
        return None


def cleanup_old_backups(max_backups: int = 10) -> None:
    """Remove old backup directories, keeping the most recent ones.

    Sorts backup directories by name (which sorts chronologically due
    to the timestamp format) and deletes the oldest beyond the limit.

    Args:
        max_backups: Maximum number of backup directories to keep.
    """
    try:
        backup_base = _get_backup_base_dir()
        if not backup_base.exists():
            return

        backup_dirs = sorted(
            [d for d in backup_base.iterdir() if d.is_dir()],
            reverse=True,  # Newest first
        )

        dirs_to_delete = backup_dirs[max_backups:]
        for old_dir in dirs_to_delete:
            try:
                shutil.rmtree(old_dir)
            except OSError:
                pass  # noqa: S110

    except Exception:
        logger.warning("Failed to clean up old backups", exc_info=True)
