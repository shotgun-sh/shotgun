"""Text formatter for benchmark results.

This module provides the TextFormatter class for displaying benchmark results
as human-readable text with Rich tables.
"""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

from rich.console import Console
from rich.table import Table

if TYPE_CHECKING:
    from shotgun.codebase.benchmarks.models import (
        BenchmarkResults,
        MetricsDisplayOptions,
    )


class TextFormatter:
    """Format benchmark results as human-readable text with Rich tables."""

    def format_results(
        self,
        results: BenchmarkResults,
        options: MetricsDisplayOptions,
    ) -> str:
        """Format benchmark results as text with tables.

        Args:
            results: Benchmark results to format
            options: Display options

        Returns:
            Formatted text string
        """
        output = io.StringIO()
        console = Console(file=output, force_terminal=False, width=120)

        # Header
        mode = results.config.mode.capitalize()
        worker_info = ""
        if results.config.mode == "parallel":
            worker_count = results.config.worker_count or "auto"
            worker_info = f" ({worker_count} workers)"

        console.print()
        console.print(
            f"[bold blue]=== Indexing Benchmark: {results.codebase_name} ===[/bold blue]"
        )
        console.print(f"Path: {results.codebase_path}")
        console.print(f"Mode: {mode}{worker_info}")
        console.print(
            f"Iterations: {results.config.iterations} ({results.config.warmup_iterations} warmup)"
        )
        console.print()

        # Get metrics from last run for detailed data
        metrics = results.get_last_metrics()

        # Phase breakdown table
        if options.show_phase_metrics and metrics and not options.show_summary_only:
            phase_table = Table(title="Phase Breakdown")
            phase_table.add_column("Phase", style="cyan")
            phase_table.add_column("Duration", justify="right")
            phase_table.add_column("Items", justify="right")
            phase_table.add_column("Throughput", justify="right")
            phase_table.add_column("Memory", justify="right")

            for phase_name, phase_metrics in metrics.phase_metrics.items():
                duration_str = f"{phase_metrics.duration_seconds:.2f}s"
                items_str = str(phase_metrics.items_processed)
                throughput_str = f"{phase_metrics.throughput:.1f}/s"
                memory_str = f"{phase_metrics.memory_mb:.1f} MB"

                phase_table.add_row(
                    phase_name,
                    duration_str,
                    items_str,
                    throughput_str,
                    memory_str,
                )

            console.print(phase_table)
            console.print()

        # Worker statistics table
        if options.show_worker_metrics and metrics and not options.show_summary_only:
            # Get worker metrics from the definitions phase
            definitions_phase = metrics.phase_metrics.get("definitions")
            if definitions_phase and definitions_phase.worker_metrics:
                worker_table = Table(title="Worker Statistics")
                worker_table.add_column("Worker", style="cyan")
                worker_table.add_column("Files", justify="right")
                worker_table.add_column("Nodes", justify="right")
                worker_table.add_column("Relationships", justify="right")
                worker_table.add_column("Duration", justify="right")
                worker_table.add_column("Throughput", justify="right")

                for (
                    worker_id,
                    worker_metrics,
                ) in definitions_phase.worker_metrics.items():
                    worker_table.add_row(
                        f"Worker {worker_id}",
                        str(worker_metrics.files_processed),
                        str(worker_metrics.nodes_created),
                        str(worker_metrics.relationships_created),
                        f"{worker_metrics.duration_seconds:.2f}s",
                        f"{worker_metrics.throughput:.1f}/s",
                    )

                console.print(worker_table)
                console.print()

        # File metrics table
        if (
            options.show_file_metrics
            and metrics
            and metrics.file_metrics
            and not options.show_summary_only
        ):
            # Sort by parse time (slowest first)
            sorted_files = sorted(
                metrics.file_metrics,
                key=lambda f: f.parse_time_ms,
                reverse=True,
            )

            # Apply filters
            if options.min_file_duration_ms:
                sorted_files = [
                    f
                    for f in sorted_files
                    if f.parse_time_ms >= options.min_file_duration_ms
                ]

            if options.top_n_files:
                sorted_files = sorted_files[: options.top_n_files]

            if sorted_files:
                title = "File Metrics"
                if options.top_n_files:
                    title = f"Top {len(sorted_files)} Slowest Files"

                file_table = Table(title=title)
                file_table.add_column("File", style="cyan", max_width=50)
                file_table.add_column("Language", justify="center")
                file_table.add_column("Size", justify="right")
                file_table.add_column("Duration", justify="right")
                file_table.add_column("Definitions", justify="right")

                for file_metric in sorted_files:
                    # Format file size
                    size_kb = file_metric.file_size_bytes / 1024
                    size_str = f"{size_kb:.1f} KB"

                    file_table.add_row(
                        file_metric.file_path,
                        file_metric.language,
                        size_str,
                        f"{file_metric.parse_time_ms:.1f}ms",
                        str(file_metric.definitions_extracted),
                    )

                console.print(file_table)
                console.print()

        # Summary statistics
        console.print("[bold]=== Summary ===[/bold]")

        if results.config.iterations > 1:
            console.print(
                f"Duration: {results.avg_duration_seconds:.2f}s (avg), "
                f"{results.min_duration_seconds:.2f}s (min), "
                f"{results.max_duration_seconds:.2f}s (max), "
                f"σ={results.std_dev_seconds:.2f}s"
            )
        else:
            console.print(f"Duration: {results.avg_duration_seconds:.2f}s")

        console.print(f"Throughput: {results.avg_throughput:.1f} files/s")
        console.print(f"Peak Memory: {results.avg_memory_mb:.1f} MB")

        if metrics:
            console.print(f"Files Processed: {metrics.total_files:,}")
            console.print(f"Nodes Created: {metrics.total_nodes:,}")
            console.print(f"Relationships: {metrics.total_relationships:,}")

        if results.efficiency:
            console.print(f"Parallelism Efficiency: {results.efficiency * 100:.0f}%")

        if results.speedup_factor:
            console.print(f"Speedup: {results.speedup_factor:.2f}x")

        console.print()
        console.print("[bold green]Benchmark complete[/bold green]")

        return output.getvalue()
