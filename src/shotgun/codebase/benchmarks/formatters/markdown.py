"""Markdown formatter for benchmark results.

This module provides the MarkdownFormatter class for displaying benchmark results
as GitHub-compatible markdown.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from shotgun.codebase.benchmarks.models import (
        BenchmarkResults,
        MetricsDisplayOptions,
    )


class MarkdownFormatter:
    """Format benchmark results as GitHub-compatible markdown."""

    def format_results(
        self,
        results: BenchmarkResults,
        options: MetricsDisplayOptions,
    ) -> str:
        """Format benchmark results as markdown.

        Args:
            results: Benchmark results to format
            options: Display options

        Returns:
            Markdown string
        """
        lines = []

        # Header
        lines.append(f"# Indexing Benchmark: {results.codebase_name}")
        lines.append("")
        lines.append(f"**Path:** `{results.codebase_path}`")

        mode = results.config.mode.capitalize()
        worker_info = ""
        if results.config.mode == "parallel":
            worker_count = results.config.worker_count or "auto"
            worker_info = f" ({worker_count} workers)"
        lines.append(f"**Mode:** {mode}{worker_info}")
        lines.append(
            f"**Iterations:** {results.config.iterations} ({results.config.warmup_iterations} warmup)"
        )
        lines.append("")

        # Summary statistics
        lines.append("## Summary")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")

        if results.config.iterations > 1:
            lines.append(f"| Duration (avg) | {results.avg_duration_seconds:.2f}s |")
            lines.append(f"| Duration (min) | {results.min_duration_seconds:.2f}s |")
            lines.append(f"| Duration (max) | {results.max_duration_seconds:.2f}s |")
            lines.append(f"| Duration (std dev) | {results.std_dev_seconds:.2f}s |")
        else:
            lines.append(f"| Duration | {results.avg_duration_seconds:.2f}s |")

        lines.append(f"| Throughput | {results.avg_throughput:.1f} files/s |")
        lines.append(f"| Peak Memory | {results.avg_memory_mb:.1f} MB |")

        metrics = results.get_last_metrics()
        if metrics:
            lines.append(f"| Files Processed | {metrics.total_files:,} |")
            lines.append(f"| Nodes Created | {metrics.total_nodes:,} |")
            lines.append(f"| Relationships | {metrics.total_relationships:,} |")

        if results.efficiency:
            lines.append(
                f"| Parallelism Efficiency | {results.efficiency * 100:.0f}% |"
            )
        if results.speedup_factor:
            lines.append(f"| Speedup | {results.speedup_factor:.2f}x |")

        lines.append("")

        # Phase breakdown
        if metrics and options.show_phase_metrics and not options.show_summary_only:
            lines.append("## Phase Breakdown")
            lines.append("")
            lines.append("| Phase | Duration | Items | Throughput | Memory |")
            lines.append("|-------|----------|-------|------------|--------|")

            for name, phase in metrics.phase_metrics.items():
                lines.append(
                    f"| {name} | {phase.duration_seconds:.2f}s | "
                    f"{phase.items_processed} | {phase.throughput:.1f}/s | "
                    f"{phase.memory_mb:.1f} MB |"
                )

            lines.append("")

        # File metrics
        if (
            metrics
            and options.show_file_metrics
            and metrics.file_metrics
            and not options.show_summary_only
        ):
            file_metrics = sorted(
                metrics.file_metrics,
                key=lambda f: f.parse_time_ms,
                reverse=True,
            )
            if options.top_n_files:
                file_metrics = file_metrics[: options.top_n_files]

            if file_metrics:
                title = "File Metrics"
                if options.top_n_files:
                    title = f"Top {len(file_metrics)} Slowest Files"

                lines.append(f"## {title}")
                lines.append("")
                lines.append("| File | Language | Size | Duration | Definitions |")
                lines.append("|------|----------|------|----------|-------------|")

                for f in file_metrics:
                    size_kb = f.file_size_bytes / 1024
                    lines.append(
                        f"| `{f.file_path}` | {f.language} | "
                        f"{size_kb:.1f} KB | {f.parse_time_ms:.1f}ms | "
                        f"{f.definitions_extracted} |"
                    )

                lines.append("")

        return "\n".join(lines)
