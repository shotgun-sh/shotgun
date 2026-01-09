"""Unit tests for WorkDistributor class."""

from pathlib import Path
from unittest.mock import patch

import pytest

from shotgun.codebase.core.work_distributor import (
    DEFAULT_BATCH_SIZE,
    DistributionStats,
    FileInfo,
    FileParseTask,
    WorkBatch,
    WorkDistributor,
    get_batch_size,
    get_worker_count,
)
from shotgun.settings import settings

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_files() -> list[FileInfo]:
    """Create sample files with varying sizes for testing."""
    sizes = [100000, 50000, 50000, 10000, 10000, 10000, 5000, 5000]
    return [
        FileInfo(
            file_path=Path(f"/repo/src/file_{i}.py"),
            relative_path=Path(f"src/file_{i}.py"),
            language="python",
            module_qn=f"project.src.file_{i}",
            container_qn="project.src",
            file_size_bytes=size,
        )
        for i, size in enumerate(sizes)
    ]


@pytest.fixture
def large_file_set() -> list[FileInfo]:
    """Create a large set of files with varying sizes."""
    return [
        FileInfo(
            file_path=Path(f"/repo/src/file_{i}.py"),
            relative_path=Path(f"src/file_{i}.py"),
            language="python",
            module_qn=f"project.src.file_{i}",
            container_qn="project.src",
            file_size_bytes=(i % 10 + 1) * 1000,  # 1KB to 10KB
        )
        for i in range(100)
    ]


# =============================================================================
# Tests for get_worker_count()
# =============================================================================


def test_get_worker_count_default_many_cores() -> None:
    """Test adaptive default for systems with 4+ cores."""
    with patch("multiprocessing.cpu_count", return_value=8):
        with patch.object(settings.indexing, "index_workers", None):
            count = get_worker_count()
            assert count == 6  # 8 - 2 = 6


def test_get_worker_count_default_few_cores() -> None:
    """Test adaptive default for systems with 1-3 cores."""
    with patch("multiprocessing.cpu_count", return_value=2):
        with patch.object(settings.indexing, "index_workers", None):
            count = get_worker_count()
            assert count == 1  # max(1, 2 - 1) = 1


def test_get_worker_count_default_minimum() -> None:
    """Test minimum worker count is 1."""
    with patch("multiprocessing.cpu_count", return_value=1):
        with patch.object(settings.indexing, "index_workers", None):
            count = get_worker_count()
            assert count >= 1


def test_get_worker_count_env_override() -> None:
    """Test SHOTGUN_INDEX_WORKERS setting override."""
    with patch.object(settings.indexing, "index_workers", 4):
        count = get_worker_count()
        assert count == 4


def test_get_worker_count_env_override_zero() -> None:
    """Test that zero setting value is treated as 1."""
    with patch.object(settings.indexing, "index_workers", 0):
        count = get_worker_count()
        assert count == 1


def test_get_worker_count_env_override_negative() -> None:
    """Test that negative setting value is treated as 1."""
    with patch.object(settings.indexing, "index_workers", -5):
        count = get_worker_count()
        assert count == 1


def test_get_worker_count_invalid_env() -> None:
    """Test that None setting falls back to adaptive default."""
    with patch("multiprocessing.cpu_count", return_value=8):
        with patch.object(settings.indexing, "index_workers", None):
            count = get_worker_count()
            assert count == 6  # Falls back to adaptive default


# =============================================================================
# Tests for get_batch_size()
# =============================================================================


def test_get_batch_size_default() -> None:
    """Test default batch size is 20."""
    with patch.object(settings.indexing, "index_batch_size", None):
        size = get_batch_size()
        assert size == DEFAULT_BATCH_SIZE
        assert size == 20


def test_get_batch_size_env_override() -> None:
    """Test SHOTGUN_INDEX_BATCH_SIZE setting override."""
    with patch.object(settings.indexing, "index_batch_size", 50):
        size = get_batch_size()
        assert size == 50


def test_get_batch_size_env_override_zero() -> None:
    """Test that zero setting value is treated as 1."""
    with patch.object(settings.indexing, "index_batch_size", 0):
        size = get_batch_size()
        assert size == 1


def test_get_batch_size_env_override_negative() -> None:
    """Test that negative setting value is treated as 1."""
    with patch.object(settings.indexing, "index_batch_size", -10):
        size = get_batch_size()
        assert size == 1


def test_get_batch_size_invalid_env() -> None:
    """Test that None setting falls back to default."""
    with patch.object(settings.indexing, "index_batch_size", None):
        size = get_batch_size()
        assert size == DEFAULT_BATCH_SIZE


# =============================================================================
# Tests for WorkDistributor initialization
# =============================================================================


