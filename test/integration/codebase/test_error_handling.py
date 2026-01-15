"""Error handling tests for parallel execution.

These tests verify graceful handling of various error conditions
during parallel file parsing.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from shotgun.codebase import CodebaseService, QueryType
from shotgun.codebase.core.metrics_types import (
    FileParseTask,
    WorkBatch,
)
from shotgun.codebase.core.parallel_executor import ParallelExecutor
from shotgun.codebase.models import GraphStatus

# =============================================================================
# Worker Error Handling Tests
# =============================================================================


@pytest.mark.integration
def test_worker_handles_nonexistent_file() -> None:
    """Test that worker handles nonexistent files gracefully."""
    task = FileParseTask(
        file_path=Path("/nonexistent/path/file.py"),
        relative_path=Path("file.py"),
        language="python",
        module_qn="test.file",
        container_qn=None,
    )
    batch = WorkBatch(batch_id=0, tasks=[task], estimated_duration_seconds=None)

    executor = ParallelExecutor(worker_count=2)
    result = executor.execute([batch])

    assert result.total_files == 1
    assert result.failed_files == 1
    assert result.successful_files == 0


@pytest.mark.integration
def test_worker_handles_parse_error(tmp_path: Path) -> None:
    """Test that worker handles files with syntax errors."""
    # Create file with invalid Python syntax
    bad_file = tmp_path / "bad_syntax.py"
    bad_file.write_text("def broken(\n  # missing closing paren and body")

    task = FileParseTask(
        file_path=bad_file,
        relative_path=Path("bad_syntax.py"),
        language="python",
        module_qn="test.bad_syntax",
        container_qn=None,
    )
    batch = WorkBatch(batch_id=0, tasks=[task], estimated_duration_seconds=None)

    executor = ParallelExecutor(worker_count=2)
    result = executor.execute([batch])

    # tree-sitter handles syntax errors gracefully, so this should succeed
    # but with partial results. Verify it doesn't crash.
    assert result.total_files == 1


@pytest.mark.integration
def test_worker_handles_binary_file(tmp_path: Path) -> None:
    """Test that worker handles binary files gracefully."""
    # Create a binary file
    binary_file = tmp_path / "binary.py"
    binary_file.write_bytes(b"\x00\x01\x02\x03\x04\x05")

    task = FileParseTask(
        file_path=binary_file,
        relative_path=Path("binary.py"),
        language="python",
        module_qn="test.binary",
        container_qn=None,
    )
    batch = WorkBatch(batch_id=0, tasks=[task], estimated_duration_seconds=None)

    executor = ParallelExecutor(worker_count=2)
    result = executor.execute([batch])

    # Should handle binary content without crashing
    assert result.total_files == 1


@pytest.mark.integration
def test_worker_handles_empty_file(tmp_path: Path) -> None:
    """Test that worker handles empty files gracefully."""
    # Create an empty file
    empty_file = tmp_path / "empty.py"
    empty_file.write_text("")

    task = FileParseTask(
        file_path=empty_file,
        relative_path=Path("empty.py"),
        language="python",
        module_qn="test.empty",
        container_qn=None,
    )
    batch = WorkBatch(batch_id=0, tasks=[task], estimated_duration_seconds=None)

    executor = ParallelExecutor(worker_count=2)
    result = executor.execute([batch])

    assert result.total_files == 1
    assert result.successful_files == 1


@pytest.mark.integration
def test_worker_handles_large_file(tmp_path: Path) -> None:
    """Test that worker handles large files."""
    # Create a large file with many definitions
    large_file = tmp_path / "large.py"
    lines = ['"""Large file for testing."""', ""]
    for i in range(100):
        lines.append(f"def func_{i}(): pass")
    large_file.write_text("\n".join(lines))

    task = FileParseTask(
        file_path=large_file,
        relative_path=Path("large.py"),
        language="python",
        module_qn="test.large",
        container_qn=None,
    )
    batch = WorkBatch(batch_id=0, tasks=[task], estimated_duration_seconds=None)

    executor = ParallelExecutor(worker_count=2)
    result = executor.execute([batch])

    assert result.total_files == 1
    assert result.successful_files == 1


# =============================================================================
# Timeout Handling Tests
# =============================================================================


@pytest.mark.integration
def test_timeout_configuration_accepted() -> None:
    """Test that timeout configuration is accepted."""
    # ParallelExecutor should accept batch_timeout_seconds
    executor = ParallelExecutor(
        worker_count=2,
        batch_timeout_seconds=60.0,
    )
    # The attribute is stored as batch_timeout
    assert executor.batch_timeout == 60.0


@pytest.mark.integration
def test_executor_handles_empty_batch_list() -> None:
    """Test that executor handles empty batch list."""
    executor = ParallelExecutor(worker_count=2)
    result = executor.execute([])

    assert result.total_files == 0
    assert result.successful_files == 0
    assert result.failed_files == 0


@pytest.mark.integration
def test_executor_handles_empty_batch() -> None:
    """Test that executor handles batch with no tasks."""
    batch = WorkBatch(batch_id=0, tasks=[], estimated_duration_seconds=None)

    executor = ParallelExecutor(worker_count=2)
    result = executor.execute([batch])

    assert result.total_files == 0


# =============================================================================
# Graceful Degradation Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_graceful_degradation_to_sequential(
    simple_python_codebase: Path,
    tmp_path: Path,
) -> None:
    """Test graceful degradation to sequential mode on errors."""

    # Mock parallel executor to raise an exception
    def failing_execute(self, batches):
        raise RuntimeError("Simulated parallel failure")

    service = CodebaseService(tmp_path / "storage")

    with patch.object(ParallelExecutor, "execute", failing_execute):
        # Should fallback to sequential and complete successfully
        graph = await service.create_graph(
            simple_python_codebase,
            "Fallback Test",
        )

    # Should still succeed via fallback
    assert graph is not None
    assert graph.status == GraphStatus.READY
    assert graph.node_count > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sequential_fallback_produces_valid_data(
    calculator_codebase: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Test that sequential fallback produces valid indexed data."""
    # Force sequential mode
    monkeypatch.setenv("SHOTGUN_INDEX_PARALLEL", "false")

    service = CodebaseService(tmp_path / "storage")
    graph = await service.create_graph(
        calculator_codebase,
        "Sequential Fallback Test",
    )

    assert graph.status == GraphStatus.READY

    # Verify classes were indexed
    result = await service.execute_query(
        graph.graph_id,
        "MATCH (c:Class) RETURN c.name as name ORDER BY c.name",
        QueryType.CYPHER,
    )

    assert result.success is True
    assert result.row_count >= 3  # Calculator, ScientificCalculator, MathConstants


