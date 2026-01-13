"""Pydantic models for markdown tools."""

from pathlib import Path

from pydantic import BaseModel


class MarkdownHeading(BaseModel):
    """Represents a heading found in a Markdown file."""

    line_number: int
    text: str
    level: int

    @property
    def normalized_text(self) -> str:
        """Return heading text without # prefix, stripped and lowercased."""
        return self.text.lstrip("#").strip().lower()


HeadingList = list[MarkdownHeading]


class HeadingMatch(BaseModel):
    """Result of a successful heading match."""

    heading: MarkdownHeading
    confidence: float


class CloseMatch(BaseModel):
    """A close match result for error messages."""

    heading_text: str
    confidence: float


class SectionNumber(BaseModel):
    """Parsed section number from a heading.

    Examples:
        - "## 3. Title" -> prefix="3", has_trailing_dot=True
        - "### 4.4 Title" -> prefix="4.4", has_trailing_dot=False
        - "#### 1.2.3.4 Title" -> prefix="1.2.3.4", has_trailing_dot=False
    """

    prefix: str  # The number part, e.g., "4.4" or "3"
    has_trailing_dot: bool  # Whether it ends with a dot before the title


class MarkdownFileContext(BaseModel):
    """Context for a loaded markdown file ready for section operations.

    This encapsulates the common state needed by all section manipulation tools:
    file path, content split into lines, line ending style, and extracted headings.
    """

    file_path: Path
    filename: str  # Original filename for error messages
    lines: list[str]
    line_ending: str
    headings: HeadingList

    model_config = {"arbitrary_types_allowed": True}


class SectionMatchResult(BaseModel):
    """Result of finding and validating a section match.

    Either contains a successful match with the heading and bounds,
    or an error message explaining why the match failed.
    """

    # Success fields (all present when error is None)
    heading: MarkdownHeading | None = None
    confidence: float = 0.0
    start_line: int = 0
    end_line: int = 0

    # Error field (present when match failed)
    error: str | None = None

    @property
    def is_success(self) -> bool:
        """Return True if this is a successful match."""
        return self.error is None and self.heading is not None
