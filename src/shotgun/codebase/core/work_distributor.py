"""Work distribution system for parallel file parsing.

This module provides infrastructure for partitioning file parsing tasks
across workers with size-balanced distribution for optimal load balancing.
"""

from __future__ import annotations

import multiprocessing

from shotgun.codebase.core.metrics_types import (
    DistributionStats,
    FileInfo,
    FileParseTask,
    WorkBatch,
)
from shotgun.logging_config import get_logger
from shotgun.settings import settings

logger = get_logger(__name__)

# Default values
DEFAULT_BATCH_SIZE = 20

# Re-export types for convenience
__all__ = [
    "DEFAULT_BATCH_SIZE",
    "DistributionStats",
    "FileInfo",
    "FileParseTask",
    "WorkBatch",
    "WorkDistributor",
    "get_batch_size",
    "get_worker_count",
]


def get_worker_count() -> int:
    """Determine optimal worker count for parallel execution.

    Uses settings override if set, otherwise uses adaptive
    defaults based on CPU count:
    - For 4+ cores: max(2, cpu_count - 2)
    - For 1-3 cores: max(1, cpu_count - 1)

    Returns:
        Number of workers to use for parallel execution.
    """
    # Check settings override first
    if settings.indexing.index_workers is not None:
        result = max(1, settings.indexing.index_workers)
        logger.debug(f"Worker count from SHOTGUN_INDEX_WORKERS: {result}")
        return result

    cpu_count = multiprocessing.cpu_count()
    if cpu_count >= 4:
        result = max(2, cpu_count - 2)
    else:
        result = max(1, cpu_count - 1)

    logger.debug(f"Worker count (adaptive): {result} (CPU count: {cpu_count})")
    return result


def get_batch_size() -> int:
    """Get the batch size for grouping file parsing tasks.

    Checks settings for override, otherwise returns the default of 20 files per batch.

    Returns:
        Number of files to include in each work batch.
    """
    if settings.indexing.index_batch_size is not None:
        result = max(1, settings.indexing.index_batch_size)
        logger.debug(f"Batch size from SHOTGUN_INDEX_BATCH_SIZE: {result}")
        return result

    return DEFAULT_BATCH_SIZE


class WorkDistributor:
    """Distributes file parsing work across workers using size-balanced partitioning.

    Uses a bin-packing algorithm to ensure even work distribution:
    1. Sort files by size (descending)
    2. Assign each file to worker with least total work
    3. Group into batches for reduced queue overhead

    This approach ensures large files don't bottleneck single workers
    and workers finish at approximately the same time.
    """

    def __init__(
        self, worker_count: int | None = None, batch_size: int | None = None
    ) -> None:
        """Initialize the work distributor.

        Args:
            worker_count: Number of workers. If None, uses get_worker_count().
            batch_size: Files per batch. If None, uses get_batch_size().
        """
        self.worker_count = (
            worker_count if worker_count is not None else get_worker_count()
        )
        self.batch_size = batch_size if batch_size is not None else get_batch_size()

        # Ensure at least 1 worker
        self.worker_count = max(1, self.worker_count)
        self.batch_size = max(1, self.batch_size)

        logger.debug(
            f"WorkDistributor initialized: {self.worker_count} workers, "
            f"batch size {self.batch_size}"
        )

    def _distribute_files(
        self, files: list[FileInfo]
    ) -> list[tuple[int, list[FileInfo]]]:
        """Distribute files across workers using size-balanced bin-packing.

        Args:
            files: List of files to distribute.

        Returns:
            List of (total_bytes, file_list) tuples, one per worker.
        """
        # Sort files by size descending (largest first)
        sorted_files = sorted(files, key=lambda f: f.file_size_bytes, reverse=True)

        # Initialize worker buckets with total work tracking
        # Each bucket is (total_bytes, list_of_files)
        worker_buckets: list[tuple[int, list[FileInfo]]] = [
            (0, []) for _ in range(self.worker_count)
        ]

        # Assign each file to worker with least total work (bin-packing)
        for file_info in sorted_files:
            # Find worker with minimum total work
            min_idx = min(
                range(len(worker_buckets)), key=lambda i: worker_buckets[i][0]
            )
            total_work, files_list = worker_buckets[min_idx]
            files_list.append(file_info)
            worker_buckets[min_idx] = (
                total_work + file_info.file_size_bytes,
                files_list,
            )

        return worker_buckets

    def create_batches(self, files: list[FileInfo]) -> list[WorkBatch]:
        """Partition files into balanced batches for parallel processing.

        Uses size-balanced bin-packing to ensure even work distribution:
        1. Sort files by size (descending)
        2. Assign each file to worker with least total work
        3. Group into batches for reduced queue overhead

        Args:
            files: List of files to distribute across workers.

        Returns:
            List of WorkBatch objects containing FileParseTask items,
            balanced across workers and grouped into batches.
        """
        if not files:
            logger.debug("create_batches called with empty file list")
            return []

        logger.debug(
            f"Distributing {len(files)} files across {self.worker_count} workers"
        )

        # Distribute files across workers
        worker_buckets = self._distribute_files(files)

        # Log distribution statistics
        for worker_id, (total_bytes, worker_files) in enumerate(worker_buckets):
            logger.debug(
                f"Worker {worker_id}: {len(worker_files)} files, "
                f"{total_bytes / 1024:.1f} KB total"
            )

        # Convert to WorkBatch objects, grouping into batches
        batches: list[WorkBatch] = []
        batch_id = 0

        for _worker_id, (_, worker_files) in enumerate(worker_buckets):
            # Split worker's files into batches
            for i in range(0, len(worker_files), self.batch_size):
                batch_files = worker_files[i : i + self.batch_size]
                if batch_files:
                    tasks = [self._file_to_task(f) for f in batch_files]
                    batches.append(
                        WorkBatch(
                            batch_id=batch_id,
                            tasks=tasks,
                            estimated_duration_seconds=None,
                        )
                    )
                    batch_id += 1

        logger.debug(f"Created {len(batches)} batches from {len(files)} files")
        return batches

    def _file_to_task(self, file_info: FileInfo) -> FileParseTask:
        """Convert FileInfo to FileParseTask for worker consumption.

        Args:
            file_info: File information with size data.

        Returns:
            FileParseTask suitable for sending to worker processes.
        """
        return FileParseTask(
            file_path=file_info.file_path,
            relative_path=file_info.relative_path,
            language=file_info.language,
            module_qn=file_info.module_qn,
            container_qn=file_info.container_qn,
        )

    def get_distribution_stats(self, files: list[FileInfo]) -> DistributionStats:
        """Get statistics about how files would be distributed.

        Useful for debugging and verification without creating actual batches.

        Args:
            files: List of files to analyze.

        Returns:
            DistributionStats with distribution information.
        """
        if not files:
            return DistributionStats(
                total_files=0,
                total_bytes=0,
                worker_count=self.worker_count,
                batch_size=self.batch_size,
                files_per_worker=[0] * self.worker_count,
                bytes_per_worker=[0] * self.worker_count,
            )

        # Use shared distribution logic
        worker_buckets = self._distribute_files(files)

        return DistributionStats(
            total_files=len(files),
            total_bytes=sum(f.file_size_bytes for f in files),
            worker_count=self.worker_count,
            batch_size=self.batch_size,
            files_per_worker=[len(file_list) for _, file_list in worker_buckets],
            bytes_per_worker=[total_bytes for total_bytes, _ in worker_buckets],
        )
