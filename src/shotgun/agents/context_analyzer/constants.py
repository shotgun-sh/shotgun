"""Tool category registry for context analysis."""

import sentry_sdk

from shotgun.logging_config import get_logger

logger = get_logger(__name__)

# Tool category registry - maps tool names to their semantic category
TOOL_CATEGORIES = {
    # Codebase understanding tools
    "query_graph": "codebase_understanding",
    "retrieve_code": "codebase_understanding",
    "file_read": "codebase_understanding",
    "directory_lister": "codebase_understanding",
    "codebase_shell": "codebase_understanding",
    # Artifact management tools
    "write_file": "artifact_management",
    "append_file": "artifact_management",
    "read_file": "artifact_management",
    # Web research tools
    "openai_web_search_tool": "web_research",
    "anthropic_web_search_tool": "web_research",
    "gemini_web_search_tool": "web_research",
    # Special: final_result is treated as agent response, not a tool
    "final_result": "agent_response",
}


def get_tool_category(tool_name: str) -> str:
    """Get category for a tool, logging unknown tools to Sentry.

    Args:
        tool_name: Name of the tool

    Returns:
        Category name or "unknown"
    """
    category = TOOL_CATEGORIES.get(tool_name)

    if category is None:
        logger.warning(f"Unknown tool encountered in context analysis: {tool_name}")
        sentry_sdk.capture_message(
            f"Unknown tool in context analysis: {tool_name}",
            level="warning",
            extras={"tool_name": tool_name},
        )
        return "unknown"

    return category
