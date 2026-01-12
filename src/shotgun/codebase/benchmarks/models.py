"""Pydantic models for benchmark system.

This module contains all data models used by the benchmark system.
"""

from __future__ import annotations

import statistics
from enum import StrEnum

from pydantic import BaseModel, Field

from shotgun.codebase.core.metrics_types import IndexingMetrics


class BenchmarkMode(StrEnum):
    """Execution mode for benchmarks."""

    PARALLEL = "parallel"
    SEQUENTIAL = "sequential"


class OutputFormat(StrEnum):
    """Output format for benchmark results."""

    JSON = "json"
    MARKDOWN = "markdown"


class BenchmarkConfig(BaseModel):
    """Configuration for benchmark execution."""

    mode: BenchmarkMode = BenchmarkMode.PARALLEL
    worker_count: int | None = None
    iterations: int = 1
    warmup_iterations: int = 0
    collect_file_metrics: bool = True
    collect_worker_metrics: bool = True


class BenchmarkRun(BaseModel):
    """Results from a single benchmark run."""

    run_id: int
    is_warmup: bool
    metrics: IndexingMetrics


class BenchmarkResults(BaseModel):
    """Complete results from benchmark execution."""

    codebase_name: str
    codebase_path: str
    config: BenchmarkConfig
    warmup_runs: list[BenchmarkRun] = Field(default_factory=list)
    measured_runs: list[BenchmarkRun] = Field(default_factory=list)

    # Aggregate statistics (calculated after runs)
    avg_duration_seconds: float = 0.0
    min_duration_seconds: float = 0.0
    max_duration_seconds: float = 0.0
    std_dev_seconds: float = 0.0
    avg_throughput: float = 0.0
    avg_memory_mb: float = 0.0

    # Comparison data
    baseline_duration: float | None = None
    speedup_factor: float | None = None
    efficiency: float | None = None

    def add_run(self, run: BenchmarkRun) -> None:
        """Add a benchmark run to results.

        Args:
            run: Benchmark run to add
        """
        if run.is_warmup:
            self.warmup_runs.append(run)
        else:
            self.measured_runs.append(run)

    def calculate_statistics(self) -> None:
        """Calculate aggregate statistics from measured runs."""
        if not self.measured_runs:
            return

        durations = [r.metrics.total_duration_seconds for r in self.measured_runs]
        throughputs = [r.metrics.avg_throughput for r in self.measured_runs]
        memories = [r.metrics.peak_memory_mb for r in self.measured_runs]

        self.avg_duration_seconds = statistics.mean(durations)
        self.min_duration_seconds = min(durations)
        self.max_duration_seconds = max(durations)
        self.std_dev_seconds = (
            statistics.stdev(durations) if len(durations) > 1 else 0.0
        )
        self.avg_throughput = statistics.mean(throughputs)
        self.avg_memory_mb = statistics.mean(memories)

        # Calculate efficiency if parallel mode with known worker count
        if (
            self.config.mode == BenchmarkMode.PARALLEL
            and self.config.worker_count
            and self.baseline_duration
        ):
            speedup = self.baseline_duration / self.avg_duration_seconds
            self.speedup_factor = speedup
            self.efficiency = speedup / self.config.worker_count

    def get_last_metrics(self) -> IndexingMetrics | None:
        """Get metrics from the last measured run.

        Returns:
            IndexingMetrics from last run, or None if no runs
        """
        if self.measured_runs:
            return self.measured_runs[-1].metrics
        return None


class MetricsDisplayOptions(BaseModel):
    """Options for controlling metrics display."""

    show_phase_metrics: bool = True
    show_worker_metrics: bool = False
    show_file_metrics: bool = False
    show_summary_only: bool = False
    top_n_files: int | None = None
    min_file_duration_ms: float | None = None
