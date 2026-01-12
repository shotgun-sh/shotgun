"""Cross-platform tests for parallel execution.

These tests verify that parallel execution works correctly on all platforms
(Linux, macOS, Windows) and that platform-specific utilities like psutil
work correctly.

Note: These tests run on all platforms via GitHub Actions matrix.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import psutil
import pytest

from shotgun.codebase.core.metrics_collector import MetricsCollector
from shotgun.codebase.core.metrics_types import (
    FileInfo,
)
from shotgun.codebase.core.parallel_executor import ParallelExecutor
from shotgun.codebase.core.work_distributor import WorkDistributor, get_worker_count

# =============================================================================
# Platform Detection Tests
# =============================================================================


@pytest.mark.integration
def test_platform_detection() -> None:
    """Test that platform detection works correctly."""
    current_platform = sys.platform
    assert current_platform in ["linux", "darwin", "win32", "cygwin"]


@pytest.mark.integration
def test_worker_count_platform_independent() -> None:
    """Test that worker count calculation works on all platforms."""
    count = get_worker_count()
    assert count >= 1
    assert isinstance(count, int)


@pytest.mark.integration
def test_cpu_count_available() -> None:
    """Test that CPU count is available on all platforms."""
    import multiprocessing

    cpu_count = multiprocessing.cpu_count()
    assert cpu_count >= 1
    assert isinstance(cpu_count, int)


# =============================================================================
# psutil Memory Tracking Tests
# =============================================================================


@pytest.mark.integration
def test_psutil_memory_info_works() -> None:
    """Verify psutil memory tracking works on all platforms."""
    process = psutil.Process()
    memory_info = process.memory_info()

    # RSS should be non-zero
    assert memory_info.rss > 0

    # VMS should exist (virtual memory size)
    assert hasattr(memory_info, "vms")


@pytest.mark.integration
def test_psutil_cpu_percent_works() -> None:
    """Verify psutil CPU percent works on all platforms."""
    cpu = psutil.cpu_percent(interval=0.1)
    assert isinstance(cpu, float)
    assert 0 <= cpu <= 100


@pytest.mark.integration
def test_psutil_process_works() -> None:
    """Verify psutil Process works on all platforms."""
    process = psutil.Process()

    # Should be able to get pid
    assert process.pid > 0

    # Should be able to get name
    name = process.name()
    assert isinstance(name, str)


@pytest.mark.integration
def test_metrics_collector_memory_tracking() -> None:
    """Test MetricsCollector's cross-platform memory tracking."""
    collector = MetricsCollector(
        codebase_name="platform-test",
        collect_file_metrics=False,
        collect_worker_metrics=False,
    )

    # _get_memory_mb should return a float on all platforms
    memory_mb = collector._get_memory_mb()
    assert isinstance(memory_mb, float)
    assert memory_mb >= 0


# =============================================================================
# Parallel Execution Platform Tests
# =============================================================================


@pytest.mark.integration
def test_parallel_executor_initialization() -> None:
    """Test ParallelExecutor can be initialized on all platforms."""
    executor = ParallelExecutor(worker_count=2)
    assert executor.worker_count == 2


@pytest.mark.integration
def test_parallel_executor_on_platform(tmp_path: Path) -> None:
    """Test ParallelExecutor works on current platform."""
    # Create a test Python file
    test_file = tmp_path / "test_module.py"
    test_file.write_text("def hello(): pass")

    # Create file infos
    file_infos = [
        FileInfo(
            file_path=test_file,
            relative_path=Path("test_module.py"),
            language="python",
            module_qn="test.test_module",
            container_qn="test",
            file_size_bytes=test_file.stat().st_size,
        )
    ]

    # Create batches
    distributor = WorkDistributor(worker_count=2, batch_size=10)
    batches = distributor.create_batches(file_infos)

    # Execute
    executor = ParallelExecutor(worker_count=2)
    result = executor.execute(batches)

    assert result.total_files == len(file_infos)


