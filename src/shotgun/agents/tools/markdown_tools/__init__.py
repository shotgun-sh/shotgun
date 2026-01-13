"""Markdown manipulation tools for Pydantic AI agents."""

from .insert_section import insert_markdown_section
from .models import (
    CloseMatch,
    HeadingList,
    HeadingMatch,
    MarkdownFileContext,
    MarkdownHeading,
    SectionMatchResult,
    SectionNumber,
)
from .remove_section import remove_markdown_section
from .replace_section import replace_markdown_section
from .utils import (
    decrement_section_number,
    detect_line_ending,
    extract_headings,
    find_and_validate_section,
    find_close_matches,
    find_matching_heading,
    find_section_bounds,
    get_heading_level,
    increment_section_number,
    load_markdown_file,
    normalize_section_content,
    parse_section_number,
    renumber_headings_after,
    split_normalized_content,
    write_markdown_file,
)

__all__ = [
    # Tools
    "replace_markdown_section",
    "insert_markdown_section",
    "remove_markdown_section",
    # Models
    "MarkdownHeading",
    "HeadingList",
    "HeadingMatch",
    "CloseMatch",
    "SectionNumber",
    "MarkdownFileContext",
    "SectionMatchResult",
    # Utilities
    "get_heading_level",
    "extract_headings",
    "find_matching_heading",
    "find_close_matches",
    "find_section_bounds",
    "detect_line_ending",
    "normalize_section_content",
    "split_normalized_content",
    "parse_section_number",
    "increment_section_number",
    "decrement_section_number",
    "renumber_headings_after",
    "load_markdown_file",
    "find_and_validate_section",
    "write_markdown_file",
]