# =============================================================================
# Error Metrics Collection Tests
# =============================================================================


@pytest.mark.integration
def test_error_metrics_collected_for_missing_file() -> None:
    """Test that error metrics are collected for missing files."""
    task = FileParseTask(
        file_path=Path("/nonexistent/file.py"),
        relative_path=Path("file.py"),
        language="python",
        module_qn="test.file",
        container_qn=None,
    )
    batch = WorkBatch(batch_id=0, tasks=[task], estimated_duration_seconds=None)

    executor = ParallelExecutor(worker_count=2)
    result = executor.execute([batch])

    # Check that errors are tracked
    assert result.failed_files >= 1

    # Check results contain error info
    for file_result in result.results:
        if not file_result.success:
            assert file_result.error is not None


@pytest.mark.integration
def test_mixed_success_failure_metrics(tmp_path: Path) -> None:
    """Test metrics with mix of successful and failed files."""
    # Create one valid file
    valid_file = tmp_path / "valid.py"
    valid_file.write_text("def hello(): pass")

    tasks = [
        FileParseTask(
            file_path=valid_file,
            relative_path=Path("valid.py"),
            language="python",
            module_qn="test.valid",
            container_qn=None,
        ),
        FileParseTask(
            file_path=Path("/nonexistent/file.py"),
            relative_path=Path("nonexistent.py"),
            language="python",
            module_qn="test.nonexistent",
            container_qn=None,
        ),
    ]
    batch = WorkBatch(batch_id=0, tasks=tasks, estimated_duration_seconds=None)

    executor = ParallelExecutor(worker_count=2)
    result = executor.execute([batch])

    assert result.total_files == 2
    assert result.successful_files == 1
    assert result.failed_files == 1


@pytest.mark.integration
def test_all_files_fail_gracefully(tmp_path: Path) -> None:
    """Test that all files failing doesn't crash the executor."""
    tasks = [
        FileParseTask(
            file_path=Path(f"/nonexistent/file_{i}.py"),
            relative_path=Path(f"file_{i}.py"),
            language="python",
            module_qn=f"test.file_{i}",
            container_qn=None,
        )
        for i in range(5)
    ]
    batch = WorkBatch(batch_id=0, tasks=tasks, estimated_duration_seconds=None)

    executor = ParallelExecutor(worker_count=2)
    result = executor.execute([batch])

    assert result.total_files == 5
    assert result.failed_files == 5
    assert result.successful_files == 0


# =============================================================================
# Multiple Batch Error Handling
# =============================================================================


@pytest.mark.integration
def test_multiple_batches_with_mixed_results(tmp_path: Path) -> None:
    """Test handling multiple batches with different outcomes."""
    # Create valid files
    valid1 = tmp_path / "valid1.py"
    valid1.write_text("def func1(): pass")

    valid2 = tmp_path / "valid2.py"
    valid2.write_text("class MyClass: pass")

    # Batch 1: valid file
    batch1 = WorkBatch(
        batch_id=0,
        tasks=[
            FileParseTask(
                file_path=valid1,
                relative_path=Path("valid1.py"),
                language="python",
                module_qn="test.valid1",
                container_qn=None,
            )
        ],
        estimated_duration_seconds=None,
    )

    # Batch 2: invalid file
    batch2 = WorkBatch(
        batch_id=1,
        tasks=[
            FileParseTask(
                file_path=Path("/nonexistent.py"),
                relative_path=Path("nonexistent.py"),
                language="python",
                module_qn="test.nonexistent",
                container_qn=None,
            )
        ],
        estimated_duration_seconds=None,
    )

    # Batch 3: valid file
    batch3 = WorkBatch(
        batch_id=2,
        tasks=[
            FileParseTask(
                file_path=valid2,
                relative_path=Path("valid2.py"),
                language="python",
                module_qn="test.valid2",
                container_qn=None,
            )
        ],
        estimated_duration_seconds=None,
    )

    executor = ParallelExecutor(worker_count=2)
    result = executor.execute([batch1, batch2, batch3])

    assert result.total_files == 3
    assert result.successful_files == 2
    assert result.failed_files == 1
