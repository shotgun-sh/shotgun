"""Tool for removing markdown sections."""

from pydantic_ai import RunContext

from shotgun.agents.models import AgentDeps, FileOperationType
from shotgun.agents.tools.file_management import _validate_agent_scoped_path
from shotgun.agents.tools.registry import ToolCategory, register_tool
from shotgun.logging_config import get_logger

from .utils import (
    find_and_validate_section,
    load_markdown_file,
    parse_section_number,
    renumber_headings_after,
    write_markdown_file,
)

logger = get_logger(__name__)


@register_tool(
    category=ToolCategory.ARTIFACT_MANAGEMENT,
    display_text="Removing section",
    key_arg="filename",
    secondary_key_arg="section_heading",
)
async def remove_markdown_section(
    ctx: RunContext[AgentDeps],
    filename: str,
    section_heading: str,
) -> str:
    """Remove an entire section from a Markdown file.

    Uses fuzzy matching on headings so minor typos are tolerated.
    Removes from the target heading down to (but not including) the next
    heading at the same or higher level.

    Note: If the removed section has a numbered heading (e.g., "### 4.4 Title"),
    subsequent numbered sections at the same level will be automatically
    decremented to maintain proper numbering order.

    Args:
        ctx: Run context with agent dependencies
        filename: Path to the Markdown file (relative to .shotgun directory)
        section_heading: The heading to find and remove. Fuzzy matched.

    Returns:
        Success message or error message
    """
    logger.debug("Removing section '%s' from: %s", section_heading, filename)

    try:
        # Validate path with agent scoping
        file_path = _validate_agent_scoped_path(filename, ctx.deps.agent_mode)

        # Load and parse the markdown file
        file_ctx = await load_markdown_file(file_path, filename)
        if isinstance(file_ctx, str):
            return file_ctx  # Error message

        # Find and validate the target section
        match = find_and_validate_section(file_ctx, section_heading)
        if not match.is_success:
            return match.error  # type: ignore[return-value]

        removed_lines = match.end_line - match.start_line

        # Check if the removed section has a numbered heading
        section_num = parse_section_number(match.heading.text)  # type: ignore[union-attr]
        heading_level = match.heading.level  # type: ignore[union-attr]

        # Remove the section
        new_lines = (
            file_ctx.lines[: match.start_line] + file_ctx.lines[match.end_line :]
        )

        # If the removed section had a numbered heading, decrement subsequent sections
        if section_num:
            new_lines = renumber_headings_after(
                new_lines,
                start_line=match.start_line,
                heading_level=heading_level,
                increment=False,
            )

        # Write the modified file
        await write_markdown_file(file_ctx, new_lines)

        # Track the file operation
        ctx.deps.file_tracker.add_operation(file_path, FileOperationType.UPDATED)

        logger.debug(
            "Successfully removed section '%s' from %s",
            match.heading.text,  # type: ignore[union-attr]
            filename,
        )

        confidence_display = f"{int(match.confidence * 100)}%"

        return (
            f"Successfully removed section '{match.heading.text}' from {filename} "  # type: ignore[union-attr]
            f"(matched with {confidence_display} confidence, {removed_lines} lines removed)"
        )

    except ValueError as e:
        # Path validation errors
        error_msg = f"Error removing section from '{filename}': {e}"
        logger.error("Section removal failed: %s", error_msg)
        return error_msg

    except Exception as e:
        error_msg = f"Error removing section from '{filename}': {e}"
        logger.error("Section removal failed: %s", error_msg)
        return error_msg
