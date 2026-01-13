"""Markdown manipulation tools for Pydantic AI agents."""

from .insert_section import insert_markdown_section
from .models import CloseMatch, HeadingList, HeadingMatch, MarkdownHeading
from .replace_section import replace_markdown_section
from .utils import (
    detect_line_ending,
    extract_headings,
    find_close_matches,
    find_matching_heading,
    find_section_bounds,
    get_heading_level,
    normalize_section_content,
)

__all__ = [
    # Tools
    "replace_markdown_section",
    "insert_markdown_section",
    # Models
    "MarkdownHeading",
    "HeadingList",
    "HeadingMatch",
    "CloseMatch",
    # Utilities
    "get_heading_level",
    "extract_headings",
    "find_matching_heading",
    "find_close_matches",
    "find_section_bounds",
    "detect_line_ending",
    "normalize_section_content",
]
