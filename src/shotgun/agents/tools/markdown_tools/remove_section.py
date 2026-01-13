"""Tool for removing markdown sections."""

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
    parse_section_number,
    renumber_headings_after,
)

logger = get_logger(__name__)


@register_tool(
    category=ToolCategory.ARTIFACT_MANAGEMENT,
    display_text="Removing section",
    key_arg="filename",
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

        # Check if file exists
        if not await aiofiles.os.path.exists(file_path):
            return f"Error: File '{filename}' not found"

        # Read file content (newline="" preserves original line endings)
        async with aiofiles.open(file_path, encoding="utf-8", newline="") as f:
            content = await f.read()

        # Detect line ending style
        line_ending = detect_line_ending(content)
        lines = content.split("\n")

        # Remove \r from lines if CRLF
        if line_ending == "\r\n":
            lines = [line.rstrip("\r") for line in lines]

        # Extract headings
        headings = extract_headings(content)

        if not headings:
            return f"Error: No headings found in '{filename}'. Cannot remove sections from files without headings."

        # Find matching heading
        match_result = find_matching_heading(headings, section_heading)

        if match_result is None:
            # No match found - provide helpful error with available headings
            available = [h.text for h in headings]
            close = find_close_matches(headings, section_heading)

            if close and close[0].confidence >= 0.6:
                # There are close matches but below threshold
                close_display = ", ".join(
                    f"'{m.heading_text}' ({int(m.confidence * 100)}%)" for m in close
                )
                return (
                    f"No section matching '{section_heading}' found in {filename}. "
                    f"Did you mean: {close_display}"
                )
            else:
                # List available headings
                available_display = ", ".join(available[:5])
                if len(available) > 5:
                    available_display += f" (+{len(available) - 5} more)"
                return (
                    f"No section matching '{section_heading}' found in {filename}. "
                    f"Available headings: {available_display}"
                )

        matched = match_result.heading
        confidence = match_result.confidence

        # Check for ambiguous matches (multiple close matches)
        if confidence < 1.0:
            close = find_close_matches(
                headings, section_heading, threshold=confidence - 0.1
            )
            if len(close) > 1 and close[1].confidence >= confidence - 0.05:
                # Second match is very close to first - ambiguous
                close_display = ", ".join(
                    f"'{m.heading_text}' ({int(m.confidence * 100)}%)"
                    for m in close[:3]
                )
                return (
                    f"Multiple sections closely match '{section_heading}' in {filename}: "
                    f"{close_display}. Please be more specific."
                )

        # Find section boundaries
        start_line, end_line = find_section_bounds(
            lines, matched.line_number, matched.level
        )
        removed_lines = end_line - start_line

        # Check if the removed section has a numbered heading
        section_num = parse_section_number(matched.text)
        heading_level = matched.level

        # Remove the section
        new_lines = lines[:start_line] + lines[end_line:]

        # If the removed section had a numbered heading, decrement subsequent sections
        if section_num:
            new_lines = renumber_headings_after(
                new_lines,
                start_line=start_line,
                heading_level=heading_level,
                increment=False,
            )

        # Join with detected line ending
        new_content = line_ending.join(new_lines)

        # Write file (newline="" preserves our chosen line endings)
        async with aiofiles.open(file_path, "w", encoding="utf-8", newline="") as f:
            await f.write(new_content)

        # Track the file operation
        ctx.deps.file_tracker.add_operation(file_path, FileOperationType.UPDATED)

        logger.debug("Successfully removed section '%s' from %s", matched.text, filename)

        confidence_display = f"{int(confidence * 100)}%"

        return (
            f"Successfully removed section '{matched.text}' from {filename} "
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
