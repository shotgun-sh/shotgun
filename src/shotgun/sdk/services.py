"""Service factory functions for SDK."""

from pathlib import Path

from shotgun.codebase.service import CodebaseService
from shotgun.utils import get_shotgun_home


def get_codebase_service(storage_dir: Path | str | None = None) -> CodebaseService:
    """Get CodebaseService instance with configurable storage.

    Args:
        storage_dir: Optional custom storage directory.
                    Defaults to ~/.shotgun-sh/codebases/

    Returns:
        Configured CodebaseService instance
    """
    if storage_dir is None:
        storage_dir = get_shotgun_home() / "codebases"
    elif isinstance(storage_dir, str):
        storage_dir = Path(storage_dir)
    return CodebaseService(storage_dir)
