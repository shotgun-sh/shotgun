"""Parallel execution framework for file parsing.

This module provides the ParallelExecutor class for distributing
file parsing work across multiple processes using ProcessPoolExecutor.
"""

from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import TYPE_CHECKING

from shotgun.codebase.core.metrics_types import (
    FileParseResult,
    InheritanceData,
    ParallelExecutionResult,
    RawCallData,
    RelationshipData,
    WorkBatch,
    WorkerMetrics,
)
from shotgun.codebase.core.work_distributor import get_worker_count
from shotgun.codebase.core.worker import process_batch
from shotgun.logging_config import get_logger

if TYPE_CHECKING:
    from shotgun.codebase.core.metrics_collector import MetricsCollector

logger = get_logger(__name__)

# Default timeout for batch processing (5 minutes)
DEFAULT_BATCH_TIMEOUT_SECONDS = 300.0


class ParallelExecutor:
    """Executes file parsing in parallel across multiple processes.

    This class orchestrates parallel file parsing using ProcessPoolExecutor,
    aggregates results from all workers, and resolves deferred relationships
    that require knowledge of the complete function registry.

    Attributes:
        worker_count: Number of worker processes to use
        batch_timeout: Timeout in seconds for each batch
        metrics_collector: Optional collector for recording metrics
    """

    def __init__(
        self,
        worker_count: int | None = None,
        batch_timeout_seconds: float = DEFAULT_BATCH_TIMEOUT_SECONDS,
        metrics_collector: MetricsCollector | None = None,
    ) -> None:
        """Initialize the parallel executor.

        Args:
            worker_count: Number of workers. If None, uses get_worker_count().
            batch_timeout_seconds: Timeout for batch processing.
            metrics_collector: Optional collector for recording metrics.
        """
        self.worker_count = worker_count if worker_count is not None else get_worker_count()
        self.batch_timeout = batch_timeout_seconds
        self.metrics_collector = metrics_collector

        logger.debug(
            f"ParallelExecutor initialized: {self.worker_count} workers, "
            f"{self.batch_timeout}s batch timeout"
        )

    def execute(
        self,
        batches: list[WorkBatch],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> ParallelExecutionResult:
        """Execute batches in parallel and aggregate results.

        Args:
            batches: List of work batches to process
            progress_callback: Optional callback(completed, total) for progress

        Returns:
            ParallelExecutionResult with all results and resolved relationships
        """
        if not batches:
            logger.debug("No batches to process")
            return ParallelExecutionResult()

        start_time = time.perf_counter()
        total_batches = len(batches)
        all_results: list[FileParseResult] = []
        worker_stats: dict[int, dict[str, int | float]] = defaultdict(
            lambda: {
                "files_processed": 0,
                "nodes_created": 0,
                "relationships_created": 0,
                "duration_seconds": 0.0,
                "error_count": 0,
            }
        )

        logger.info(
            f"Starting parallel execution: {total_batches} batches, "
            f"{self.worker_count} workers"
        )

        # Execute batches in parallel
        completed = 0
        with ProcessPoolExecutor(max_workers=self.worker_count) as executor:
            # Submit all batches with worker_id based on submission order
            futures = {}
            for i, batch in enumerate(batches):
                worker_id = i % self.worker_count
                future = executor.submit(process_batch, batch, worker_id)
                futures[future] = (batch, worker_id)

            # Collect results as they complete
            for future in as_completed(futures):
                batch, worker_id = futures[future]

                try:
                    batch_results = future.result(timeout=self.batch_timeout)
                    all_results.extend(batch_results)

                    # Update worker stats
                    for result in batch_results:
                        worker_stats[worker_id]["files_processed"] += 1
                        worker_stats[worker_id]["nodes_created"] += len(result.nodes)
                        worker_stats[worker_id]["relationships_created"] += len(
                            result.relationships
                        )
                        if not result.success:
                            worker_stats[worker_id]["error_count"] += 1

                except TimeoutError:
                    logger.warning(
                        f"Batch {batch.batch_id} timed out after {self.batch_timeout}s"
                    )
                    # Create error results for timed-out tasks
                    for task in batch.tasks:
                        all_results.append(
                            FileParseResult(
                                task=task,
                                success=False,
                                error=f"Timeout after {self.batch_timeout}s",
                            )
                        )
                        worker_stats[worker_id]["error_count"] += 1

                except Exception as e:
                    logger.error(f"Batch {batch.batch_id} failed: {e}")
                    # Create error results for failed tasks
                    for task in batch.tasks:
                        all_results.append(
                            FileParseResult(
                                task=task,
                                success=False,
                                error=str(e),
                            )
                        )
                        worker_stats[worker_id]["error_count"] += 1

                completed += 1
                if progress_callback:
                    progress_callback(completed, total_batches)

        total_duration = time.perf_counter() - start_time
        logger.info(f"Parallel execution completed in {total_duration:.2f}s")

        # Aggregate registries from all results
        function_registry, simple_name_lookup = self._aggregate_registries(all_results)

        logger.info(
            f"Aggregated registry: {len(function_registry)} entries, "
            f"{len(simple_name_lookup)} unique names"
        )

        # Resolve deferred relationships
        resolved_relationships = self._resolve_all_relationships(
            all_results, function_registry, simple_name_lookup
        )

        logger.info(f"Resolved {len(resolved_relationships)} deferred relationships")

        # Calculate final stats
        successful_files = sum(1 for r in all_results if r.success)
        failed_files = sum(1 for r in all_results if not r.success)

        # Build worker metrics
        worker_metrics = {}
        for worker_id, stats in worker_stats.items():
            files = int(stats["files_processed"])
            nodes = int(stats["nodes_created"])
            rels = int(stats["relationships_created"])
            errors = int(stats["error_count"])
            duration = total_duration / max(1, self.worker_count)  # Estimate per worker
            worker_metrics[worker_id] = WorkerMetrics(
                worker_id=worker_id,
                files_processed=files,
                nodes_created=nodes,
                relationships_created=rels,
                duration_seconds=duration,
                throughput=files / duration if duration > 0 else 0,
                peak_memory_mb=0.0,  # Would need per-process memory tracking
                idle_time_seconds=0.0,  # Would need more detailed tracking
                error_count=errors,
            )

        return ParallelExecutionResult(
            results=all_results,
            resolved_relationships=resolved_relationships,
            function_registry=function_registry,
            simple_name_lookup=simple_name_lookup,
            total_files=len(all_results),
            successful_files=successful_files,
            failed_files=failed_files,
            total_duration_seconds=total_duration,
            worker_metrics=worker_metrics,
        )

    def _aggregate_registries(
        self,
        results: list[FileParseResult],
    ) -> tuple[dict[str, str], dict[str, list[str]]]:
        """Merge function_registry and simple_name_lookup from all workers.

        Args:
            results: Results from all workers

        Returns:
            Tuple of (function_registry, simple_name_lookup)
        """
        function_registry: dict[str, str] = {}
        simple_name_lookup: dict[str, list[str]] = defaultdict(list)

        for result in results:
            if not result.success:
                continue

            # Merge function registry
            function_registry.update(result.function_registry_entries)

            # Merge simple name lookup
            for name, qns in result.simple_name_entries.items():
                for qn in qns:
                    if qn not in simple_name_lookup[name]:
                        simple_name_lookup[name].append(qn)

        return function_registry, dict(simple_name_lookup)

    def _resolve_all_relationships(
        self,
        results: list[FileParseResult],
        function_registry: dict[str, str],
        simple_name_lookup: dict[str, list[str]],
    ) -> list[RelationshipData]:
        """Resolve all deferred relationships.

        Args:
            results: Results containing raw call and inheritance data
            function_registry: Merged registry from all workers
            simple_name_lookup: Merged name lookup from all workers

        Returns:
            List of resolved RelationshipData
        """
        resolved: list[RelationshipData] = []

        # Collect all raw data
        all_raw_calls: list[RawCallData] = []
        all_inheritance: list[InheritanceData] = []

        for result in results:
            if result.success:
                all_raw_calls.extend(result.raw_calls)
                all_inheritance.extend(result.inheritance_data)

        # Resolve call relationships
        call_rels = self._resolve_call_relationships(
            all_raw_calls, function_registry, simple_name_lookup
        )
        resolved.extend(call_rels)

        # Resolve inheritance relationships
        inheritance_rels = self._resolve_inheritance_relationships(
            all_inheritance, function_registry, simple_name_lookup
        )
        resolved.extend(inheritance_rels)

        return resolved

    def _resolve_call_relationships(
        self,
        raw_calls: list[RawCallData],
        function_registry: dict[str, str],
        simple_name_lookup: dict[str, list[str]],
    ) -> list[RelationshipData]:
        """Resolve raw calls to CALLS relationships.

        Args:
            raw_calls: List of unresolved call data
            function_registry: Complete function registry
            simple_name_lookup: Complete name lookup

        Returns:
            List of resolved CALLS relationships
        """
        resolved: list[RelationshipData] = []

        for call in raw_calls:
            # Get all possible callees
            possible_callees = simple_name_lookup.get(call.callee_name, [])
            if not possible_callees:
                continue

            # Calculate confidence scores and pick best match
            scored_callees = []
            for possible_qn in possible_callees:
                score = self._calculate_callee_confidence(
                    caller_qn=call.caller_qn,
                    callee_qn=possible_qn,
                    module_qn=call.module_qn,
                    object_name=call.object_name,
                    simple_name_lookup=simple_name_lookup,
                )
                scored_callees.append((possible_qn, score))

            # Sort by confidence and use highest match
            scored_callees.sort(key=lambda x: x[1], reverse=True)
            callee_qn, _confidence = scored_callees[0]

            # Get types from registry
            caller_type = function_registry.get(call.caller_qn)
            callee_type = function_registry.get(callee_qn)

            if caller_type and callee_type:
                resolved.append(
                    RelationshipData(
                        from_label=caller_type,
                        from_key="qualified_name",
                        from_value=call.caller_qn,
                        rel_type="CALLS",
                        to_label=callee_type,
                        to_key="qualified_name",
                        to_value=callee_qn,
                    )
                )

        return resolved

    def _calculate_callee_confidence(
        self,
        caller_qn: str,
        callee_qn: str,
        module_qn: str,
        object_name: str | None,
        simple_name_lookup: dict[str, list[str]],
    ) -> float:
        """Calculate confidence score for a potential callee match.

        Args:
            caller_qn: Qualified name of the calling function
            callee_qn: Qualified name of the potential callee
            module_qn: Qualified name of the current module
            object_name: Object name for method calls
            simple_name_lookup: Complete name lookup for disambiguation

        Returns:
            Confidence score between 0.0 and 1.0
        """
        score = 0.0

        # Module locality - functions in the same module are most likely
        if callee_qn.startswith(module_qn + "."):
            score += 0.5

            # Even higher if in the same class
            caller_parts = caller_qn.split(".")
            callee_parts = callee_qn.split(".")
            if len(caller_parts) >= 3 and len(callee_parts) >= 3:
                if caller_parts[:-1] == callee_parts[:-1]:
                    score += 0.2

        # Package locality
        elif "." in module_qn:
            package = module_qn.rsplit(".", 1)[0]
            if callee_qn.startswith(package + "."):
                score += 0.3

        # Object/class match for method calls
        if object_name:
            callee_parts = callee_qn.split(".")
            if len(callee_parts) >= 2:
                class_name = callee_parts[-2]
                if class_name.lower() == object_name.lower():
                    score += 0.3
                elif object_name == "self" and callee_qn.startswith(
                    caller_qn.rsplit(".", 1)[0]
                ):
                    score += 0.4

        # Standard library boost
        if callee_qn.startswith(("builtins.", "typing.", "collections.")):
            score += 0.1

        # Name uniqueness boost
        callee_simple_name = callee_qn.split(".")[-1]
        possible_count = len(simple_name_lookup.get(callee_simple_name, []))
        if possible_count == 1:
            score += 0.2
        elif possible_count <= 3:
            score += 0.1

        return min(score, 1.0)

    def _resolve_inheritance_relationships(
        self,
        inheritance_data: list[InheritanceData],
        function_registry: dict[str, str],
        simple_name_lookup: dict[str, list[str]],
    ) -> list[RelationshipData]:
        """Resolve raw inheritance to INHERITS relationships.

        Args:
            inheritance_data: List of unresolved inheritance data
            function_registry: Complete function registry
            simple_name_lookup: Complete name lookup

        Returns:
            List of resolved INHERITS relationships
        """
        resolved: list[RelationshipData] = []

        for data in inheritance_data:
            child_qn = data.child_class_qn

            for parent_name in data.parent_simple_names:
                # Check if parent exists directly in registry
                if parent_name in function_registry:
                    resolved.append(
                        RelationshipData(
                            from_label="Class",
                            from_key="qualified_name",
                            from_value=child_qn,
                            rel_type="INHERITS",
                            to_label="Class",
                            to_key="qualified_name",
                            to_value=parent_name,
                        )
                    )
                else:
                    # Try simple name lookup
                    parent_simple = parent_name.split(".")[-1]
                    possible_parents = simple_name_lookup.get(parent_simple, [])

                    # Filter to only classes
                    class_parents = [
                        p for p in possible_parents
                        if function_registry.get(p) == "Class"
                    ]

                    if len(class_parents) == 1:
                        resolved.append(
                            RelationshipData(
                                from_label="Class",
                                from_key="qualified_name",
                                from_value=child_qn,
                                rel_type="INHERITS",
                                to_label="Class",
                                to_key="qualified_name",
                                to_value=class_parents[0],
                            )
                        )

        return resolved
