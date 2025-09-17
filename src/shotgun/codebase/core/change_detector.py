"""Change detection for incremental graph updates."""

import hashlib
import os
from enum import Enum
from pathlib import Path
from typing import Any, cast

import kuzu

from shotgun.logging_config import get_logger

logger = get_logger(__name__)


class ChangeType(Enum):
    """Types of file changes."""

    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"


class ChangeDetector:
    """Detects changes in the codebase by comparing with FileMetadata nodes."""

    def __init__(self, connection: kuzu.Connection, repo_path: Path):
        """Initialize change detector.

        Args:
            connection: Kuzu database connection
            repo_path: Root path of the repository
        """
        self.conn = connection
        self.repo_path = Path(repo_path).resolve()

        # Validate that repo path exists
        if not self.repo_path.exists():
            raise ValueError(f"Repository path does not exist: {self.repo_path}")
        if not self.repo_path.is_dir():
            raise ValueError(f"Repository path is not a directory: {self.repo_path}")

        logger.info(f"ChangeDetector initialized with repo_path: {self.repo_path}")

    def detect_changes(
        self,
        languages: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> dict[str, ChangeType]:
        """Detect all changes since last update.

        Args:
            languages: Optional list of languages to include
            exclude_patterns: Optional patterns to exclude

        Returns:
            Dictionary mapping file paths to change types
        """
        changes = {}
        current_files = set()

        # Get supported file extensions
        from shotgun.codebase.core.language_config import get_language_config

        supported_extensions = set()
        if languages:
            # Map language names to their primary extensions
            lang_to_ext = {
                "python": ".py",
                "javascript": ".js",
                "typescript": ".ts",
                "java": ".java",
                "cpp": ".cpp",
                "c": ".c",
                "csharp": ".cs",
                "go": ".go",
                "rust": ".rs",
                "ruby": ".rb",
                "php": ".php",
            }

            for lang in languages:
                # Try to get config using the language's primary extension
                primary_ext = lang_to_ext.get(lang.lower())
                if primary_ext:
                    config = get_language_config(primary_ext)
                    if config:
                        supported_extensions.update(config.file_extensions)
        else:
            # Get all supported extensions
            for ext in [
                ".py",
                ".js",
                ".ts",
                ".tsx",
                ".jsx",
                ".java",
                ".cpp",
                ".c",
                ".hpp",
                ".h",
                ".cs",
                ".go",
                ".rs",
                ".rb",
                ".php",
            ]:
                if get_language_config(ext):
                    supported_extensions.add(ext)

        # Walk through all source files
        logger.debug(
            f"Walking source files in {self.repo_path} with extensions {supported_extensions}"
        )
        for filepath in self._walk_source_files(supported_extensions, exclude_patterns):
            # Normalize the relative path to use forward slashes consistently
            relative_path = str(filepath.relative_to(self.repo_path)).replace(
                os.sep, "/"
            )
            current_files.add(relative_path)

            file_info = self._get_file_info(relative_path)
            if not file_info:
                # New file
                changes[relative_path] = ChangeType.ADDED
                logger.debug(f"Detected new file: {relative_path}")
            else:
                # Check if modified
                mtime = int(filepath.stat().st_mtime)
                if mtime > file_info["mtime"]:
                    # Check hash to confirm actual change
                    current_hash = self._calculate_file_hash(filepath)
                    if current_hash != file_info.get("hash", ""):
                        changes[relative_path] = ChangeType.MODIFIED
                        logger.debug(f"Detected modified file: {relative_path}")

        # Check for deleted files
        tracked_files = self._get_tracked_files()
        logger.debug(
            f"Found {len(tracked_files)} tracked files, {len(current_files)} current files"
        )

        # Log sample of files for debugging
        if tracked_files and current_files:
            logger.debug(f"Sample tracked files: {list(tracked_files)[:5]}")
            logger.debug(f"Sample current files: {list(current_files)[:5]}")

        for tracked_file in tracked_files:
            if tracked_file not in current_files:
                changes[tracked_file] = ChangeType.DELETED
                logger.debug(f"Detected deleted file: {tracked_file}")

        # Warn if detecting large number of deletions
        deleted_count = sum(1 for c in changes.values() if c == ChangeType.DELETED)
        if deleted_count > 100:
            logger.warning(
                f"Detected {deleted_count} file deletions - this may indicate a path resolution issue"
            )

        logger.info(
            f"Detected {len(changes)} file changes: "
            f"{sum(1 for c in changes.values() if c == ChangeType.ADDED)} added, "
            f"{sum(1 for c in changes.values() if c == ChangeType.MODIFIED)} modified, "
            f"{sum(1 for c in changes.values() if c == ChangeType.DELETED)} deleted"
        )

        return changes

    def _get_file_info(self, filepath: str) -> dict[str, Any] | None:
        """Get FileMetadata info for a file.

        Args:
            filepath: Relative file path

        Returns:
            Dictionary with file metadata or None if not found
        """
        try:
            result = self.conn.execute(
                "MATCH (f:FileMetadata {filepath: $path}) RETURN f.mtime, f.hash",
                {"path": filepath},
            )

            # Handle the QueryResult properly - cast to proper type
            if hasattr(result, "has_next"):
                query_result = cast(Any, result)
                if query_result.has_next():
                    row = query_result.get_next()
                    if isinstance(row, list | tuple) and len(row) >= 2:
                        return {"mtime": row[0], "hash": row[1]}
        except Exception as e:
            logger.error(f"Failed to get file info for {filepath}: {e}")

        return None

    def _get_tracked_files(self) -> list[str]:
        """Get all tracked file paths from database.

        Returns:
            List of relative file paths
        """
        files = []
        try:
            result = self.conn.execute("MATCH (f:FileMetadata) RETURN f.filepath")
            # Handle the QueryResult properly - cast to proper type
            if hasattr(result, "has_next"):
                query_result = cast(Any, result)
                while query_result.has_next():
                    # Normalize path separators to forward slashes
                    row = query_result.get_next()
                    if isinstance(row, list | tuple) and len(row) > 0:
                        filepath = row[0]
                        if filepath:
                            normalized_path = filepath.replace(os.sep, "/")
                            files.append(normalized_path)
        except Exception as e:
            logger.error(f"Failed to get tracked files: {e}")
        return files

    def _walk_source_files(
        self, supported_extensions: set[str], exclude_patterns: list[str] | None = None
    ) -> list[Path]:
        """Walk repository and find all source files.

        Args:
            supported_extensions: Set of file extensions to include
            exclude_patterns: Optional patterns to exclude

        Returns:
            List of absolute file paths
        """
        source_files = []
        ignore_dirs = {
            ".git",
            "__pycache__",
            "node_modules",
            ".venv",
            "venv",
            ".env",
            "dist",
            "build",
            ".pytest_cache",
            ".mypy_cache",
            ".tox",
        }

        logger.debug(f"Walking files from: {self.repo_path}")
        logger.debug(f"Current working directory: {Path.cwd()}")

        # Add custom exclude patterns
        if exclude_patterns:
            for pattern in exclude_patterns:
                if pattern.startswith("*/"):
                    ignore_dirs.add(pattern[2:])

        for root, dirs, files in os.walk(self.repo_path):
            root_path = Path(root)

            # Filter out ignored directories
            dirs[:] = [d for d in dirs if d not in ignore_dirs]

            # Skip if any parent directory should be ignored
            if any(part in ignore_dirs for part in root_path.parts):
                continue

            for file in files:
                filepath = root_path / file

                # Check if it's a supported source file
                if filepath.suffix in supported_extensions:
                    # Check exclude patterns
                    if exclude_patterns:
                        relative_path = str(filepath.relative_to(self.repo_path))
                        if any(
                            self._matches_pattern(relative_path, pattern)
                            for pattern in exclude_patterns
                        ):
                            continue

                    source_files.append(filepath)

        return source_files

    def _matches_pattern(self, filepath: str, pattern: str) -> bool:
        """Check if filepath matches an exclude pattern.

        Args:
            filepath: File path to check
            pattern: Pattern to match against

        Returns:
            True if matches
        """
        # Simple pattern matching
        if "*" in pattern:
            # Convert simple glob to regex-like matching
            import fnmatch

            return fnmatch.fnmatch(filepath, pattern)
        else:
            # Direct substring match
            return pattern in filepath

    def _calculate_file_hash(self, filepath: Path) -> str:
        """Calculate hash of file contents.

        Args:
            filepath: Path to file

        Returns:
            SHA256 hash of file contents
        """
        try:
            with open(filepath, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()
        except Exception as e:
            logger.error(f"Failed to calculate hash for {filepath}: {e}")
            return ""

    def get_file_nodes(self, filepath: str) -> set[str]:
        """Get all nodes tracked by a FileMetadata.

        Args:
            filepath: Relative file path

        Returns:
            Set of qualified names of nodes in the file
        """
        nodes = set()

        # Query each TRACKS relationship type
        for node_type, rel_type in [
            ("Module", "TRACKS_Module"),
            ("Class", "TRACKS_Class"),
            ("Function", "TRACKS_Function"),
            ("Method", "TRACKS_Method"),
        ]:
            try:
                result = self.conn.execute(
                    f"""
                    MATCH (f:FileMetadata {{filepath: $path}})-[:{rel_type}]->(n:{node_type})
                    RETURN n.qualified_name
                """,
                    {"path": filepath},
                )

                # Handle the QueryResult properly - cast to proper type
                if hasattr(result, "has_next"):
                    query_result = cast(Any, result)
                    while query_result.has_next():
                        row = query_result.get_next()
                        if isinstance(row, list | tuple) and len(row) > 0:
                            nodes.add(row[0])
            except Exception as e:
                # Ignore if relationship doesn't exist - this is expected when tables aren't created yet
                logger.debug(f"No {rel_type} relationship found for {filepath}: {e}")

        return nodes
