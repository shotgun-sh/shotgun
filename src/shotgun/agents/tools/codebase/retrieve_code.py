"""Retrieve source code by qualified name from codebase."""

from pathlib import Path

from pydantic_ai import RunContext

from shotgun.agents.models import AgentDeps
from shotgun.codebase.core.code_retrieval import retrieve_code_by_qualified_name
from shotgun.codebase.core.language_config import get_language_config
from shotgun.logging_config import get_logger

from .models import CodeSnippetResult

logger = get_logger(__name__)


async def retrieve_code(
    ctx: RunContext[AgentDeps], graph_id: str, qualified_name: str
) -> CodeSnippetResult:
    """Get source code by fully qualified name.

    Args:
        ctx: RunContext containing AgentDeps with codebase service
        graph_id: Graph ID to query (use the ID, not the name)
        qualified_name: Fully qualified name like "module.Class.method"

    Returns:
        CodeSnippetResult with formatted output via __str__
    """
    logger.debug("🔧 Retrieving code for: %s in graph %s", qualified_name, graph_id)

    try:
        if not ctx.deps.codebase_service:
            return CodeSnippetResult(
                found=False,
                qualified_name=qualified_name,
                error="No codebase service available in context",
            )

        # Use the existing code retrieval functionality
        code_snippet = await retrieve_code_by_qualified_name(
            manager=ctx.deps.codebase_service.manager,
            graph_id=graph_id,
            qualified_name=qualified_name,
        )

        # Detect language from file extension
        language = ""
        if code_snippet.file_path:
            file_extension = Path(code_snippet.file_path).suffix
            language_config = get_language_config(file_extension)
            if language_config:
                language = language_config.name

        # Convert to our result model
        result = CodeSnippetResult(
            found=code_snippet.found,
            qualified_name=code_snippet.qualified_name,
            file_path=code_snippet.file_path if code_snippet.found else None,
            line_start=code_snippet.line_start if code_snippet.found else None,
            line_end=code_snippet.line_end if code_snippet.found else None,
            source_code=code_snippet.source_code if code_snippet.found else None,
            docstring=code_snippet.docstring,
            language=language,
            error=code_snippet.error_message if not code_snippet.found else None,
        )

        logger.debug(
            "📄 Retrieved code: %s for %s",
            "found" if result.found else "not found",
            qualified_name,
        )

        return result

    except Exception as e:
        error_msg = f"Error retrieving code: {str(e)}"
        logger.error("❌ Retrieve code failed: %s", str(e))
        return CodeSnippetResult(
            found=False, qualified_name=qualified_name, error=error_msg
        )
