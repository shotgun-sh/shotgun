"""CSV formatter for benchmark results.

This module provides the CsvFormatter class for displaying benchmark results
as CSV.
"""

from __future__ import annotations

import csv
import io
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from shotgun.codebase.benchmarks.models import (
        BenchmarkResults,
        MetricsDisplayOptions,
    )


class CsvFormatter:
    """Format benchmark results as CSV."""

    def format_results(
        self,
        results: BenchmarkResults,
        options: MetricsDisplayOptions,
    ) -> str:
        """Format benchmark results as CSV.

        Args:
            results: Benchmark results to format
            options: Display options

        Returns:
            CSV string
        """
        output = io.StringIO()
        writer = csv.writer(output)

        # Header section
        writer.writerow(["# Benchmark Results"])
        writer.writerow(["Codebase", results.codebase_name])
        writer.writerow(["Path", results.codebase_path])
        writer.writerow(["Mode", results.config.mode])
        writer.writerow(["Worker Count", results.config.worker_count or "auto"])
        writer.writerow(["Iterations", results.config.iterations])
        writer.writerow([])

        # Summary statistics
        writer.writerow(["# Summary Statistics"])
        writer.writerow(["Metric", "Value"])
        writer.writerow(["Average Duration (s)", f"{results.avg_duration_seconds:.3f}"])
        writer.writerow(["Min Duration (s)", f"{results.min_duration_seconds:.3f}"])
        writer.writerow(["Max Duration (s)", f"{results.max_duration_seconds:.3f}"])
        writer.writerow(["Std Dev (s)", f"{results.std_dev_seconds:.3f}"])
        writer.writerow(
            ["Average Throughput (files/s)", f"{results.avg_throughput:.1f}"]
        )
        writer.writerow(["Average Memory (MB)", f"{results.avg_memory_mb:.1f}"])
        writer.writerow([])

        # Phase metrics from last run
        metrics = results.get_last_metrics()
        if metrics and options.show_phase_metrics:
            writer.writerow(["# Phase Metrics"])
            writer.writerow(
                [
                    "Phase",
                    "Duration (s)",
                    "Items",
                    "Throughput (items/s)",
                    "Memory (MB)",
                ]
            )
            for name, phase in metrics.phase_metrics.items():
                writer.writerow(
                    [
                        name,
                        f"{phase.duration_seconds:.3f}",
                        phase.items_processed,
                        f"{phase.throughput:.1f}",
                        f"{phase.memory_mb:.1f}",
                    ]
                )
            writer.writerow([])

        # File metrics
        if metrics and options.show_file_metrics and metrics.file_metrics:
            writer.writerow(["# File Metrics"])
            writer.writerow(
                ["File", "Language", "Size (bytes)", "Duration (ms)", "Definitions"]
            )

            file_metrics = sorted(
                metrics.file_metrics,
                key=lambda f: f.parse_time_ms,
                reverse=True,
            )
            if options.top_n_files:
                file_metrics = file_metrics[: options.top_n_files]

            for f in file_metrics:
                writer.writerow(
                    [
                        f.file_path,
                        f.language,
                        f.file_size_bytes,
                        f"{f.parse_time_ms:.2f}",
                        f.definitions_extracted,
                    ]
                )

        return output.getvalue()
