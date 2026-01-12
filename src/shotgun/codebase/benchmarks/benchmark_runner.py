"""Benchmark runner for codebase indexing performance analysis.

This module provides the BenchmarkRunner class for running benchmark iterations
and collecting performance statistics.
"""

from __future__ import annotations

import gc
import hashlib
import json
import shutil
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from shotgun.codebase.benchmarks.models import (
    BenchmarkConfig,
    BenchmarkMode,
    BenchmarkResults,
    BenchmarkRun,
)
from shotgun.codebase.core import Ingestor, SimpleGraphBuilder
from shotgun.codebase.core.kuzu_compat import get_kuzu
from shotgun.codebase.core.metrics_collector import MetricsCollector
from shotgun.codebase.core.parser_loader import load_parsers
from shotgun.logging_config import get_logger
from shotgun.sdk.services import get_codebase_service
from shotgun.utils.file_system_utils import get_shotgun_home

logger = get_logger(__name__)


def _compute_graph_id(codebase_path: Path) -> str:
    """Compute a unique graph ID from the codebase path.

    Args:
        codebase_path: Path to the codebase

    Returns:
        A 12-character hex string identifying this codebase
    """
    return hashlib.sha256(str(codebase_path).encode()).hexdigest()[:12]


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
            mode=BenchmarkMode.PARALLEL if parallel else BenchmarkMode.SEQUENTIAL,
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

        # Register the codebase so it persists after benchmark
        await self._register_codebase()

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
        # Create metrics collector
        metrics_collector = MetricsCollector(
            codebase_name=self.codebase_name,
            collect_file_metrics=self.collect_file_metrics,
            collect_worker_metrics=self.collect_worker_metrics,
        )

        # Generate unique graph ID for this run
        graph_id = _compute_graph_id(self.codebase_path)

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
        graph_id = _compute_graph_id(self.codebase_path)

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

    async def _register_codebase(self) -> None:
        """Register the codebase so it appears in `shotgun codebase list`.

        This creates a Project node in the database with metadata that
        identifies the indexed codebase.
        """
        graph_id = _compute_graph_id(self.codebase_path)
        graph_path = self._storage_dir / f"{graph_id}.kuzu"

        if not graph_path.exists():
            logger.warning("Cannot register codebase: database not found")
            return

        kuzu = get_kuzu()
        db = kuzu.Database(str(graph_path))
        conn = kuzu.Connection(db)

        try:
            # Check if Project node already exists
            result = conn.execute("MATCH (p:Project) RETURN p.graph_id LIMIT 1")
            if result.has_next():
                logger.debug("Project node already exists, skipping registration")
                return

            # Create Project node with metadata
            current_time = int(time.time())
            conn.execute(
                """
                CREATE (p:Project {
                    name: $name,
                    repo_path: $repo_path,
                    graph_id: $graph_id,
                    created_at: $created_at,
                    updated_at: $updated_at,
                    schema_version: $schema_version,
                    build_options: $build_options,
                    indexed_from_cwds: $indexed_from_cwds
                })
                """,
                {
                    "name": self.codebase_name,
                    "repo_path": str(self.codebase_path),
                    "graph_id": graph_id,
                    "created_at": current_time,
                    "updated_at": current_time,
                    "schema_version": "1.0.0",
                    "build_options": json.dumps({}),
                    "indexed_from_cwds": json.dumps([str(Path.cwd())]),
                },
            )
            logger.info(
                f"Registered codebase '{self.codebase_name}' with graph_id: {graph_id}"
            )
        finally:
            del conn
            del db
