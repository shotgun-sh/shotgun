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
