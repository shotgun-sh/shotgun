"""Filtered codebase service that restricts access to current directory's codebase only."""

from pathlib import Path

from shotgun.codebase.models import CodebaseGraph
from shotgun.codebase.service import CodebaseService


class FilteredCodebaseService(CodebaseService):
    """CodebaseService subclass that filters graphs to only those accessible from CWD.

    This ensures TUI agents can only see and access the codebase indexed from the
    current working directory, providing isolation between different project directories.
    """

    def __init__(self, storage_dir: Path | str):
        """Initialize the filtered service.

        Args:
            storage_dir: Directory to store graph databases
        """
        super().__init__(storage_dir)
        self._cwd = str(Path.cwd().resolve())

    async def list_graphs(self) -> list[CodebaseGraph]:
        """List only graphs accessible from the current working directory.

        Returns:
            Filtered list of CodebaseGraph objects accessible from CWD
        """
        # Use the existing filtering logic from list_graphs_for_directory
        return await super().list_graphs_for_directory(self._cwd)

    async def list_graphs_for_directory(
        self, directory: Path | str | None = None
    ) -> list[CodebaseGraph]:
        """List graphs for directory - always filters to CWD for TUI context.

        Args:
            directory: Ignored in TUI context, always uses CWD

        Returns:
            Filtered list of CodebaseGraph objects accessible from CWD
        """
        # Always use CWD regardless of what directory is passed
        return await super().list_graphs_for_directory(self._cwd)
