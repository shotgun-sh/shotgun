"""File scanner for .shotgun/ directory."""

import fnmatch
from pathlib import Path

from shotgun.logging_config import get_logger
from shotgun.shotgun_web.models import FileMetadata

logger = get_logger(__name__)

# Patterns to ignore when scanning .shotgun/ directory
IGNORE_PATTERNS = [
    # OS-generated files
    ".DS_Store",
    "Thumbs.db",
    # Python cache
    "__pycache__",
    "*.pyc",
    "*.pyo",
    # Editor files
    ".vscode",
    ".idea",
    "*.swp",
    "*~",
    "*.bak",
    # Git
    ".git",
]


def _should_ignore(path: Path) -> bool:
    """Check if a path should be ignored based on ignore patterns.

    Args:
        path: Path to check (can be file or directory)

    Returns:
        True if path matches any ignore pattern
    """
    name = path.name

    for pattern in IGNORE_PATTERNS:
        if fnmatch.fnmatch(name, pattern):
            return True

    return False


def _is_in_ignored_directory(path: Path, base_path: Path) -> bool:
    """Check if a path is inside an ignored directory.

    Args:
        path: Path to check
        base_path: Base path to check relative to

    Returns:
        True if path is inside an ignored directory
    """
    relative = path.relative_to(base_path)
    for part in relative.parts[
        :-1
    ]:  # Check all parent directories, not the file itself
        if any(fnmatch.fnmatch(part, pattern) for pattern in IGNORE_PATTERNS):
            return True
    return False


async def scan_shotgun_directory(project_root: Path) -> list[FileMetadata]:
    """Recursively scan .shotgun/ directory and return file metadata.

    Applies ignore patterns to exclude common unwanted files like:
    - .DS_Store, Thumbs.db
    - __pycache__, *.pyc, *.pyo
    - .vscode, .idea, *.swp
    - *~, *.bak

    Args:
        project_root: Path to project root containing .shotgun/ directory

    Returns:
        List of FileMetadata with relative paths (relative to .shotgun/)

    Raises:
        FileNotFoundError: If .shotgun/ directory does not exist
    """
    shotgun_dir = project_root / ".shotgun"

    if not shotgun_dir.exists():
        raise FileNotFoundError(f".shotgun/ directory not found at {shotgun_dir}")

    if not shotgun_dir.is_dir():
        raise NotADirectoryError(f"{shotgun_dir} is not a directory")

    files: list[FileMetadata] = []

    logger.debug("Scanning directory: %s", shotgun_dir)

    for path in shotgun_dir.rglob("*"):
        # Skip directories
        if path.is_dir():
            continue

        # Skip ignored files
        if _should_ignore(path):
            logger.debug("Ignoring file (pattern match): %s", path)
            continue

        # Skip files in ignored directories
        if _is_in_ignored_directory(path, shotgun_dir):
            logger.debug("Ignoring file (in ignored directory): %s", path)
            continue

        # Calculate relative path from .shotgun/
        relative_path = str(path.relative_to(shotgun_dir))

        files.append(
            FileMetadata(
                relative_path=relative_path,
                absolute_path=path,
                size_bytes=path.stat().st_size,
            )
        )

    logger.info("Found %d files in .shotgun/", len(files))

    # Sort by relative path for consistent ordering
    files.sort(key=lambda f: f.relative_path)

    return files


def get_shotgun_directory(project_root: Path | None = None) -> Path:
    """Get the .shotgun/ directory path.

    Args:
        project_root: Optional project root path. If None, uses current directory.

    Returns:
        Path to .shotgun/ directory
    """
    if project_root is None:
        project_root = Path.cwd()
    return project_root / ".shotgun"
