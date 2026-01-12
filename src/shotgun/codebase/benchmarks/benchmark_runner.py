"""Benchmark runner for codebase indexing performance analysis.

This module provides the BenchmarkRunner class for running benchmark iterations
and collecting performance statistics.
"""

from __future__ import annotations

import gc
import shutil
import statistics
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from shotgun.codebase.core.metrics_collector import MetricsCollector
from shotgun.codebase.core.metrics_types import IndexingMetrics
from shotgun.logging_config import get_logger
from shotgun.sdk.services import get_codebase_service
from shotgun.utils.file_system_utils import get_shotgun_home

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class BenchmarkConfig:
    """Configuration for benchmark execution."""

    def __init__(
        self,
        mode: str = "parallel",
        worker_count: int | None = None,
        iterations: int = 1,
        warmup_iterations: int = 0,
        collect_file_metrics: bool = True,
        collect_worker_metrics: bool = True,
    ) -> None:
        """Initialize benchmark configuration.

        Args:
            mode: Execution mode - "parallel" or "sequential"
            worker_count: Number of workers for parallel mode (None = auto)
            iterations: Number of measured benchmark runs
            warmup_iterations: Number of warmup runs (not measured)
            collect_file_metrics: Whether to collect per-file metrics
            collect_worker_metrics: Whether to collect per-worker metrics
        """
        self.mode = mode
        self.worker_count = worker_count
        self.iterations = iterations
        self.warmup_iterations = warmup_iterations
        self.collect_file_metrics = collect_file_metrics
        self.collect_worker_metrics = collect_worker_metrics


class BenchmarkRun:
    """Results from a single benchmark run."""

    def __init__(
        self,
        run_id: int,
        is_warmup: bool,
        metrics: IndexingMetrics,
    ) -> None:
        """Initialize benchmark run results.

        Args:
            run_id: Run number (0 for first warmup, etc.)
            is_warmup: Whether this was a warmup run
            metrics: Collected metrics from this run
        """
        self.run_id = run_id
        self.is_warmup = is_warmup
        self.metrics = metrics


class BenchmarkResults:
    """Complete results from benchmark execution."""

    def __init__(
        self,
        codebase_name: str,
        codebase_path: str,
        config: BenchmarkConfig,
    ) -> None:
        """Initialize benchmark results.

        Args:
            codebase_name: Name of the benchmarked codebase
            codebase_path: Path to the codebase
            config: Benchmark configuration used
        """
        self.codebase_name = codebase_name
        self.codebase_path = codebase_path
        self.config = config
        self.warmup_runs: list[BenchmarkRun] = []
        self.measured_runs: list[BenchmarkRun] = []

        # Aggregate statistics (calculated after runs)
        self.avg_duration_seconds: float = 0.0
        self.min_duration_seconds: float = 0.0
        self.max_duration_seconds: float = 0.0
        self.std_dev_seconds: float = 0.0
        self.avg_throughput: float = 0.0
        self.avg_memory_mb: float = 0.0

        # Comparison data
        self.baseline_duration: float | None = None
        self.speedup_factor: float | None = None
        self.efficiency: float | None = None

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
            self.config.mode == "parallel"
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


