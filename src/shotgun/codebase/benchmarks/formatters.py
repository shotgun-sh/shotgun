"""Result formatters for benchmark output.

This module provides formatters for displaying benchmark results in various
formats: text (Rich tables), JSON, CSV, and Markdown.
"""

from __future__ import annotations

import csv
import io
import json
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from shotgun.codebase.benchmarks.benchmark_runner import BenchmarkResults


class MetricsDisplayOptions:
    """Options for controlling metrics display."""

    def __init__(
        self,
        show_phase_metrics: bool = True,
        show_worker_metrics: bool = False,
        show_file_metrics: bool = False,
        show_summary_only: bool = False,
        top_n_files: int | None = None,
        min_file_duration_ms: float | None = None,
    ) -> None:
        """Initialize display options.

        Args:
            show_phase_metrics: Show phase breakdown table
            show_worker_metrics: Show per-worker statistics
            show_file_metrics: Show per-file details
            show_summary_only: Show only summary (hide detailed tables)
            top_n_files: Show only N slowest files
            min_file_duration_ms: Show only files slower than threshold
        """
        self.show_phase_metrics = show_phase_metrics
        self.show_worker_metrics = show_worker_metrics
        self.show_file_metrics = show_file_metrics
        self.show_summary_only = show_summary_only
        self.top_n_files = top_n_files
        self.min_file_duration_ms = min_file_duration_ms


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
        from rich.console import Console
        from rich.table import Table

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


def get_formatter(
    output_format: str,
) -> TextFormatter | JsonFormatter | CsvFormatter | MarkdownFormatter:
    """Get appropriate formatter for output format.

    Args:
        output_format: Format name - "text", "json", "csv", or "markdown"

    Returns:
        Formatter instance

    Raises:
        ValueError: If output format is unknown
    """
    formatters: dict[
        str, type[TextFormatter | JsonFormatter | CsvFormatter | MarkdownFormatter]
    ] = {
        "text": TextFormatter,
        "json": JsonFormatter,
        "csv": CsvFormatter,
        "markdown": MarkdownFormatter,
    }

    format_lower = output_format.lower()
    if format_lower not in formatters:
        raise ValueError(
            f"Unknown output format: {output_format}. "
            f"Valid formats: {', '.join(formatters.keys())}"
        )

    return formatters[format_lower]()
