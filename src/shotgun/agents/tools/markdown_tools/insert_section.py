"""Tool for inserting content into markdown sections."""

import aiofiles
import aiofiles.os
from pydantic_ai import RunContext

from shotgun.agents.models import AgentDeps, FileOperationType
from shotgun.agents.tools.file_management import _validate_agent_scoped_path
from shotgun.agents.tools.registry import ToolCategory, register_tool
from shotgun.logging_config import get_logger

from .utils import (
    detect_line_ending,
    extract_headings,
    find_close_matches,
    find_matching_heading,
    find_section_bounds,
    normalize_section_content,
)

logger = get_logger(__name__)


@register_tool(
    category=ToolCategory.ARTIFACT_MANAGEMENT,
    display_text="Inserting content",
    key_arg="filename",
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

        # Check if file exists
        if not await aiofiles.os.path.exists(file_path):
            return f"Error: File '{filename}' not found"

        # Read file content (newline="" preserves original line endings)
        async with aiofiles.open(file_path, encoding="utf-8", newline="") as f:
            file_content = await f.read()

        # Detect line ending style
        line_ending = detect_line_ending(file_content)
        lines = file_content.split("\n")

        # Remove \r from lines if CRLF
        if line_ending == "\r\n":
            lines = [line.rstrip("\r") for line in lines]

        # Extract headings
        headings = extract_headings(file_content)

        if not headings:
            return f"Error: No headings found in '{filename}'. Cannot insert into files without headings."

        # Find matching heading
        match_result = find_matching_heading(headings, after_heading)

        if match_result is None:
            # No match found - provide helpful error with available headings
            available = [h.text for h in headings]
            close = find_close_matches(headings, after_heading)

            if close and close[0].confidence >= 0.6:
                # There are close matches but below threshold
                close_display = ", ".join(
                    f"'{m.heading_text}' ({int(m.confidence * 100)}%)" for m in close
                )
                return (
                    f"No section matching '{after_heading}' found in {filename}. "
                    f"Did you mean: {close_display}"
                )
            else:
                # List available headings
                available_display = ", ".join(available[:5])
                if len(available) > 5:
                    available_display += f" (+{len(available) - 5} more)"
                return (
                    f"No section matching '{after_heading}' found in {filename}. "
                    f"Available headings: {available_display}"
                )

        matched = match_result.heading
        confidence = match_result.confidence

        # Check for ambiguous matches (multiple close matches)
        if confidence < 1.0:
            close = find_close_matches(
                headings, after_heading, threshold=confidence - 0.1
            )
            if len(close) > 1 and close[1].confidence >= confidence - 0.05:
                # Second match is very close to first - ambiguous
                close_display = ", ".join(
                    f"'{m.heading_text}' ({int(m.confidence * 100)}%)"
                    for m in close[:3]
                )
                return (
                    f"Multiple sections closely match '{after_heading}' in {filename}: "
                    f"{close_display}. Please be more specific."
                )

        # Find section boundaries
        _start_line, end_line = find_section_bounds(
            lines, matched.line_number, matched.level
        )

        # Build insert content
        normalized_content = normalize_section_content(content)
        insert_content_lines = normalized_content.split("\n")
        # Remove empty last line from split (since we added \n)
        if insert_content_lines and insert_content_lines[-1] == "":
            insert_content_lines.pop()

        # Build the insert lines
        insert_lines: list[str] = [""]  # Blank line separator before new content

        if new_heading:
            insert_lines.append(new_heading)
            insert_lines.append("")  # Blank line after heading

        insert_lines.extend(insert_content_lines)

        # Add trailing blank line if not at EOF
        if end_line < len(lines):
            insert_lines.append("")

        # Insert before section end (before next heading or EOF)
        new_lines = lines[:end_line] + insert_lines + lines[end_line:]

        # Join with detected line ending
        new_content = line_ending.join(new_lines)

        # Write file (newline="" preserves our chosen line endings)
        async with aiofiles.open(file_path, "w", encoding="utf-8", newline="") as f:
            await f.write(new_content)

        # Track the file operation
        ctx.deps.file_tracker.add_operation(file_path, FileOperationType.UPDATED)

        logger.debug(
            "Successfully inserted content into section '%s' in %s",
            matched.text,
            filename,
        )

        lines_added = len(insert_lines)
        confidence_display = f"{int(confidence * 100)}%"

        if new_heading:
            return (
                f"Successfully inserted '{new_heading}' into '{matched.text}' in {filename} "
                f"(matched with {confidence_display} confidence, {lines_added} lines added)"
            )
        else:
            return (
                f"Successfully inserted content into '{matched.text}' in {filename} "
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