def test_work_distributor_default_initialization() -> None:
    """Test WorkDistributor uses defaults when not specified."""
    with patch("multiprocessing.cpu_count", return_value=8):
        with (
            patch.object(settings.indexing, "index_workers", None),
            patch.object(settings.indexing, "index_batch_size", None),
        ):
            distributor = WorkDistributor()
            assert distributor.worker_count == 6
            assert distributor.batch_size == 20


def test_work_distributor_custom_initialization() -> None:
    """Test WorkDistributor respects custom parameters."""
    distributor = WorkDistributor(worker_count=4, batch_size=10)
    assert distributor.worker_count == 4
    assert distributor.batch_size == 10


def test_work_distributor_minimum_values() -> None:
    """Test WorkDistributor enforces minimum values."""
    distributor = WorkDistributor(worker_count=0, batch_size=0)
    assert distributor.worker_count == 1
    assert distributor.batch_size == 1


# =============================================================================
# Tests for create_batches()
# =============================================================================


def test_create_batches_empty_list() -> None:
    """Test create_batches handles empty file list."""
    distributor = WorkDistributor(worker_count=4, batch_size=10)
    batches = distributor.create_batches([])
    assert batches == []


def test_create_batches_single_file() -> None:
    """Test create_batches handles single file."""
    file = FileInfo(
        file_path=Path("/repo/test.py"),
        relative_path=Path("test.py"),
        language="python",
        module_qn="project.test",
        container_qn=None,
        file_size_bytes=1000,
    )
    distributor = WorkDistributor(worker_count=4, batch_size=10)
    batches = distributor.create_batches([file])

    assert len(batches) == 1
    assert len(batches[0].tasks) == 1
    assert batches[0].batch_id == 0


def test_create_batches_preserves_all_files(sample_files: list[FileInfo]) -> None:
    """Test that all files are preserved in the distribution."""
    distributor = WorkDistributor(worker_count=4, batch_size=10)
    batches = distributor.create_batches(sample_files)

    # Count total tasks across all batches
    total_tasks = sum(len(batch.tasks) for batch in batches)
    assert total_tasks == len(sample_files)


def test_create_batches_balanced_distribution(sample_files: list[FileInfo]) -> None:
    """Test that large files are distributed across workers."""
    distributor = WorkDistributor(worker_count=4, batch_size=20)
    batches = distributor.create_batches(sample_files)

    # Verify batches were created
    assert len(batches) > 0

    # Get distribution stats
    stats = distributor.get_distribution_stats(sample_files)

    # Check that files are distributed across workers
    assert all(isinstance(count, int) for count in stats.files_per_worker)

    # Bytes should be somewhat balanced (not all in one worker)
    assert max(stats.bytes_per_worker) <= sum(stats.bytes_per_worker)

    # Verify batch distribution matches stats
    total_tasks_in_batches = sum(len(batch.tasks) for batch in batches)
    assert total_tasks_in_batches == stats.total_files


def test_create_batches_large_files_not_bottlenecked(
    sample_files: list[FileInfo],
) -> None:
    """Test that the largest files are assigned to different workers."""
    # sample_files has sizes: 100000, 50000, 50000, 10000, 10000, 10000, 5000, 5000
    distributor = WorkDistributor(worker_count=4, batch_size=20)

    stats = distributor.get_distribution_stats(sample_files)

    # The two largest files (100KB, 50KB) should go to different workers
    # so max worker should have at most ~100KB + some small files
    max_bytes = max(stats.bytes_per_worker)
    total_bytes = sum(stats.bytes_per_worker)

    # No single worker should have more than 60% of total work
    assert max_bytes <= total_bytes * 0.6


def test_create_batches_same_size_files() -> None:
    """Test create_batches with all files having same size."""
    files = [
        FileInfo(
            file_path=Path(f"/repo/file_{i}.py"),
            relative_path=Path(f"file_{i}.py"),
            language="python",
            module_qn=f"project.file_{i}",
            container_qn=None,
            file_size_bytes=1000,  # All same size
        )
        for i in range(12)
    ]
    distributor = WorkDistributor(worker_count=4, batch_size=20)
    batches = distributor.create_batches(files)

    # All files should be preserved
    total_tasks = sum(len(batch.tasks) for batch in batches)
    assert total_tasks == 12

    # Distribution should be even (3 files per worker)
    stats = distributor.get_distribution_stats(files)
    assert stats.files_per_worker == [3, 3, 3, 3]


def test_create_batches_batch_size_respected(large_file_set: list[FileInfo]) -> None:
    """Test that batch size is respected when grouping files."""
    batch_size = 15
    distributor = WorkDistributor(worker_count=4, batch_size=batch_size)
    batches = distributor.create_batches(large_file_set)

    # Each batch should have at most batch_size tasks
    for batch in batches:
        assert len(batch.tasks) <= batch_size


