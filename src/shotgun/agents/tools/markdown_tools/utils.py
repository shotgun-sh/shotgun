"""Utility functions for markdown parsing and manipulation."""

import re
from difflib import SequenceMatcher
from pathlib import Path

import aiofiles
import aiofiles.os

from .models import (
    CloseMatch,
    HeadingList,
    HeadingMatch,
    MarkdownFileContext,
    MarkdownHeading,
    SectionMatchResult,
    SectionNumber,
)


def get_heading_level(line: str) -> int | None:
    """Get the heading level (1-6) from a line, or None if not a heading.

    Args:
        line: A line of text to check

    Returns:
        The heading level (1-6) or None if not a heading
    """
    match = re.match(r"^(#{1,6})\s+", line)
    return len(match.group(1)) if match else None


def extract_headings(content: str) -> HeadingList:
    """Extract all headings from markdown content.

    Args:
        content: The markdown content to parse

    Returns:
        List of MarkdownHeading objects
    """
    headings: HeadingList = []
    for i, line in enumerate(content.splitlines()):
        level = get_heading_level(line)
        if level is not None:
            headings.append(MarkdownHeading(line_number=i, text=line, level=level))
    return headings


def find_matching_heading(
    headings: HeadingList,
    target: str,
    threshold: float = 0.8,
) -> HeadingMatch | None:
    """Find the best matching heading above the similarity threshold.

    Args:
        headings: List of MarkdownHeading objects
        target: The target heading to match (e.g., "## Requirements")
        threshold: Minimum similarity ratio (0.0-1.0)

    Returns:
        HeadingMatch with the matched heading and confidence, or None if no match
    """
    best_heading: MarkdownHeading | None = None
    best_ratio = 0.0

    # Normalize target: strip leading #s and whitespace, lowercase
    norm_target = target.lstrip("#").strip().lower()

    for heading in headings:
        ratio = SequenceMatcher(None, heading.normalized_text, norm_target).ratio()

        if ratio > best_ratio and ratio >= threshold:
            best_ratio = ratio
            best_heading = heading

    if best_heading is not None:
        return HeadingMatch(heading=best_heading, confidence=best_ratio)
    return None


def find_close_matches(
    headings: HeadingList,
    target: str,
    threshold: float = 0.6,
    max_matches: int = 3,
) -> list[CloseMatch]:
    """Find headings that are close matches to the target.

    Used for error messages when no exact match is found.

    Args:
        headings: List of MarkdownHeading objects
        target: The target heading to match
        threshold: Minimum similarity ratio for inclusion
        max_matches: Maximum number of matches to return

    Returns:
        List of CloseMatch objects, sorted by confidence descending
    """
    norm_target = target.lstrip("#").strip().lower()
    matches: list[CloseMatch] = []

    for heading in headings:
        ratio = SequenceMatcher(None, heading.normalized_text, norm_target).ratio()
        if ratio >= threshold:
            matches.append(CloseMatch(heading_text=heading.text, confidence=ratio))

    # Sort by confidence descending
    matches.sort(key=lambda x: x.confidence, reverse=True)
    return matches[:max_matches]


def find_section_bounds(
    lines: list[str],
    heading_line_num: int,
    heading_level: int,
) -> tuple[int, int]:
    """Find the boundaries of a section.

    The section includes everything from the heading to the next heading
    at the same or higher level (exclusive), or end of file.

    Args:
        lines: All lines of the file
        heading_line_num: Line number of the section heading
        heading_level: Level of the section heading (1-6)

    Returns:
        Tuple of (start_line, end_line) where end_line is exclusive
    """
    start = heading_line_num
    end = len(lines)  # Default to EOF

    for i in range(heading_line_num + 1, len(lines)):
        level = get_heading_level(lines[i])
        if level is not None and level <= heading_level:
            end = i
            break

    return (start, end)


