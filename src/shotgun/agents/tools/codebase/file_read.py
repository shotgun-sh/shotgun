"""Read file contents from codebase."""

from pathlib import Path

import aiofiles
from pydantic_ai import RunContext

from shotgun.agents.models import AgentDeps
from shotgun.agents.tools.registry import ToolCategory, register_tool
from shotgun.codebase.core.language_config import get_language_config
from shotgun.logging_config import get_logger

from .models import FileReadResult

logger = get_logger(__name__)


@register_tool(
    category=ToolCategory.CODEBASE_UNDERSTANDING,
    display_text="Reading file",
    key_arg="file_path",
)
async def file_read(
    ctx: RunContext[AgentDeps], file_path: str, graph_id: str = ""
) -> FileReadResult:
    """Read file contents from codebase or current working directory.

    Args:
        ctx: RunContext containing AgentDeps with codebase service
        file_path: Path to file relative to repository root or CWD
        graph_id: Graph ID to identify the repository (optional - uses CWD if not provided)

    Returns:
        FileReadResult with formatted output via __str__
    """
    logger.debug("🔧 Reading file: %s in graph %s", file_path, graph_id or "(CWD)")

    try:
        # Determine the root path - either from indexed codebase or CWD
        repo_path: Path | None = None

        if graph_id and ctx.deps.codebase_service:
            # Try to get the graph to find the repository path
            try:
                graphs = await ctx.deps.codebase_service.list_graphs()
                graph = next((g for g in graphs if g.graph_id == graph_id), None)
                if graph:
                    repo_path = Path(graph.repo_path).resolve()
            except Exception as e:
                logger.debug("Could not find graph '%s': %s", graph_id, e)

        # Fall back to CWD if no graph found or no graph_id provided
        if repo_path is None:
            repo_path = Path.cwd().resolve()
            logger.debug("📂 Using CWD as root: %s", repo_path)

        # Validate the file path is within the root
        full_file_path = (repo_path / file_path).resolve()

        # Security check: ensure the resolved path is within the root directory
        try:
            full_file_path.relative_to(repo_path)
        except ValueError:
            error_msg = (
                f"Access denied: Path '{file_path}' is outside allowed directory bounds"
            )
            logger.warning("🚨 Security violation attempt: %s", error_msg)
            return FileReadResult(success=False, file_path=file_path, error=error_msg)

        # Check if file exists
        if not full_file_path.exists():
            return FileReadResult(
                success=False,
                file_path=file_path,
                error=f"File not found: {file_path}",
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
            async with aiofiles.open(full_file_path, encoding="utf-8") as f:
                content = await f.read()
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
                async with aiofiles.open(full_file_path, encoding="latin-1") as f:
                    content = await f.read()
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