class BenchmarkRunner:
    """Runs benchmark iterations and collects statistics."""

    def __init__(
        self,
        codebase_path: Path,
        codebase_name: str,
        iterations: int = 1,
        warmup_iterations: int = 0,
        parallel: bool = True,
        worker_count: int | None = None,
        collect_file_metrics: bool = True,
        collect_worker_metrics: bool = True,
        progress_callback: Callable[..., Any] | None = None,
    ) -> None:
        """Initialize benchmark runner.

        Args:
            codebase_path: Path to repository to benchmark
            codebase_name: Human-readable name for the codebase
            iterations: Number of measured benchmark runs
            warmup_iterations: Number of warmup runs (not measured)
            parallel: Whether to use parallel execution
            worker_count: Number of workers (None = auto)
            collect_file_metrics: Whether to collect per-file metrics
            collect_worker_metrics: Whether to collect per-worker metrics
            progress_callback: Optional callback for progress updates
        """
        self.codebase_path = codebase_path.resolve()
        self.codebase_name = codebase_name
        self.iterations = iterations
        self.warmup_iterations = warmup_iterations
        self.parallel = parallel
        self.worker_count = worker_count
        self.collect_file_metrics = collect_file_metrics
        self.collect_worker_metrics = collect_worker_metrics
        self.progress_callback = progress_callback

        # Configuration object
        self.config = BenchmarkConfig(
            mode="parallel" if parallel else "sequential",
            worker_count=worker_count,
            iterations=iterations,
            warmup_iterations=warmup_iterations,
            collect_file_metrics=collect_file_metrics,
            collect_worker_metrics=collect_worker_metrics,
        )

        # Storage for database operations
        self._storage_dir = get_shotgun_home() / "codebases"
        self._service = get_codebase_service(self._storage_dir)

    async def run(self) -> BenchmarkResults:
        """Run all benchmark iterations and return aggregated results.

        Returns:
            BenchmarkResults with all run data and statistics
        """
        results = BenchmarkResults(
            codebase_name=self.codebase_name,
            codebase_path=str(self.codebase_path),
            config=self.config,
        )

        # Run warmup iterations
        for i in range(self.warmup_iterations):
            logger.info(f"Running warmup iteration {i + 1}/{self.warmup_iterations}...")
            if self.progress_callback:
                self.progress_callback(
                    f"Warmup {i + 1}/{self.warmup_iterations}", None, None
                )

            run = await self._run_single_iteration(
                run_id=i,
                is_warmup=True,
            )
            results.add_run(run)
            await self._cleanup_database()

        # Run measured iterations
        for i in range(self.iterations):
            logger.info(f"Running benchmark iteration {i + 1}/{self.iterations}...")
            if self.progress_callback:
                self.progress_callback(
                    f"Benchmark {i + 1}/{self.iterations}", None, None
                )

            run = await self._run_single_iteration(
                run_id=i,
                is_warmup=False,
            )
            results.add_run(run)

            # Clean up between iterations (but not after the last one)
            if i < self.iterations - 1:
                await self._cleanup_database()

        # Calculate statistics
        results.calculate_statistics()

        logger.info(
            f"Benchmark complete: {self.iterations} iterations, "
            f"avg {results.avg_duration_seconds:.2f}s"
        )

        return results

    async def _run_single_iteration(
        self,
        run_id: int,
        is_warmup: bool,
    ) -> BenchmarkRun:
        """Run a single benchmark iteration.

        Args:
            run_id: Run number
            is_warmup: Whether this is a warmup run

        Returns:
            BenchmarkRun with collected metrics
        """
        from shotgun.codebase.core import Ingestor, SimpleGraphBuilder
        from shotgun.codebase.core.kuzu_compat import get_kuzu
        from shotgun.codebase.core.parser_loader import load_parsers

        # Create metrics collector
        metrics_collector = MetricsCollector(
            codebase_name=self.codebase_name,
            collect_file_metrics=self.collect_file_metrics,
            collect_worker_metrics=self.collect_worker_metrics,
        )

        # Generate unique graph ID for this run
        import hashlib

        graph_id = hashlib.sha256(str(self.codebase_path).encode()).hexdigest()[:12]

        # Create database
        kuzu = get_kuzu()
        graph_path = self._storage_dir / f"{graph_id}.kuzu"

        # Ensure clean state
        if graph_path.exists():
            if graph_path.is_dir():
                shutil.rmtree(graph_path)
            else:
                graph_path.unlink()
        wal_path = self._storage_dir / f"{graph_id}.kuzu.wal"
        if wal_path.exists():
            wal_path.unlink()

        # Create database and connection
        db = kuzu.Database(str(graph_path))
        conn = kuzu.Connection(db)

        # Load parsers
        parsers, queries = load_parsers()

        # Create ingestor and builder
        ingestor = Ingestor(conn)
        ingestor.create_schema()

        builder = SimpleGraphBuilder(
            ingestor=ingestor,
            repo_path=self.codebase_path,
            parsers=parsers,
            queries=queries,
            metrics_collector=metrics_collector,
            enable_parallel=self.parallel,
            progress_callback=None,  # Disable TUI progress in benchmark mode
        )

        # Run indexing
        await builder.run()

        # Get metrics
        metrics = metrics_collector.get_metrics()

        # Close connection
        del conn
        del db

        return BenchmarkRun(
            run_id=run_id,
            is_warmup=is_warmup,
            metrics=metrics,
        )

    async def _cleanup_database(self) -> None:
        """Delete database files and clear caches between runs."""
        import hashlib

        graph_id = hashlib.sha256(str(self.codebase_path).encode()).hexdigest()[:12]

        # Delete database file
        graph_path = self._storage_dir / f"{graph_id}.kuzu"
        if graph_path.exists():
            if graph_path.is_dir():
                shutil.rmtree(graph_path)
            else:
                graph_path.unlink()
            logger.debug(f"Deleted database: {graph_path}")

        # Delete WAL file
        wal_path = self._storage_dir / f"{graph_id}.kuzu.wal"
        if wal_path.exists():
            wal_path.unlink()
            logger.debug(f"Deleted WAL: {wal_path}")

        # Force garbage collection
        gc.collect()