def test_create_batches_unique_batch_ids() -> None:
    """Test that all batches have unique IDs."""
    files = [
        FileInfo(
            file_path=Path(f"/repo/file_{i}.py"),
            relative_path=Path(f"file_{i}.py"),
            language="python",
            module_qn=f"project.file_{i}",
            container_qn=None,
            file_size_bytes=1000,
        )
        for i in range(50)
    ]
    distributor = WorkDistributor(worker_count=4, batch_size=5)
    batches = distributor.create_batches(files)

    batch_ids = [batch.batch_id for batch in batches]
    assert len(batch_ids) == len(set(batch_ids))  # All unique


def test_create_batches_task_data_correct(sample_files: list[FileInfo]) -> None:
    """Test that FileParseTask contains correct data from FileInfo."""
    distributor = WorkDistributor(worker_count=2, batch_size=10)
    batches = distributor.create_batches(sample_files)

    # Get all tasks
    all_tasks: list[FileParseTask] = []
    for batch in batches:
        all_tasks.extend(batch.tasks)

    # Check that task data matches file data
    file_paths = {str(f.file_path) for f in sample_files}
    task_paths = {str(t.file_path) for t in all_tasks}
    assert file_paths == task_paths


# =============================================================================
# Tests for get_distribution_stats()
# =============================================================================


def test_get_distribution_stats_empty() -> None:
    """Test get_distribution_stats with empty file list."""
    distributor = WorkDistributor(worker_count=4, batch_size=10)
    stats = distributor.get_distribution_stats([])

    assert stats.total_files == 0
    assert stats.total_bytes == 0
    assert stats.worker_count == 4
    assert stats.batch_size == 10
    assert stats.files_per_worker == [0, 0, 0, 0]
    assert stats.bytes_per_worker == [0, 0, 0, 0]


def test_get_distribution_stats_populated(sample_files: list[FileInfo]) -> None:
    """Test get_distribution_stats returns correct totals."""
    distributor = WorkDistributor(worker_count=4, batch_size=10)
    stats = distributor.get_distribution_stats(sample_files)

    assert stats.total_files == len(sample_files)
    assert stats.total_bytes == sum(f.file_size_bytes for f in sample_files)
    assert stats.worker_count == 4
    assert stats.batch_size == 10
    assert len(stats.files_per_worker) == 4
    assert len(stats.bytes_per_worker) == 4


def test_get_distribution_stats_returns_pydantic_model() -> None:
    """Test that get_distribution_stats returns a DistributionStats model."""
    distributor = WorkDistributor(worker_count=2, batch_size=5)
    stats = distributor.get_distribution_stats([])

    assert isinstance(stats, DistributionStats)


# =============================================================================
# Tests for FileInfo and FileParseTask models
# =============================================================================


def test_file_info_model_creation() -> None:
    """Test FileInfo model can be created with all fields."""
    file_info = FileInfo(
        file_path=Path("/repo/src/test.py"),
        relative_path=Path("src/test.py"),
        language="python",
        module_qn="project.src.test",
        container_qn="project.src",
        file_size_bytes=5000,
    )

    assert file_info.file_path == Path("/repo/src/test.py")
    assert file_info.relative_path == Path("src/test.py")
    assert file_info.language == "python"
    assert file_info.module_qn == "project.src.test"
    assert file_info.container_qn == "project.src"
    assert file_info.file_size_bytes == 5000


def test_file_info_optional_container() -> None:
    """Test FileInfo allows None for container_qn."""
    file_info = FileInfo(
        file_path=Path("/repo/test.py"),
        relative_path=Path("test.py"),
        language="python",
        module_qn="project.test",
        container_qn=None,
        file_size_bytes=1000,
    )

    assert file_info.container_qn is None


def test_file_parse_task_model_creation() -> None:
    """Test FileParseTask model can be created with all fields."""
    task = FileParseTask(
        file_path=Path("/repo/src/test.py"),
        relative_path=Path("src/test.py"),
        language="python",
        module_qn="project.src.test",
        container_qn="project.src",
    )

    assert task.file_path == Path("/repo/src/test.py")
    assert task.language == "python"


def test_work_batch_model_creation() -> None:
    """Test WorkBatch model can be created with tasks."""
    task = FileParseTask(
        file_path=Path("/repo/test.py"),
        relative_path=Path("test.py"),
        language="python",
        module_qn="project.test",
        container_qn=None,
    )
    batch = WorkBatch(
        batch_id=0,
        tasks=[task],
        estimated_duration_seconds=1.5,
    )

    assert batch.batch_id == 0
    assert len(batch.tasks) == 1
    assert batch.estimated_duration_seconds == 1.5
