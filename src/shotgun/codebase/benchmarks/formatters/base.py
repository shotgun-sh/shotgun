"""Base classes and protocols for formatters.

This module provides the Protocol interface that all formatters implement.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from shotgun.codebase.benchmarks.models import (
        BenchmarkResults,
        MetricsDisplayOptions,
    )


class ResultFormatter(Protocol):
    """Protocol for formatting benchmark results."""

    def format_results(
        self,
        results: BenchmarkResults,
        options: MetricsDisplayOptions,
    ) -> str:
        """Format benchmark results for display.

        Args:
            results: Benchmark results to format
            options: Display options

        Returns:
            Formatted string ready for output
        """
        ...
