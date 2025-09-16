"""Common models for CLI commands."""

from enum import Enum


class OutputFormat(str, Enum):
    """Output format options for CLI commands."""

    TEXT = "text"
    JSON = "json"
