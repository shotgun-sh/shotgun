"""Pydantic models for markdown tools."""

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
