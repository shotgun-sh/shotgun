"""Metrics exporters for saving benchmark results to files.

This module provides the MetricsExporter class for exporting benchmark
results to various file formats.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from shotgun.codebase.benchmarks.formatters import (
    JsonFormatter,
    MarkdownFormatter,
    MetricsDisplayOptions,
)
from shotgun.logging_config import get_logger

if TYPE_CHECKING:
    from shotgun.codebase.benchmarks.models import BenchmarkResults

logger = get_logger(__name__)


class MetricsExporter:
    """Export benchmark metrics to files."""

    def __init__(self) -> None:
        """Initialize metrics exporter."""
        self._format_map = {
            ".json": self._export_json,
            ".md": self._export_markdown,
            ".markdown": self._export_markdown,
        }

    def export(
        self,
        results: BenchmarkResults,
        filepath: Path | str,
        format: str | None = None,
        options: MetricsDisplayOptions | None = None,
    ) -> None:
        """Export benchmark results to file.

        The format is auto-detected from the file extension if not specified.

        Args:
            results: Benchmark results to export
            filepath: Path to export file
            format: Optional format override ("json", "markdown")
            options: Display options for controlling what to include

        Raises:
            ValueError: If format cannot be determined or is unsupported
            OSError: If file cannot be written
        """
        filepath = Path(filepath)
        options = options or MetricsDisplayOptions()

        # Determine format
        if format:
            format_lower = format.lower()
            if format_lower == "json":
                export_func = self._export_json
            elif format_lower in ("markdown", "md"):
                export_func = self._export_markdown
            else:
                raise ValueError(f"Unknown export format: {format}")
        else:
            # Auto-detect from extension
            suffix = filepath.suffix.lower()
            if suffix not in self._format_map:
                raise ValueError(
                    f"Cannot determine format from extension '{suffix}'. "
                    f"Supported extensions: {', '.join(self._format_map.keys())}. "
                    f"Or specify format explicitly."
                )
            export_func = self._format_map[suffix]

        # Ensure parent directory exists
        filepath.parent.mkdir(parents=True, exist_ok=True)

        # Export
        export_func(results, filepath, options)
        logger.info(f"Exported benchmark results to {filepath}")

    def _export_json(
        self,
        results: BenchmarkResults,
        filepath: Path,
        options: MetricsDisplayOptions,
    ) -> None:
        """Export results to JSON file.

        Args:
            results: Benchmark results
            filepath: Output path
            options: Display options
        """
        formatter = JsonFormatter()
        content = formatter.format_results(results, options)
        filepath.write_text(content)

    def _export_markdown(
        self,
        results: BenchmarkResults,
        filepath: Path,
        options: MetricsDisplayOptions,
    ) -> None:
        """Export results to Markdown file.

        Args:
            results: Benchmark results
            filepath: Output path
            options: Display options
        """
        formatter = MarkdownFormatter()
        content = formatter.format_results(results, options)
        filepath.write_text(content)
