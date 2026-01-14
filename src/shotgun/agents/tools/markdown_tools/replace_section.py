"""Tool for replacing markdown sections."""

from pydantic_ai import RunContext

from shotgun.agents.models import AgentDeps, FileOperationType
from shotgun.agents.tools.file_management import _validate_agent_scoped_path
from shotgun.agents.tools.registry import ToolCategory, register_tool
from shotgun.logging_config import get_logger

from .utils import (
    find_and_validate_section,
    load_markdown_file,
    split_normalized_content,
    write_markdown_file,
)

logger = get_logger(__name__)


@register_tool(
    category=ToolCategory.ARTIFACT_MANAGEMENT,
    display_text="Replacing section",
    key_arg="filename",
    secondary_key_arg="section_heading",
)
async def replace_markdown_section(
    ctx: RunContext[AgentDeps],
    filename: str,
    section_heading: str,
    new_contents: str,
    new_heading: str | None = None,
) -> str:
    """Replace an entire section in a Markdown file.

    PREFER THIS TOOL over rewriting the entire file - it is faster, less costly,
    and less error-prone.

    Uses fuzzy matching on headings so minor typos are tolerated.
    Replaces from the target heading down to (but not including) the next
    heading at the same or higher level.

    Args:
        ctx: Run context with agent dependencies
        filename: Path to the Markdown file (relative to .shotgun directory)
        section_heading: The heading to find (e.g., '## Requirements'). Fuzzy matched.
        new_contents: The new content for the section body (not including the heading)
        new_heading: Optional new heading text to replace the old one

    Returns:
        Success message or error message
    """
    logger.debug("Replacing section '%s' in: %s", section_heading, filename)

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

        old_section_lines = match.end_line - match.start_line

        # Build new section
        final_heading = new_heading if new_heading else match.heading.text  # type: ignore[union-attr]
        new_content_lines = split_normalized_content(new_contents)

        # Build the new section: heading + blank line + content
        new_section_lines = [final_heading, ""]
        new_section_lines.extend(new_content_lines)

        # Add trailing blank line if not at EOF
        if match.end_line < len(file_ctx.lines):
            new_section_lines.append("")

        # Replace section
        new_lines = (
            file_ctx.lines[: match.start_line]
            + new_section_lines
            + file_ctx.lines[match.end_line :]
        )

        # Write the modified file
        await write_markdown_file(file_ctx, new_lines)

        # Track the file operation
        ctx.deps.file_tracker.add_operation(file_path, FileOperationType.UPDATED)

        logger.debug(
            "Successfully replaced section '%s' in %s",
            match.heading.text,  # type: ignore[union-attr]
            filename,
        )

        new_section_line_count = len(new_section_lines)
        confidence_display = f"{int(match.confidence * 100)}%"

        return (
            f"Successfully replaced section '{match.heading.text}' in {filename} "  # type: ignore[union-attr]
            f"(matched with {confidence_display} confidence, "
            f"{old_section_lines} lines -> {new_section_line_count} lines)"
        )

    except ValueError as e:
        # Path validation errors
        error_msg = f"Error replacing section in '{filename}': {e}"
        logger.error("Section replacement failed: %s", error_msg)
        return error_msg

    except Exception as e:
        error_msg = f"Error replacing section in '{filename}': {e}"
        logger.error("Section replacement failed: %s", error_msg)
        return error_msg
