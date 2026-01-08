"""Gitignore pattern matching for codebase indexing.

This module provides functionality to read and apply .gitignore rules
to filter files during indexing, significantly improving performance
for large codebases that may contain ignored directories like venv,
node_modules, build artifacts, etc.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pathspec

from shotgun.codebase.models import GitignoreStats
from shotgun.logging_config import get_logger

if TYPE_CHECKING:
    from pathspec import PathSpec

logger = get_logger(__name__)


class GitignoreManager:
    """Manages gitignore patterns for a repository.

    This class loads and caches gitignore patterns from:
    1. The repository's .gitignore file
    2. Any .gitignore files in subdirectories (hierarchical gitignore)
    3. Global gitignore patterns (optional)

    Usage:
        manager = GitignoreManager(repo_path)
        if manager.is_ignored("path/to/file.py"):
            # Skip this file
            pass
    """

    def __init__(
        self,
        repo_path: Path,
        load_nested: bool = True,
        respect_gitignore: bool = True,
    ):
        """Initialize the gitignore manager.

        Args:
            repo_path: Root path of the repository
            load_nested: Whether to load .gitignore files from subdirectories
            respect_gitignore: Whether to respect .gitignore at all (if False, nothing is ignored)
        """
        self.repo_path = repo_path.resolve()
        self.load_nested = load_nested
        self.respect_gitignore = respect_gitignore

        # Cache for PathSpec objects by directory
        self._specs: dict[Path, PathSpec] = {}

        # Combined spec for the root gitignore
        self._root_spec: PathSpec | None = None

        # Statistics for debugging
        self.stats = GitignoreStats()

        if respect_gitignore:
            self._load_gitignore_files()

    def _load_gitignore_files(self) -> None:
        """Load all gitignore files in the repository."""
        root_gitignore = self.repo_path / ".gitignore"

        if root_gitignore.exists():
            self._root_spec = self._load_gitignore_file(root_gitignore)
            self.stats.gitignore_files_loaded += 1
            logger.debug(
                f"Loaded root .gitignore with patterns - "
                f"path: {root_gitignore}, patterns: {self.stats.patterns_loaded}"
            )

        if self.load_nested:
            # Find all nested .gitignore files
            for gitignore_path in self.repo_path.rglob(".gitignore"):
                if gitignore_path.parent == self.repo_path:
                    continue  # Skip root, already loaded

                spec = self._load_gitignore_file(gitignore_path)
                if spec:
                    self._specs[gitignore_path.parent] = spec
                    self.stats.gitignore_files_loaded += 1

            if self._specs:
                logger.debug(f"Loaded {len(self._specs)} nested .gitignore files")

    def _load_gitignore_file(self, gitignore_path: Path) -> PathSpec | None:
        """Load patterns from a single gitignore file.

        Args:
            gitignore_path: Path to the .gitignore file

        Returns:
            PathSpec object or None if file couldn't be loaded
        """
        try:
            with open(gitignore_path, encoding="utf-8", errors="ignore") as f:
                patterns = f.read().splitlines()

            # Filter out empty lines and comments
            valid_patterns = [
                p.strip()
                for p in patterns
                if p.strip() and not p.strip().startswith("#")
            ]

            if not valid_patterns:
                return None

            self.stats.patterns_loaded += len(valid_patterns)

            return pathspec.PathSpec.from_lines("gitwildmatch", valid_patterns)
        except Exception as e:
            logger.warning(f"Failed to load gitignore: {gitignore_path}, error: {e}")
            return None

    def is_ignored(self, path: str | Path) -> bool:
        """Check if a path should be ignored based on gitignore rules.

        Args:
            path: Path to check (relative to repo root or absolute)

        Returns:
            True if the path should be ignored
        """
        if not self.respect_gitignore:
            return False

        self.stats.files_checked += 1

        # Convert to Path and make relative to repo root
        path_obj = Path(path) if isinstance(path, str) else path

        if path_obj.is_absolute():
            # Resolve to handle symlinks (e.g., /var -> /private/var on macOS)
            try:
                resolved_path = path_obj.resolve()
                path_obj = resolved_path.relative_to(self.repo_path)
            except ValueError:
                # Path is not under repo_path
                return False

        # Convert to string with forward slashes for consistency
        path_str = str(path_obj).replace("\\", "/")

        # Check root gitignore first
        if self._root_spec and self._root_spec.match_file(path_str):
            self.stats.files_ignored += 1
            return True

        # Check nested gitignore files
        if self.load_nested:
            # Walk up the directory tree to find applicable gitignore files
            current_dir = (self.repo_path / path_obj).parent
            while current_dir >= self.repo_path:
                if current_dir in self._specs:
                    # Make path relative to this gitignore's directory
                    try:
                        rel_path = path_obj.relative_to(
                            current_dir.relative_to(self.repo_path)
                        )
                        rel_path_str = str(rel_path).replace("\\", "/")
                        if self._specs[current_dir].match_file(rel_path_str):
                            self.stats.files_ignored += 1
                            return True
                    except ValueError:
                        pass
                current_dir = current_dir.parent

        return False

    def is_directory_ignored(self, path: str | Path) -> bool:
        """Check if a directory should be ignored.

        For directories, we add a trailing slash to match gitignore semantics.

        Args:
            path: Directory path to check

        Returns:
            True if the directory should be ignored
        """
        if not self.respect_gitignore:
            return False

        # Convert to Path and make relative to repo root
        path_obj = Path(path) if isinstance(path, str) else path

        if path_obj.is_absolute():
            try:
                path_obj = path_obj.relative_to(self.repo_path)
            except ValueError:
                return False

        # Check both with and without trailing slash
        path_str = str(path_obj).replace("\\", "/")
        path_str_dir = path_str.rstrip("/") + "/"

        # Check root gitignore
        if self._root_spec:
            if self._root_spec.match_file(path_str) or self._root_spec.match_file(
                path_str_dir
            ):
                logger.debug(f"Directory ignored by root .gitignore: {path_str}")
                return True

        return False

    def filter_paths(self, paths: list[Path]) -> list[Path]:
        """Filter a list of paths, removing ignored ones.

        Args:
            paths: List of paths to filter

        Returns:
            List of paths that are not ignored
        """
        return [p for p in paths if not self.is_ignored(p)]

    def get_stats_summary(self) -> str:
        """Get a summary of gitignore statistics.

        Returns:
            Human-readable statistics string
        """
        return (
            f"Gitignore stats: "
            f"{self.stats.gitignore_files_loaded} files loaded, "
            f"{self.stats.patterns_loaded} patterns, "
            f"{self.stats.files_checked} paths checked, "
            f"{self.stats.files_ignored} ignored"
        )


def load_gitignore_for_repo(repo_path: Path | str) -> GitignoreManager:
    """Convenience function to create a GitignoreManager for a repository.

    Args:
        repo_path: Path to the repository root

    Returns:
        Configured GitignoreManager
    """
    return GitignoreManager(Path(repo_path))