@pytest.mark.integration
def test_work_distributor_on_platform(tmp_path: Path) -> None:
    """Test WorkDistributor works on current platform."""
    # Create test Python files
    for i in range(5):
        test_file = tmp_path / f"module_{i}.py"
        test_file.write_text(f"def func_{i}(): pass")

    # Find Python files
    py_files = list(tmp_path.rglob("*.py"))

    # Create file infos
    file_infos = []
    for py_file in py_files:
        relative = py_file.relative_to(tmp_path)
        file_infos.append(
            FileInfo(
                file_path=py_file,
                relative_path=relative,
                language="python",
                module_qn=f"test.{relative.stem}",
                container_qn="test",
                file_size_bytes=py_file.stat().st_size,
            )
        )

    # Distribute work
    distributor = WorkDistributor(worker_count=4, batch_size=5)
    batches = distributor.create_batches(file_infos)

    # Verify batches are created
    assert len(batches) > 0
    total_tasks = sum(len(b.tasks) for b in batches)
    assert total_tasks == len(file_infos)


# =============================================================================
# Path Handling Tests
# =============================================================================


@pytest.mark.integration
def test_path_separator_handling(tmp_path: Path) -> None:
    """Test that path separators are handled correctly on all platforms."""
    # Create nested directory
    nested = tmp_path / "a" / "b" / "c"
    nested.mkdir(parents=True)

    # Create a file
    test_file = nested / "test.py"
    test_file.write_text("print('hello')")

    # Verify path operations work
    relative = test_file.relative_to(tmp_path)

    # Convert to forward slashes (Unix style) as used in the codebase
    unix_path = str(relative).replace(os.sep, "/")
    assert "/" in unix_path or len(relative.parts) == 1


@pytest.mark.integration
def test_temp_directory_creation() -> None:
    """Test that temporary directories work on all platforms."""
    with tempfile.TemporaryDirectory(prefix="shotgun_test_") as temp_dir:
        path = Path(temp_dir)
        assert path.exists()
        assert path.is_dir()

        # Create a file
        test_file = path / "test.txt"
        test_file.write_text("test content")
        assert test_file.exists()


@pytest.mark.integration
def test_path_resolve_works(tmp_path: Path) -> None:
    """Test that path.resolve() works on all platforms."""
    # Create a relative path situation
    test_file = tmp_path / "test.py"
    test_file.write_text("pass")

    # Resolve should return absolute path
    resolved = test_file.resolve()
    assert resolved.is_absolute()


# =============================================================================
# Timeout Handling Platform Tests
# =============================================================================


@pytest.mark.integration
def test_timeout_handling_works() -> None:
    """Test that ThreadPoolExecutor timeout works on all platforms."""
    import time
    from concurrent.futures import ThreadPoolExecutor, TimeoutError

    def slow_function():
        time.sleep(10)
        return "done"

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(slow_function)

        with pytest.raises(TimeoutError):
            future.result(timeout=0.1)


@pytest.mark.integration
def test_thread_creation_works() -> None:
    """Test that thread creation works on all platforms."""
    import threading

    results = []

    def worker(value: int) -> None:
        results.append(value * 2)

    threads = []
    for i in range(4):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=5.0)

    assert len(results) == 4


# =============================================================================
# Environment Variable Tests
# =============================================================================


@pytest.mark.integration
def test_environment_variable_access() -> None:
    """Test that environment variables work on all platforms."""
    # Set a test variable
    os.environ["SHOTGUN_TEST_VAR"] = "test_value"

    # Read it back
    value = os.environ.get("SHOTGUN_TEST_VAR")
    assert value == "test_value"

    # Clean up
    del os.environ["SHOTGUN_TEST_VAR"]


@pytest.mark.integration
def test_worker_count_env_override(monkeypatch) -> None:
    """Test that SHOTGUN_INDEX_WORKERS env var works via settings."""
    from shotgun.codebase.core.work_distributor import settings

    # Patch the settings object directly since env vars are read at import time
    monkeypatch.setattr(settings.indexing, "index_workers", 4)

    # This should read from patched settings
    count = get_worker_count()
    assert count == 4
