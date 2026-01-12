"""Result formatters for benchmark output.

This package provides formatters for displaying benchmark results in various
formats: JSON and Markdown.
"""

from shotgun.codebase.benchmarks.formatters.base import ResultFormatter
from shotgun.codebase.benchmarks.formatters.json_formatter import JsonFormatter
from shotgun.codebase.benchmarks.formatters.markdown import MarkdownFormatter

# Re-export MetricsDisplayOptions from models for convenience
from shotgun.codebase.benchmarks.models import MetricsDisplayOptions

__all__ = [
    "JsonFormatter",
    "MarkdownFormatter",
    "MetricsDisplayOptions",
    "ResultFormatter",
    "get_formatter",
]


def get_formatter(
    output_format: str,
) -> JsonFormatter | MarkdownFormatter:
    """Get appropriate formatter for output format.

    Args:
        output_format: Format name - "json" or "markdown"

    Returns:
        Formatter instance

    Raises:
        ValueError: If output format is unknown
    """
    formatters: dict[str, type[JsonFormatter | MarkdownFormatter]] = {
        "json": JsonFormatter,
        "markdown": MarkdownFormatter,
    }

    format_lower = output_format.lower()
    if format_lower not in formatters:
        raise ValueError(
            f"Unknown output format: {output_format}. "
            f"Valid formats: {', '.join(formatters.keys())}"
        )

    return formatters[format_lower]()
