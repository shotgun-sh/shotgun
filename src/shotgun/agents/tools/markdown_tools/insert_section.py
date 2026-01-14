"""Tool for inserting content into markdown sections."""

from pydantic_ai import RunContext

from shotgun.agents.models import AgentDeps, FileOperationType
from shotgun.agents.tools.file_management import _validate_agent_scoped_path
from shotgun.agents.tools.registry import ToolCategory, register_tool
from shotgun.logging_config import get_logger

from .utils import (
    find_and_validate_section,
    get_heading_level,
    load_markdown_file,
    parse_section_number,
    renumber_headings_after,
    split_normalized_content,
    write_markdown_file,
)

logger = get_logger(__name__)


@register_tool(
    category=ToolCategory.ARTIFACT_MANAGEMENT,
    display_text="Inserting content",
    key_arg="filename",
    secondary_key_arg="new_heading",
)
async def insert_markdown_section(
    ctx: RunContext[AgentDeps],
    filename: str,
    after_heading: str,
    content: str,
    new_heading: str | None = None,
) -> str:
    """Insert content at the end of a Markdown section.

    PREFER THIS TOOL over rewriting the entire file - it is faster, less costly,
    and less error-prone. Use this to append content to an existing section.

    Uses fuzzy matching on headings so minor typos are tolerated.
    Inserts content just before the next heading at the same or higher level.

    Note: If new_heading contains a section number (e.g., "### 4.4 New Section"),
    subsequent numbered sections at the same level will be automatically incremented
    to maintain proper numbering order.

    Args:
        ctx: Run context with agent dependencies
        filename: Path to the Markdown file (relative to .shotgun directory)
        after_heading: The heading to insert after (e.g., '## Requirements'). Fuzzy matched.
        content: The content to insert at the end of the section
        new_heading: Optional heading for the inserted content (creates a subsection)

    Returns:
        Success message or error message
    """
    logger.debug("Inserting content into section '%s' in: %s", after_heading, filename)

    try:
        # Validate path with agent scoping
        file_path = _validate_agent_scoped_path(filename, ctx.deps.agent_mode)

        # Load and parse the markdown file
        file_ctx = await load_markdown_file(file_path, filename)
        if isinstance(file_ctx, str):
            return file_ctx  # Error message

        # Find and validate the target section
        match = find_and_validate_section(file_ctx, after_heading)
        if not match.is_success:
            return match.error  # type: ignore[return-value]

        # Build insert content
        insert_content_lines = split_normalized_content(content)

        # Build the insert lines
        insert_lines: list[str] = [""]  # Blank line separator before new content

        if new_heading:
            insert_lines.append(new_heading)
            insert_lines.append("")  # Blank line after heading

        insert_lines.extend(insert_content_lines)

        # Add trailing blank line if not at EOF
        if match.end_line < len(file_ctx.lines):
            insert_lines.append("")

        # Insert before section end (before next heading or EOF)
        new_lines = (
            file_ctx.lines[: match.end_line]
            + insert_lines
            + file_ctx.lines[match.end_line :]
        )

        # If new_heading has a section number, renumber subsequent sections
        if new_heading:
            new_heading_level = get_heading_level(new_heading)
            if new_heading_level:
                section_num = parse_section_number(new_heading)
                if section_num:
                    # Calculate the line number where subsequent sections start
                    # (after the inserted content)
                    renumber_start = match.end_line + len(insert_lines)
                    new_lines = renumber_headings_after(
                        new_lines,
                        start_line=renumber_start,
                        heading_level=new_heading_level,
                        increment=True,
                    )

        # Write the modified file
        await write_markdown_file(file_ctx, new_lines)

        # Track the file operation
        ctx.deps.file_tracker.add_operation(file_path, FileOperationType.UPDATED)

        logger.debug(
            "Successfully inserted content into section '%s' in %s",
            match.heading.text,  # type: ignore[union-attr]
            filename,
        )

        lines_added = len(insert_lines)
        confidence_display = f"{int(match.confidence * 100)}%"

        if new_heading:
            return (
                f"Successfully inserted '{new_heading}' into '{match.heading.text}' in {filename} "  # type: ignore[union-attr]
                f"(matched with {confidence_display} confidence, {lines_added} lines added)"
            )
        else:
            return (
                f"Successfully inserted content into '{match.heading.text}' in {filename} "  # type: ignore[union-attr]
                f"(matched with {confidence_display} confidence, {lines_added} lines added)"
            )

    except ValueError as e:
        # Path validation errors
        error_msg = f"Error inserting into '{filename}': {e}"
        logger.error("Section insertion failed: %s", error_msg)
        return error_msg

    except Exception as e:
        error_msg = f"Error inserting into '{filename}': {e}"
        logger.error("Section insertion failed: %s", error_msg)
        return error_msg
