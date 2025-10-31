"""Common models for CLI commands."""

from enum import StrEnum


class OutputFormat(StrEnum):
    """Output format options for CLI commands."""

    TEXT = "text"
    JSON = "json"
    MARKDOWN = "markdown"
