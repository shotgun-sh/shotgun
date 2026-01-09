"""Thread-safe metrics collector for indexing operations.

This module provides the MetricsCollector class for tracking performance
metrics during codebase indexing, including phase timing, memory usage,
and optional per-file and per-worker metrics.
"""

import csv
import threading
import time
import uuid
from pathlib import Path

import psutil

from shotgun.codebase.core.metrics_types import (
    FileParseMetrics,
    IndexingMetrics,
    IndexingPhase,
    PhaseMetrics,
    WorkerMetrics,
)


class MetricsCollector:
    """Thread-safe metrics collector for indexing operations.

    Collects performance metrics at multiple granularities:
    - Phase-level: timing and throughput for each indexing phase
    - Worker-level: per-worker statistics (optional, for parallel execution)
    - File-level: per-file parsing metrics (optional)

    All collection methods are thread-safe using a lock.
    """

    def __init__(
        self,
        codebase_name: str,
        collect_file_metrics: bool = True,
        collect_worker_metrics: bool = True,
    ) -> None:
        """Initialize the metrics collector.

        Args:
            codebase_name: Name of the codebase being indexed
            collect_file_metrics: Whether to collect per-file metrics
            collect_worker_metrics: Whether to collect per-worker metrics
        """
        self._lock = threading.Lock()
        self._session_id = str(uuid.uuid4())
        self._codebase_name = codebase_name
        self._collect_file_metrics = collect_file_metrics
        self._collect_worker_metrics = collect_worker_metrics

        # Phase tracking
        self._phase_starts: dict[str, tuple[float, float]] = {}  # (time, memory)
        self._phase_metrics: dict[str, PhaseMetrics] = {}

        # File metrics (optional)
        self._file_metrics: list[FileParseMetrics] = []

        # Worker metrics (optional)
        self._worker_metrics: dict[int, WorkerMetrics] = {}

        # Session timing
        self._session_start = time.perf_counter()
        self._session_start_timestamp = time.time()

        # Aggregates (set during flush phases)
        self._total_nodes = 0
        self._total_relationships = 0
        self._total_files = 0

    def _get_memory_mb(self) -> float:
        """Get current RSS memory in MB (cross-platform).

        Returns:
            Current memory usage in megabytes, or 0.0 if unavailable.
        """
        try:
            process = psutil.Process()
            rss_bytes: int = process.memory_info().rss
            return float(rss_bytes) / 1024 / 1024
        except Exception:
            return 0.0

    def start_phase(self, phase: IndexingPhase | str) -> None:
        """Mark the start of a processing phase.

        Args:
            phase: The indexing phase (use IndexingPhase enum)
        """
        phase_name = str(phase)
        with self._lock:
            start_time = time.perf_counter()
            start_memory = self._get_memory_mb()
            self._phase_starts[phase_name] = (start_time, start_memory)

    def end_phase(self, phase: IndexingPhase | str, items_processed: int) -> None:
        """Mark the end of a processing phase.

        Args:
            phase: The indexing phase (use IndexingPhase enum)
            items_processed: Number of items processed in this phase
        """
        phase_name = str(phase)
        end_time = time.perf_counter()
        end_memory = self._get_memory_mb()

        with self._lock:
            if phase_name not in self._phase_starts:
                return

            start_time, start_memory = self._phase_starts[phase_name]
            duration = end_time - start_time
            peak_memory = max(start_memory, end_memory)

            # Calculate throughput (avoid division by zero)
            throughput = items_processed / duration if duration > 0 else 0.0

            # Create phase metrics
            self._phase_metrics[phase_name] = PhaseMetrics(
                phase_name=phase_name,
                start_time=self._session_start_timestamp
                + (start_time - self._session_start),
                end_time=self._session_start_timestamp
                + (end_time - self._session_start),
                duration_seconds=duration,
                items_processed=items_processed,
                throughput=throughput,
                memory_mb=peak_memory,
                worker_count=None,
                worker_metrics=None,
            )

            # Track files for definitions phase
            if phase_name == IndexingPhase.DEFINITIONS:
                self._total_files = items_processed

    def record_file_parse(self, metrics: FileParseMetrics) -> None:
        """Record metrics for a single file parse.

        Args:
            metrics: File parsing metrics
        """
        if not self._collect_file_metrics:
            return

        with self._lock:
            self._file_metrics.append(metrics)

    def record_worker_metrics(self, worker_id: int, metrics: WorkerMetrics) -> None:
        """Record metrics for a worker.

        Args:
            worker_id: Unique worker identifier
            metrics: Worker performance metrics
        """
        if not self._collect_worker_metrics:
            return

        with self._lock:
            self._worker_metrics[worker_id] = metrics

    def set_totals(self, nodes: int, relationships: int) -> None:
        """Set the total node and relationship counts.

        Args:
            nodes: Total number of nodes created
            relationships: Total number of relationships created
        """
        with self._lock:
            self._total_nodes = nodes
            self._total_relationships = relationships

    def get_metrics(self) -> IndexingMetrics:
        """Get complete metrics for the indexing session.

        Returns:
            Complete indexing metrics including all phases and aggregates.
        """
        with self._lock:
            total_duration = time.perf_counter() - self._session_start

            # Calculate average throughput from definitions phase
            avg_throughput = 0.0
            definitions_key = str(IndexingPhase.DEFINITIONS)
            if definitions_key in self._phase_metrics:
                avg_throughput = self._phase_metrics[definitions_key].throughput

            # Get peak memory across all phases
            peak_memory = max(
                (pm.memory_mb for pm in self._phase_metrics.values()),
                default=self._get_memory_mb(),
            )

            # Calculate parallelism efficiency if worker metrics available
            parallelism_efficiency = None
            if self._worker_metrics:
                worker_count = len(self._worker_metrics)
                if worker_count > 1:
                    # Efficiency = actual speedup / ideal speedup
                    # For now, use balanced work distribution as proxy
                    files_per_worker = [
                        w.files_processed for w in self._worker_metrics.values()
                    ]
                    if files_per_worker:
                        avg_files = sum(files_per_worker) / len(files_per_worker)
                        max_files = max(files_per_worker)
                        if max_files > 0:
                            parallelism_efficiency = avg_files / max_files

            return IndexingMetrics(
                session_id=self._session_id,
                codebase_name=self._codebase_name,
                total_duration_seconds=total_duration,
                phase_metrics=dict(self._phase_metrics),
                file_metrics=list(self._file_metrics),
                total_files=self._total_files,
                total_nodes=self._total_nodes,
                total_relationships=self._total_relationships,
                avg_throughput=avg_throughput,
                peak_memory_mb=peak_memory,
                parallelism_efficiency=parallelism_efficiency,
            )

    def export_json(self, path: Path) -> None:
        """Export metrics to JSON file.

        Args:
            path: Path to write JSON file
        """
        metrics = self.get_metrics()
        path.write_text(metrics.model_dump_json(indent=2))

    def export_csv(self, path: Path) -> None:
        """Export metrics to CSV file.

        Exports phase metrics and optionally file metrics as separate sections.

        Args:
            path: Path to write CSV file
        """
        metrics = self.get_metrics()

        with path.open("w", newline="") as f:
            writer = csv.writer(f)

            # Header section
            writer.writerow(["# Indexing Metrics"])
            writer.writerow(["Session ID", metrics.session_id])
            writer.writerow(["Codebase", metrics.codebase_name])
            writer.writerow(
                ["Total Duration (s)", f"{metrics.total_duration_seconds:.2f}"]
            )
            writer.writerow(["Total Files", metrics.total_files])
            writer.writerow(["Total Nodes", metrics.total_nodes])
            writer.writerow(["Total Relationships", metrics.total_relationships])
            writer.writerow(["Peak Memory (MB)", f"{metrics.peak_memory_mb:.1f}"])
            writer.writerow([])

            # Phase metrics
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
            for phase in metrics.phase_metrics.values():
                writer.writerow(
                    [
                        phase.phase_name,
                        f"{phase.duration_seconds:.3f}",
                        phase.items_processed,
                        f"{phase.throughput:.1f}",
                        f"{phase.memory_mb:.1f}",
                    ]
                )
            writer.writerow([])

            # File metrics (if collected)
            if metrics.file_metrics:
                writer.writerow(["# File Metrics"])
                writer.writerow(
                    [
                        "File",
                        "Language",
                        "Size (bytes)",
                        "Parse Time (ms)",
                        "AST Nodes",
                        "Definitions",
                        "Relationships",
                    ]
                )
                for fm in metrics.file_metrics:
                    writer.writerow(
                        [
                            fm.file_path,
                            fm.language,
                            fm.file_size_bytes,
                            f"{fm.parse_time_ms:.2f}",
                            fm.ast_nodes,
                            fm.definitions_extracted,
                            fm.relationships_found,
                        ]
                    )