def detect_line_ending(content: str) -> str:
    """Detect the line ending style used in the content.

    Args:
        content: The file content

    Returns:
        The line ending string ('\\r\\n' or '\\n')
    """
    if "\r\n" in content:
        return "\r\n"
    return "\n"


def normalize_section_content(content: str) -> str:
    """Normalize content to have no leading whitespace and single trailing newline.

    Args:
        content: The content to normalize

    Returns:
        Normalized content
    """
    return content.strip() + "\n"


def split_normalized_content(content: str) -> list[str]:
    """Normalize content and split into lines for insertion.

    Strips whitespace, ensures consistent formatting, and splits into lines
    ready for insertion into a markdown file.

    Args:
        content: The content to normalize and split

    Returns:
        List of lines (without trailing empty line from split)
    """
    normalized = normalize_section_content(content)
    lines = normalized.split("\n")
    # Remove empty last line from split (since normalize_section_content adds \n)
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def parse_section_number(heading_text: str) -> SectionNumber | None:
    """Parse section number from heading text.

    Matches patterns like:
    - "## 3. Title" -> prefix="3", has_trailing_dot=True
    - "### 4.4 Title" -> prefix="4.4", has_trailing_dot=False
    - "### 4.4. Title" -> prefix="4.4", has_trailing_dot=True
    - "## 10.2.3 Title" -> prefix="10.2.3", has_trailing_dot=False

    Args:
        heading_text: The full heading line (e.g., "### 4.4 Title")

    Returns:
        SectionNumber if a number is found, None otherwise
    """
    # Pattern: ## <number>[.<number>...][.] <title>
    # The number must be at the start after the hashes
    match = re.match(r"^#{1,6}\s+(\d+(?:\.\d+)*)(\.?)\s+", heading_text)
    if match:
        return SectionNumber(
            prefix=match.group(1),
            has_trailing_dot=bool(match.group(2)),
        )
    return None


def increment_section_number(section_num: SectionNumber) -> str:
    """Increment the last component of a section number.

    Examples:
        - "4.4" -> "4.5"
        - "3" with trailing dot -> "4."
        - "10.2.3" -> "10.2.4"

    Args:
        section_num: The parsed section number

    Returns:
        The incremented number string (with trailing dot if original had one)
    """
    parts = section_num.prefix.split(".")
    parts[-1] = str(int(parts[-1]) + 1)
    result = ".".join(parts)
    if section_num.has_trailing_dot:
        result += "."
    return result


def decrement_section_number(section_num: SectionNumber) -> str:
    """Decrement the last component of a section number.

    Examples:
        - "4.5" -> "4.4"
        - "4" with trailing dot -> "3."

    Args:
        section_num: The parsed section number

    Returns:
        The decremented number string (with trailing dot if original had one)
    """
    parts = section_num.prefix.split(".")
    parts[-1] = str(int(parts[-1]) - 1)
    result = ".".join(parts)
    if section_num.has_trailing_dot:
        result += "."
    return result


def renumber_headings_after(
    lines: list[str],
    start_line: int,
    heading_level: int,
    increment: bool = True,
) -> list[str]:
    """Renumber all numbered headings at the given level after start_line.

    Only renumbers headings at exactly the same level.
    Stops when encountering a heading at a higher level (lower number).

    Args:
        lines: All lines of the file
        start_line: Line number to start renumbering from (inclusive)
        heading_level: The heading level to renumber (1-6)
        increment: True to increment numbers, False to decrement

    Returns:
        New list of lines with renumbered headings
    """
    new_lines = lines.copy()

    for i in range(start_line, len(new_lines)):
        level = get_heading_level(new_lines[i])
        if level is None:
            continue

        # Stop if we hit a higher-level heading (parent section ended)
        if level < heading_level:
            break

        # Only renumber headings at the exact same level
        if level != heading_level:
            continue

        section_num = parse_section_number(new_lines[i])
        if section_num is None:
            continue

        # Calculate new number
        if increment:
            new_num = increment_section_number(section_num)
        else:
            new_num = decrement_section_number(section_num)

        # Replace the number in the heading
        new_lines[i] = re.sub(
            r"^(#{1,6}\s+)\d+(?:\.\d+)*\.?\s+",
            f"\\g<1>{new_num} ",
            new_lines[i],
        )

    return new_lines


