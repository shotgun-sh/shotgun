"""Cascade tools for the Router Agent.

These tools help the router understand file dependencies and determine
which files need to be updated when a parent file changes.
"""

from pydantic_ai import RunContext

from shotgun.agents.models import AgentDeps
from shotgun.agents.router.models import FILE_DEPENDENCIES, get_dependent_files
from shotgun.agents.tools.registry import ToolCategory, register_tool
from shotgun.logging_config import get_logger

logger = get_logger(__name__)


@register_tool(
    category=ToolCategory.ARTIFACT_MANAGEMENT,
    display_text="Checking dependents",
    key_arg="file_path",
)
async def check_dependents(ctx: RunContext[AgentDeps], file_path: str) -> str:
    """Check which files depend on the given file.

    Use this to understand what other files might need updating
    after modifying a file in the shotgun workflow.

    Args:
        file_path: Path to the file to check (e.g., "specification.md")

    Returns:
        List of dependent files, or message if none exist
    """
    logger.debug("Checking dependents for: %s", file_path)

    dependents = get_dependent_files(file_path)

    if not dependents:
        return f"No files depend on '{file_path}'. It is a leaf node in the dependency chain."

    return (
        f"Files that depend on '{file_path}':\n"
        + "\n".join(f"  - {dep}" for dep in dependents)
        + "\n\nConsider asking the user if these should be updated to stay in sync."
    )


@register_tool(
    category=ToolCategory.ARTIFACT_MANAGEMENT,
    display_text="Getting dependencies",
    key_arg="",
)
async def get_file_dependencies(ctx: RunContext[AgentDeps]) -> str:
    """Get the full file dependency map.

    Returns the complete dependency chain showing how shotgun
    workflow files relate to each other.

    Returns:
        Formatted dependency map
    """
    logger.debug("Getting file dependency map")

    lines = ["File Dependency Map:", ""]
    lines.append("Changes flow downstream in this order:")
    lines.append("  research.md → specification.md → plan.md → tasks.md")
    lines.append("")
    lines.append("Detailed dependencies:")

    for file, deps in FILE_DEPENDENCIES.items():
        if deps:
            lines.append(f"  {file} → {', '.join(deps)}")
        else:
            lines.append(f"  {file} (leaf node, no dependents)")

    return "\n".join(lines)
