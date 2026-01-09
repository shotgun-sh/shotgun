"""Unit tests for ParallelExecutor class."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from shotgun.codebase.core.metrics_types import (
    FileParseResult,
    FileParseTask,
    InheritanceData,
    RawCallData,
    WorkBatch,
)
from shotgun.codebase.core.parallel_executor import (
    DEFAULT_BATCH_TIMEOUT_SECONDS,
    ParallelExecutor,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_task() -> FileParseTask:
    """Create a sample file parse task."""
    return FileParseTask(
        file_path=Path("/repo/src/test.py"),
        relative_path=Path("src/test.py"),
        language="python",
        module_qn="project.src.test",
        container_qn="project.src",
    )


@pytest.fixture
def sample_batch(sample_task: FileParseTask) -> WorkBatch:
    """Create a sample work batch."""
    return WorkBatch(
        batch_id=1,
        tasks=[sample_task],
        estimated_duration_seconds=None,
    )


# =============================================================================
# Tests for ParallelExecutor initialization
# =============================================================================


def test_parallel_executor_initializes_with_defaults() -> None:
    """Test that ParallelExecutor initializes with sensible defaults."""
    executor = ParallelExecutor()

    assert executor.worker_count >= 1
    assert executor.batch_timeout == DEFAULT_BATCH_TIMEOUT_SECONDS
    assert executor.metrics_collector is None


def test_parallel_executor_accepts_custom_worker_count() -> None:
    """Test that ParallelExecutor accepts custom worker count."""
    executor = ParallelExecutor(worker_count=4)

    assert executor.worker_count == 4


def test_parallel_executor_accepts_custom_timeout() -> None:
    """Test that ParallelExecutor accepts custom timeout."""
    executor = ParallelExecutor(batch_timeout_seconds=60.0)

    assert executor.batch_timeout == 60.0


def test_parallel_executor_accepts_metrics_collector() -> None:
    """Test that ParallelExecutor accepts metrics collector."""
    mock_collector = MagicMock()
    executor = ParallelExecutor(metrics_collector=mock_collector)

    assert executor.metrics_collector is mock_collector


# =============================================================================
# Tests for execute() - basic functionality
# =============================================================================


def test_execute_returns_empty_result_for_no_batches() -> None:
    """Test that execute returns empty result when no batches provided."""
    executor = ParallelExecutor(worker_count=2)
    result = executor.execute([])

    assert result.total_files == 0
    assert result.successful_files == 0
    assert result.failed_files == 0
    assert len(result.results) == 0


def test_execute_processes_batches_with_real_file() -> None:
    """Test that execute processes batches with real files."""
    import tempfile

    content = '''
def my_func():
    pass
'''
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False
    ) as f:
        f.write(content)
        file_path = Path(f.name)

    task = FileParseTask(
        file_path=file_path,
        relative_path=Path("test.py"),
        language="python",
        module_qn="project.test",
        container_qn="project",
    )
    batch = WorkBatch(batch_id=1, tasks=[task], estimated_duration_seconds=None)

    executor = ParallelExecutor(worker_count=2)
    result = executor.execute([batch])

    assert result.total_files == 1
    assert result.successful_files == 1
    assert result.failed_files == 0
    assert len(result.results) == 1


def test_execute_calls_progress_callback_with_real_file() -> None:
    """Test that execute calls progress callback with real files."""
    import tempfile

    content = "def func(): pass"
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False
    ) as f:
        f.write(content)
        file_path = Path(f.name)

    task = FileParseTask(
        file_path=file_path,
        relative_path=Path("test.py"),
        language="python",
        module_qn="project.test",
        container_qn="project",
    )
    batch = WorkBatch(batch_id=1, tasks=[task], estimated_duration_seconds=None)

    executor = ParallelExecutor(worker_count=2)
    progress_calls = []

    def progress_callback(completed: int, total: int) -> None:
        progress_calls.append((completed, total))

    executor.execute([batch], progress_callback=progress_callback)

    assert len(progress_calls) == 1
    assert progress_calls[0] == (1, 1)


# =============================================================================
# Tests for _aggregate_registries()
# =============================================================================


def test_aggregate_registries_merges_function_registry() -> None:
    """Test that _aggregate_registries merges function registries."""
    executor = ParallelExecutor()

    result1 = FileParseResult(
        task=FileParseTask(
            file_path=Path("/repo/a.py"),
            relative_path=Path("a.py"),
            language="python",
            module_qn="project.a",
            container_qn="project",
        ),
        success=True,
        function_registry_entries={
            "project.a.ClassA": "Class",
            "project.a.func_a": "Function",
        },
        simple_name_entries={
            "ClassA": ["project.a.ClassA"],
            "func_a": ["project.a.func_a"],
        },
    )

    result2 = FileParseResult(
        task=FileParseTask(
            file_path=Path("/repo/b.py"),
            relative_path=Path("b.py"),
            language="python",
            module_qn="project.b",
            container_qn="project",
        ),
        success=True,
        function_registry_entries={
            "project.b.ClassB": "Class",
            "project.b.func_b": "Function",
        },
        simple_name_entries={
            "ClassB": ["project.b.ClassB"],
            "func_b": ["project.b.func_b"],
        },
    )

    registry, lookup = executor._aggregate_registries([result1, result2])

    # Check registry contains all entries
    assert "project.a.ClassA" in registry
    assert "project.b.ClassB" in registry
    assert registry["project.a.ClassA"] == "Class"
    assert registry["project.b.func_b"] == "Function"


def test_aggregate_registries_merges_simple_name_lookup() -> None:
    """Test that _aggregate_registries merges simple name lookups."""
    executor = ParallelExecutor()

    result1 = FileParseResult(
        task=FileParseTask(
            file_path=Path("/repo/a.py"),
            relative_path=Path("a.py"),
            language="python",
            module_qn="project.a",
            container_qn="project",
        ),
        success=True,
        function_registry_entries={"project.a.MyClass": "Class"},
        simple_name_entries={"MyClass": ["project.a.MyClass"]},
    )

    result2 = FileParseResult(
        task=FileParseTask(
            file_path=Path("/repo/b.py"),
            relative_path=Path("b.py"),
            language="python",
            module_qn="project.b",
            container_qn="project",
        ),
        success=True,
        function_registry_entries={"project.b.MyClass": "Class"},
        simple_name_entries={"MyClass": ["project.b.MyClass"]},
    )

    _, lookup = executor._aggregate_registries([result1, result2])

    # Both MyClass entries should be in lookup
    assert "MyClass" in lookup
    assert "project.a.MyClass" in lookup["MyClass"]
    assert "project.b.MyClass" in lookup["MyClass"]


def test_aggregate_registries_skips_failed_results() -> None:
    """Test that _aggregate_registries skips failed results."""
    executor = ParallelExecutor()

    success_result = FileParseResult(
        task=FileParseTask(
            file_path=Path("/repo/a.py"),
            relative_path=Path("a.py"),
            language="python",
            module_qn="project.a",
            container_qn="project",
        ),
        success=True,
        function_registry_entries={"project.a.ClassA": "Class"},
        simple_name_entries={"ClassA": ["project.a.ClassA"]},
    )

    failed_result = FileParseResult(
        task=FileParseTask(
            file_path=Path("/repo/b.py"),
            relative_path=Path("b.py"),
            language="python",
            module_qn="project.b",
            container_qn="project",
        ),
        success=False,
        error="Parse error",
        function_registry_entries={"project.b.ClassB": "Class"},
        simple_name_entries={"ClassB": ["project.b.ClassB"]},
    )

    registry, lookup = executor._aggregate_registries([success_result, failed_result])

    # Only successful result should be included
    assert "project.a.ClassA" in registry
    assert "project.b.ClassB" not in registry


# =============================================================================
# Tests for _resolve_call_relationships()
# =============================================================================


def test_resolve_call_relationships_resolves_local_call() -> None:
    """Test that _resolve_call_relationships resolves local function calls."""
    executor = ParallelExecutor()

    raw_calls = [
        RawCallData(
            caller_qn="project.test.caller",
            callee_name="callee",
            object_name=None,
            line_number=10,
            module_qn="project.test",
        ),
    ]

    function_registry = {
        "project.test.caller": "Function",
        "project.test.callee": "Function",
    }

    simple_name_lookup = {
        "caller": ["project.test.caller"],
        "callee": ["project.test.callee"],
    }

    resolved = executor._resolve_call_relationships(
        raw_calls, function_registry, simple_name_lookup
    )

    assert len(resolved) == 1
    assert resolved[0].rel_type == "CALLS"
    assert resolved[0].from_value == "project.test.caller"
    assert resolved[0].to_value == "project.test.callee"


def test_resolve_call_relationships_prefers_local_module() -> None:
    """Test that _resolve_call_relationships prefers local module matches."""
    executor = ParallelExecutor()

    raw_calls = [
        RawCallData(
            caller_qn="project.a.caller",
            callee_name="helper",
            object_name=None,
            line_number=10,
            module_qn="project.a",
        ),
    ]

    function_registry = {
        "project.a.caller": "Function",
        "project.a.helper": "Function",  # Local
        "project.b.helper": "Function",  # Different module
    }

    simple_name_lookup = {
        "helper": ["project.a.helper", "project.b.helper"],
    }

    resolved = executor._resolve_call_relationships(
        raw_calls, function_registry, simple_name_lookup
    )

    assert len(resolved) == 1
    # Should prefer local module
    assert resolved[0].to_value == "project.a.helper"


def test_resolve_call_relationships_handles_no_matches() -> None:
    """Test that _resolve_call_relationships handles no matches gracefully."""
    executor = ParallelExecutor()

    raw_calls = [
        RawCallData(
            caller_qn="project.test.caller",
            callee_name="nonexistent",
            object_name=None,
            line_number=10,
            module_qn="project.test",
        ),
    ]

    function_registry = {"project.test.caller": "Function"}
    simple_name_lookup: dict[str, list[str]] = {}

    resolved = executor._resolve_call_relationships(
        raw_calls, function_registry, simple_name_lookup
    )

    assert len(resolved) == 0


def test_resolve_call_relationships_handles_missing_caller_type() -> None:
    """Test that _resolve_call_relationships handles missing caller type."""
    executor = ParallelExecutor()

    raw_calls = [
        RawCallData(
            caller_qn="project.test.unknown",
            callee_name="callee",
            object_name=None,
            line_number=10,
            module_qn="project.test",
        ),
    ]

    function_registry = {"project.test.callee": "Function"}
    simple_name_lookup = {"callee": ["project.test.callee"]}

    resolved = executor._resolve_call_relationships(
        raw_calls, function_registry, simple_name_lookup
    )

    # Should not create relationship if caller type is unknown
    assert len(resolved) == 0


# =============================================================================
# Tests for _resolve_inheritance_relationships()
# =============================================================================


def test_resolve_inheritance_creates_inherits_relationship() -> None:
    """Test that _resolve_inheritance_relationships creates INHERITS."""
    executor = ParallelExecutor()

    inheritance_data = [
        InheritanceData(
            child_class_qn="project.test.Child",
            parent_simple_names=["Parent"],
        ),
    ]

    function_registry = {
        "project.test.Child": "Class",
        "project.test.Parent": "Class",
    }

    simple_name_lookup = {
        "Parent": ["project.test.Parent"],
    }

    resolved = executor._resolve_inheritance_relationships(
        inheritance_data, function_registry, simple_name_lookup
    )

    assert len(resolved) == 1
    assert resolved[0].rel_type == "INHERITS"
    assert resolved[0].from_value == "project.test.Child"
    assert resolved[0].to_value == "project.test.Parent"


def test_resolve_inheritance_handles_multiple_parents() -> None:
    """Test that _resolve_inheritance_relationships handles multiple inheritance."""
    executor = ParallelExecutor()

    inheritance_data = [
        InheritanceData(
            child_class_qn="project.test.Child",
            parent_simple_names=["ParentA", "ParentB"],
        ),
    ]

    function_registry = {
        "project.test.Child": "Class",
        "project.test.ParentA": "Class",
        "project.test.ParentB": "Class",
    }

    simple_name_lookup = {
        "ParentA": ["project.test.ParentA"],
        "ParentB": ["project.test.ParentB"],
    }

    resolved = executor._resolve_inheritance_relationships(
        inheritance_data, function_registry, simple_name_lookup
    )

    assert len(resolved) == 2
    parent_values = [r.to_value for r in resolved]
    assert "project.test.ParentA" in parent_values
    assert "project.test.ParentB" in parent_values


def test_resolve_inheritance_skips_ambiguous_parents() -> None:
    """Test that _resolve_inheritance_relationships skips ambiguous matches."""
    executor = ParallelExecutor()

    inheritance_data = [
        InheritanceData(
            child_class_qn="project.test.Child",
            parent_simple_names=["Parent"],
        ),
    ]

    function_registry = {
        "project.test.Child": "Class",
        "project.a.Parent": "Class",
        "project.b.Parent": "Class",  # Ambiguous - two Parents
    }

    simple_name_lookup = {
        "Parent": ["project.a.Parent", "project.b.Parent"],
    }

    resolved = executor._resolve_inheritance_relationships(
        inheritance_data, function_registry, simple_name_lookup
    )

    # Should skip ambiguous matches
    assert len(resolved) == 0


def test_resolve_inheritance_handles_unknown_parent() -> None:
    """Test that _resolve_inheritance_relationships handles unknown parents."""
    executor = ParallelExecutor()

    inheritance_data = [
        InheritanceData(
            child_class_qn="project.test.Child",
            parent_simple_names=["UnknownParent"],
        ),
    ]

    function_registry = {"project.test.Child": "Class"}
    simple_name_lookup: dict[str, list[str]] = {}

    resolved = executor._resolve_inheritance_relationships(
        inheritance_data, function_registry, simple_name_lookup
    )

    assert len(resolved) == 0


# =============================================================================
# Tests for _calculate_callee_confidence()
# =============================================================================


def test_calculate_confidence_boosts_same_module() -> None:
    """Test that confidence calculation boosts same-module callees."""
    executor = ParallelExecutor()

    # Same module
    score_same = executor._calculate_callee_confidence(
        caller_qn="project.mod.caller",
        callee_qn="project.mod.callee",
        module_qn="project.mod",
        object_name=None,
        simple_name_lookup={"callee": ["project.mod.callee"]},
    )

    # Different module
    score_diff = executor._calculate_callee_confidence(
        caller_qn="project.mod.caller",
        callee_qn="project.other.callee",
        module_qn="project.mod",
        object_name=None,
        simple_name_lookup={"callee": ["project.other.callee"]},
    )

    assert score_same > score_diff


def test_calculate_confidence_boosts_self_calls() -> None:
    """Test that confidence calculation boosts self.method() calls."""
    executor = ParallelExecutor()

    # self call to same class method
    score = executor._calculate_callee_confidence(
        caller_qn="project.mod.MyClass.caller",
        callee_qn="project.mod.MyClass.callee",
        module_qn="project.mod",
        object_name="self",
        simple_name_lookup={"callee": ["project.mod.MyClass.callee"]},
    )

    # Should get a significant boost for self calls
    assert score >= 0.4


def test_calculate_confidence_boosts_unique_names() -> None:
    """Test that confidence calculation boosts unique function names."""
    executor = ParallelExecutor()

    # Unique name
    score_unique = executor._calculate_callee_confidence(
        caller_qn="project.mod.caller",
        callee_qn="project.other.unique_func",
        module_qn="project.mod",
        object_name=None,
        simple_name_lookup={"unique_func": ["project.other.unique_func"]},
    )

    # Common name (multiple matches)
    score_common = executor._calculate_callee_confidence(
        caller_qn="project.mod.caller",
        callee_qn="project.other.common",
        module_qn="project.mod",
        object_name=None,
        simple_name_lookup={
            "common": [
                "project.a.common",
                "project.b.common",
                "project.c.common",
                "project.other.common",
            ]
        },
    )

    assert score_unique > score_common


# =============================================================================
# Tests for error handling
# =============================================================================


def test_execute_handles_nonexistent_file() -> None:
    """Test that execute handles nonexistent files gracefully."""
    task = FileParseTask(
        file_path=Path("/nonexistent/path/to/file.py"),
        relative_path=Path("file.py"),
        language="python",
        module_qn="project.file",
        container_qn="project",
    )
    batch = WorkBatch(batch_id=1, tasks=[task], estimated_duration_seconds=None)

    executor = ParallelExecutor(worker_count=2)
    result = executor.execute([batch])

    # Should have error result but not crash
    assert result.total_files == 1
    assert result.failed_files == 1
    assert result.successful_files == 0


def test_execute_handles_mixed_success_failure() -> None:
    """Test that execute handles mix of success and failure."""
    import tempfile

    # Create a valid file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False
    ) as f:
        f.write("def valid(): pass")
        valid_path = Path(f.name)

    valid_task = FileParseTask(
        file_path=valid_path,
        relative_path=Path("valid.py"),
        language="python",
        module_qn="project.valid",
        container_qn="project",
    )

    invalid_task = FileParseTask(
        file_path=Path("/nonexistent/file.py"),
        relative_path=Path("invalid.py"),
        language="python",
        module_qn="project.invalid",
        container_qn="project",
    )

    batch = WorkBatch(
        batch_id=1,
        tasks=[valid_task, invalid_task],
        estimated_duration_seconds=None,
    )

    executor = ParallelExecutor(worker_count=2)
    result = executor.execute([batch])

    assert result.total_files == 2
    assert result.successful_files == 1
    assert result.failed_files == 1


# =============================================================================
# Tests for worker metrics
# =============================================================================


def test_execute_collects_worker_metrics_with_real_file() -> None:
    """Test that execute collects worker metrics with real files."""
    import tempfile

    content = "def func(): pass"
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False
    ) as f:
        f.write(content)
        file_path = Path(f.name)

    task = FileParseTask(
        file_path=file_path,
        relative_path=Path("test.py"),
        language="python",
        module_qn="project.test",
        container_qn="project",
    )
    batch = WorkBatch(batch_id=1, tasks=[task], estimated_duration_seconds=None)

    executor = ParallelExecutor(worker_count=2)
    result = executor.execute([batch])

    assert len(result.worker_metrics) > 0
    # At least one worker should have processed files
    total_processed = sum(m.files_processed for m in result.worker_metrics.values())
    assert total_processed == 1
