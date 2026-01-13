"""Utility functions for markdown parsing and manipulation."""

import re
from difflib import SequenceMatcher

from .models import (
    CloseMatch,
    HeadingList,
    HeadingMatch,
    MarkdownHeading,
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
