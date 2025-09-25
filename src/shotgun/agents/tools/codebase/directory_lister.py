"""List directory contents in codebase."""

from pathlib import Path

from pydantic_ai import RunContext

from shotgun.agents.models import AgentDeps
from shotgun.logging_config import get_logger

from .models import DirectoryListResult

logger = get_logger(__name__)


async def directory_lister(
    ctx: RunContext[AgentDeps], graph_id: str, directory: str = "."
) -> DirectoryListResult:
    """List directory contents in codebase.

    Args:
        ctx: RunContext containing AgentDeps with codebase service
        graph_id: Graph ID to identify the repository
        directory: Path to directory relative to repository root (default: ".")

    Returns:
        DirectoryListResult with formatted output via __str__
    """
    logger.debug("🔧 Listing directory: %s in graph %s", directory, graph_id)

    try:
        if not ctx.deps.codebase_service:
            return DirectoryListResult(
                success=False,
                directory=directory,
                full_path="",
                error="No codebase indexed",
            )

        # Get the graph to find the repository path
        try:
            graphs = await ctx.deps.codebase_service.list_graphs()
            graph = next((g for g in graphs if g.graph_id == graph_id), None)
        except Exception as e:
            logger.error("Error getting graph: %s", e)
            return DirectoryListResult(
                success=False,
                directory=directory,
                full_path="",
                error=f"Could not find graph with ID '{graph_id}'",
            )

        if not graph:
            return DirectoryListResult(
                success=False,
                directory=directory,
                full_path="",
                error=f"Graph '{graph_id}' not found",
            )

        # Validate the directory path is within the repository
        repo_path = Path(graph.repo_path).resolve()
        full_dir_path = (repo_path / directory).resolve()

        # Security check: ensure the resolved path is within the repository
        try:
            full_dir_path.relative_to(repo_path)
        except ValueError:
            error_msg = (
                f"Access denied: Path '{directory}' is outside repository bounds"
            )
            logger.warning("🚨 Security violation attempt: %s", error_msg)
            return DirectoryListResult(
                success=False,
                directory=directory,
                full_path=str(full_dir_path),
                error=error_msg,
            )

        # Check if directory exists
        if not full_dir_path.exists():
            return DirectoryListResult(
                success=False,
                directory=directory,
                full_path=str(full_dir_path),
                error=f"Directory '{directory}' not found in repository",
            )

        if not full_dir_path.is_dir():
            return DirectoryListResult(
                success=False,
                directory=directory,
                full_path=str(full_dir_path),
                error=f"'{directory}' is not a directory",
            )

        # List directory contents
        try:
            entries = list(full_dir_path.iterdir())
            entries.sort(key=lambda p: (not p.is_dir(), p.name.lower()))

            directories = []
            files = []

            for entry in entries:
                if entry.is_dir():
                    directories.append(entry.name)
                elif entry.is_file():
                    try:
                        size = entry.stat().st_size
                        files.append((entry.name, size))
                    except OSError:
                        files.append((entry.name, 0))

            logger.debug(
                "📄 Listed directory: %d directories, %d files",
                len(directories),
                len(files),
            )

            return DirectoryListResult(
                success=True,
                directory=directory,
                full_path=str(full_dir_path),
                directories=directories,
                files=files,
            )

        except PermissionError:
            return DirectoryListResult(
                success=False,
                directory=directory,
                full_path=str(full_dir_path),
                error=f"Permission denied accessing directory '{directory}'",
            )

    except Exception as e:
        error_msg = f"Error listing directory: {str(e)}"
        logger.error("❌ Directory listing failed: %s", str(e))
        return DirectoryListResult(
            success=False, directory=directory, full_path="", error=error_msg
        )