async def load_markdown_file(
    file_path: Path,
    filename: str,
) -> MarkdownFileContext | str:
    """Load a markdown file and prepare it for section operations.

    Handles file reading, line ending detection, CRLF normalization,
    and heading extraction.

    Args:
        file_path: Absolute path to the file
        filename: Original filename for error messages

    Returns:
        MarkdownFileContext on success, or error message string on failure
    """
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
        return f"Error: No headings found in '{filename}'. Cannot manipulate sections in files without headings."

    return MarkdownFileContext(
        file_path=file_path,
        filename=filename,
        lines=lines,
        line_ending=line_ending,
        headings=headings,
    )


def find_and_validate_section(
    ctx: MarkdownFileContext,
    target_heading: str,
) -> SectionMatchResult:
    """Find a section by heading with fuzzy matching and validate the match.

    Handles:
    - Finding the best matching heading
    - Detecting "no match" with helpful suggestions
    - Detecting ambiguous matches
    - Finding section boundaries

    Args:
        ctx: The loaded markdown file context
        target_heading: The heading to search for (fuzzy matched)

    Returns:
        SectionMatchResult with either success data or error message
    """
    # Find matching heading
    match_result = find_matching_heading(ctx.headings, target_heading)

    if match_result is None:
        # No match found - provide helpful error with available headings
        available = [h.text for h in ctx.headings]
        close = find_close_matches(ctx.headings, target_heading)

        if close and close[0].confidence >= 0.6:
            # There are close matches but below threshold
            close_display = ", ".join(
                f"'{m.heading_text}' ({int(m.confidence * 100)}%)" for m in close
            )
            return SectionMatchResult(
                error=f"No section matching '{target_heading}' found in {ctx.filename}. "
                f"Did you mean: {close_display}"
            )
        else:
            # List available headings
            available_display = ", ".join(available[:5])
            if len(available) > 5:
                available_display += f" (+{len(available) - 5} more)"
            return SectionMatchResult(
                error=f"No section matching '{target_heading}' found in {ctx.filename}. "
                f"Available headings: {available_display}"
            )

    matched = match_result.heading
    confidence = match_result.confidence

    # Check for ambiguous matches (multiple close matches)
    if confidence < 1.0:
        close = find_close_matches(
            ctx.headings, target_heading, threshold=confidence - 0.1
        )
        if len(close) > 1 and close[1].confidence >= confidence - 0.05:
            # Second match is very close to first - ambiguous
            close_display = ", ".join(
                f"'{m.heading_text}' ({int(m.confidence * 100)}%)" for m in close[:3]
            )
            return SectionMatchResult(
                error=f"Multiple sections closely match '{target_heading}' in {ctx.filename}: "
                f"{close_display}. Please be more specific."
            )

    # Find section boundaries
    start_line, end_line = find_section_bounds(
        ctx.lines, matched.line_number, matched.level
    )

    return SectionMatchResult(
        heading=matched,
        confidence=confidence,
        start_line=start_line,
        end_line=end_line,
    )


async def write_markdown_file(ctx: MarkdownFileContext, new_lines: list[str]) -> None:
    """Write modified lines back to a markdown file.

    Args:
        ctx: The markdown file context (provides path and line ending)
        new_lines: The new lines to write
    """
    new_content = ctx.line_ending.join(new_lines)
    # Ensure file ends with a newline (standard for text files, prevents corruption
    # when multiple operations are performed sequentially)
    if new_content and not new_content.endswith(ctx.line_ending):
        new_content += ctx.line_ending
    async with aiofiles.open(ctx.file_path, "w", encoding="utf-8", newline="") as f:
        await f.write(new_content)
