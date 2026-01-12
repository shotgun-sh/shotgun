"""JSON formatter for benchmark results.

This module provides the JsonFormatter class for displaying benchmark results
as JSON.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from shotgun.codebase.benchmarks.models import (
        BenchmarkResults,
        MetricsDisplayOptions,
    )


class JsonFormatter:
    """Format benchmark results as JSON."""

    def format_results(
        self,
        results: BenchmarkResults,
        options: MetricsDisplayOptions,
    ) -> str:
        """Format benchmark results as JSON.

        Args:
            results: Benchmark results to format
            options: Display options

        Returns:
            JSON string
        """
        data = {
            "codebase_name": results.codebase_name,
            "codebase_path": results.codebase_path,
            "config": {
                "mode": results.config.mode,
                "worker_count": results.config.worker_count,
                "iterations": results.config.iterations,
                "warmup_iterations": results.config.warmup_iterations,
            },
            "statistics": {
                "avg_duration_seconds": results.avg_duration_seconds,
                "min_duration_seconds": results.min_duration_seconds,
                "max_duration_seconds": results.max_duration_seconds,
                "std_dev_seconds": results.std_dev_seconds,
                "avg_throughput": results.avg_throughput,
                "avg_memory_mb": results.avg_memory_mb,
                "speedup_factor": results.speedup_factor,
                "efficiency": results.efficiency,
            },
            "runs": [],
        }

        # Add run data
        for run in results.measured_runs:
            run_data: dict[str, object] = {
                "run_id": run.run_id,
                "duration_seconds": run.metrics.total_duration_seconds,
                "total_files": run.metrics.total_files,
                "total_nodes": run.metrics.total_nodes,
                "total_relationships": run.metrics.total_relationships,
                "throughput": run.metrics.avg_throughput,
                "peak_memory_mb": run.metrics.peak_memory_mb,
            }

            # Add phase metrics
            if options.show_phase_metrics:
                phase_data: dict[str, dict[str, object]] = {}
                for name, phase in run.metrics.phase_metrics.items():
                    phase_data[name] = {
                        "duration_seconds": phase.duration_seconds,
                        "items_processed": phase.items_processed,
                        "throughput": phase.throughput,
                        "memory_mb": phase.memory_mb,
                    }
                run_data["phase_metrics"] = phase_data

            # Add file metrics
            if options.show_file_metrics and run.metrics.file_metrics:
                file_metrics_list = run.metrics.file_metrics
                if options.top_n_files:
                    file_metrics_list = sorted(
                        file_metrics_list,
                        key=lambda f: f.parse_time_ms,
                        reverse=True,
                    )[: options.top_n_files]

                run_data["file_metrics"] = [
                    {
                        "file_path": f.file_path,
                        "language": f.language,
                        "file_size_bytes": f.file_size_bytes,
                        "parse_time_ms": f.parse_time_ms,
                        "definitions_extracted": f.definitions_extracted,
                    }
                    for f in file_metrics_list
                ]

            runs_list: list[dict[str, object]] = data["runs"]  # type: ignore[assignment]
            runs_list.append(run_data)

        return json.dumps(data, indent=2)
