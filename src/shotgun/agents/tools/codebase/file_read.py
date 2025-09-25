"""Read file contents from codebase."""

from pathlib import Path

from pydantic_ai import RunContext

from shotgun.agents.models import AgentDeps
from shotgun.codebase.core.language_config import get_language_config
from shotgun.logging_config import get_logger

from .models import FileReadResult

logger = get_logger(__name__)


async def file_read(
    ctx: RunContext[AgentDeps], graph_id: str, file_path: str
) -> FileReadResult:
    """Read file contents from codebase.

    Args:
        ctx: RunContext containing AgentDeps with codebase service
        graph_id: Graph ID to identify the repository
        file_path: Path to file relative to repository root

    Returns:
        FileReadResult with formatted output via __str__
    """
    logger.debug("🔧 Reading file: %s in graph %s", file_path, graph_id)

    try:
        if not ctx.deps.codebase_service:
            return FileReadResult(
                success=False,
                file_path=file_path,
                error="No codebase indexed",
            )

        # Get the graph to find the repository path
        try:
            graphs = await ctx.deps.codebase_service.list_graphs()
            graph = next((g for g in graphs if g.graph_id == graph_id), None)
        except Exception as e:
            logger.error("Error getting graph: %s", e)
            return FileReadResult(
                success=False,
                file_path=file_path,
                error=f"Could not find graph with ID '{graph_id}'",
            )

        if not graph:
            return FileReadResult(
                success=False,
                file_path=file_path,
                error=f"Graph '{graph_id}' not found",
            )

        # Validate the file path is within the repository
        repo_path = Path(graph.repo_path).resolve()
        full_file_path = (repo_path / file_path).resolve()

        # Security check: ensure the resolved path is within the repository
        try:
            full_file_path.relative_to(repo_path)
        except ValueError:
            error_msg = (
                f"Access denied: Path '{file_path}' is outside repository bounds"
            )
            logger.warning("🚨 Security violation attempt: %s", error_msg)
            return FileReadResult(success=False, file_path=file_path, error=error_msg)

        # Check if file exists
        if not full_file_path.exists():
            return FileReadResult(
                success=False,
                file_path=file_path,
                error=f"File '{file_path}' not found in repository",
            )

        if full_file_path.is_dir():
            return FileReadResult(
                success=False,
                file_path=file_path,
                error=f"'{file_path}' is a directory, not a file. Use directory_lister instead.",
            )

        # Read file contents
        encoding_used = "utf-8"
        try:
            content = full_file_path.read_text(encoding="utf-8")
            size_bytes = full_file_path.stat().st_size

            logger.debug(
                "📄 Read file: %d characters, %d bytes", len(content), size_bytes
            )

            # Detect language from file extension
            language = ""
            file_extension = Path(file_path).suffix
            language_config = get_language_config(file_extension)
            if language_config:
                language = language_config.name

            return FileReadResult(
                success=True,
                file_path=file_path,
                content=content,
                encoding=encoding_used,
                size_bytes=size_bytes,
                language=language,
            )
        except UnicodeDecodeError:
            try:
                # Try with different encoding
                encoding_used = "latin-1"
                content = full_file_path.read_text(encoding="latin-1")
                size_bytes = full_file_path.stat().st_size

                # Detect language from file extension
                language = ""
                file_extension = Path(file_path).suffix
                language_config = get_language_config(file_extension)
                if language_config:
                    language = language_config.name

                return FileReadResult(
                    success=True,
                    file_path=file_path,
                    content=content,
                    encoding=encoding_used,
                    size_bytes=size_bytes,
                    language=language,
                )
            except Exception:
                return FileReadResult(
                    success=False,
                    file_path=file_path,
                    error=f"Unable to read file '{file_path}' - binary or unsupported encoding",
                )

    except Exception as e:
        error_msg = f"Error reading file: {str(e)}"
        logger.error("❌ File read failed: %s", str(e))
        return FileReadResult(success=False, file_path=file_path, error=error_msg)
