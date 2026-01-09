"""Integration tests for parallel execution correctness.

These tests verify that parallel file parsing produces the same
results as sequential parsing.
"""

import tempfile
from pathlib import Path

import pytest

from shotgun.codebase.core.metrics_types import (
    FileInfo,
    FileParseTask,
    WorkBatch,
)
from shotgun.codebase.core.parallel_executor import ParallelExecutor
from shotgun.codebase.core.work_distributor import WorkDistributor
from shotgun.codebase.core.worker import ParserWorker


@pytest.fixture
def sample_codebase() -> Path:
    """Create a sample codebase structure for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # Create a module with classes and functions
        module_a = root / "module_a.py"
        module_a.write_text('''"""Module A with various definitions."""

class BaseClass:
    """A base class."""

    def base_method(self):
        """Base method."""
        pass


class DerivedClass(BaseClass):
    """A derived class."""

    def derived_method(self):
        """Derived method that calls base."""
        self.base_method()


def standalone_func():
    """A standalone function."""
    obj = DerivedClass()
    obj.derived_method()
''')

        # Create another module
        module_b = root / "module_b.py"
        module_b.write_text('''"""Module B with more definitions."""

from module_a import BaseClass

class AnotherClass(BaseClass):
    """Another derived class."""

    def another_method(self):
        """Method that makes calls."""
        return "result"


def helper_func():
    """A helper function."""
    return AnotherClass()
''')

        # Create a subdirectory with modules
        subdir = root / "subpackage"
        subdir.mkdir()
        (subdir / "__init__.py").write_text('"""Subpackage."""\n')

        module_c = subdir / "module_c.py"
        module_c.write_text('''"""Module C in subpackage."""

class SubpackageClass:
    """Class in subpackage."""

    def subpackage_method(self):
        """Method in subpackage class."""
        pass
''')

        yield root


def test_parallel_extracts_all_definitions(sample_codebase: Path) -> None:
    """Test that parallel execution extracts all class and function definitions."""
    # Build tasks for all Python files
    tasks = []
    for py_file in sample_codebase.rglob("*.py"):
        relative = py_file.relative_to(sample_codebase)
        if py_file.name == "__init__.py":
            module_qn = f"project.{'.'.join(relative.parent.parts)}"
        else:
            module_qn = f"project.{'.'.join(relative.with_suffix('').parts)}"

        tasks.append(
            FileParseTask(
                file_path=py_file,
                relative_path=relative,
                language="python",
                module_qn=module_qn,
                container_qn="project",
            )
        )

    # Create batch and execute
    batch = WorkBatch(batch_id=1, tasks=tasks, estimated_duration_seconds=None)
    executor = ParallelExecutor(worker_count=2)
    result = executor.execute([batch])

    # Verify all files processed successfully
    assert result.total_files == 4  # module_a, module_b, __init__, module_c
    assert result.successful_files == 4
    assert result.failed_files == 0

    # Collect all class names
    all_classes = []
    for file_result in result.results:
        for node in file_result.nodes:
            if node.label == "Class":
                all_classes.append(node.properties["name"])

    # Verify expected classes
    assert "BaseClass" in all_classes
    assert "DerivedClass" in all_classes
    assert "AnotherClass" in all_classes
    assert "SubpackageClass" in all_classes


def test_parallel_extracts_inheritance(sample_codebase: Path) -> None:
    """Test that parallel execution correctly extracts inheritance data."""
    tasks = []
    for py_file in sample_codebase.rglob("*.py"):
        relative = py_file.relative_to(sample_codebase)
        if py_file.name == "__init__.py":
            module_qn = f"project.{'.'.join(relative.parent.parts)}"
        else:
            module_qn = f"project.{'.'.join(relative.with_suffix('').parts)}"

        tasks.append(
            FileParseTask(
                file_path=py_file,
                relative_path=relative,
                language="python",
                module_qn=module_qn,
                container_qn="project",
            )
        )

    batch = WorkBatch(batch_id=1, tasks=tasks, estimated_duration_seconds=None)
    executor = ParallelExecutor(worker_count=2)
    result = executor.execute([batch])

    # Collect all inheritance data
    all_inheritance = []
    for file_result in result.results:
        all_inheritance.extend(file_result.inheritance_data)

    # Verify inheritance relationships
    child_to_parents = {
        data.child_class_qn: data.parent_simple_names for data in all_inheritance
    }

    # DerivedClass inherits from BaseClass
    derived_key = [k for k in child_to_parents if "DerivedClass" in k]
    assert len(derived_key) == 1
    assert "BaseClass" in child_to_parents[derived_key[0]]

    # AnotherClass inherits from BaseClass
    another_key = [k for k in child_to_parents if "AnotherClass" in k]
    assert len(another_key) == 1
    assert "BaseClass" in child_to_parents[another_key[0]]


def test_parallel_builds_function_registry(sample_codebase: Path) -> None:
    """Test that parallel execution builds complete function registry."""
    tasks = []
    for py_file in sample_codebase.rglob("*.py"):
        relative = py_file.relative_to(sample_codebase)
        if py_file.name == "__init__.py":
            module_qn = f"project.{'.'.join(relative.parent.parts)}"
        else:
            module_qn = f"project.{'.'.join(relative.with_suffix('').parts)}"

        tasks.append(
            FileParseTask(
                file_path=py_file,
                relative_path=relative,
                language="python",
                module_qn=module_qn,
                container_qn="project",
            )
        )

    batch = WorkBatch(batch_id=1, tasks=tasks, estimated_duration_seconds=None)
    executor = ParallelExecutor(worker_count=2)
    result = executor.execute([batch])

    # Verify registry is populated
    registry = result.function_registry
    assert len(registry) > 0

    # Verify registry contains expected types
    assert any(v == "Class" for v in registry.values())
    assert any(v == "Function" for v in registry.values())
    assert any(v == "Method" for v in registry.values())

    # Verify simple name lookup
    lookup = result.simple_name_lookup
    assert "BaseClass" in lookup
    assert "DerivedClass" in lookup
    assert "standalone_func" in lookup


def test_parallel_matches_sequential(sample_codebase: Path) -> None:
    """Test that parallel execution produces same results as sequential."""
    # Build tasks
    tasks = []
    for py_file in sample_codebase.rglob("*.py"):
        relative = py_file.relative_to(sample_codebase)
        if py_file.name == "__init__.py":
            module_qn = f"project.{'.'.join(relative.parent.parts)}"
        else:
            module_qn = f"project.{'.'.join(relative.with_suffix('').parts)}"

        tasks.append(
            FileParseTask(
                file_path=py_file,
                relative_path=relative,
                language="python",
                module_qn=module_qn,
                container_qn="project",
            )
        )

    # Run sequential (single worker processes tasks one by one)
    worker = ParserWorker(worker_id=0)
    sequential_results = []
    sequential_registry: dict[str, str] = {}
    sequential_lookup: dict[str, list[str]] = {}

    for task in tasks:
        result = worker.process_file(task)
        sequential_results.append(result)
        sequential_registry.update(result.function_registry_entries)
        for name, qns in result.simple_name_entries.items():
            if name not in sequential_lookup:
                sequential_lookup[name] = []
            sequential_lookup[name].extend(qns)

    # Run parallel
    batch = WorkBatch(batch_id=1, tasks=tasks, estimated_duration_seconds=None)
    executor = ParallelExecutor(worker_count=2)
    parallel_result = executor.execute([batch])

    # Compare results
    assert parallel_result.total_files == len(sequential_results)
    assert parallel_result.successful_files == sum(
        1 for r in sequential_results if r.success
    )

    # Compare registries
    assert set(parallel_result.function_registry.keys()) == set(
        sequential_registry.keys()
    )
    for key in sequential_registry:
        assert parallel_result.function_registry[key] == sequential_registry[key]

    # Compare simple name lookups
    for name in sequential_lookup:
        assert name in parallel_result.simple_name_lookup
        assert set(parallel_result.simple_name_lookup[name]) == set(
            sequential_lookup[name]
        )


def test_work_distributor_integration(sample_codebase: Path) -> None:
    """Test that WorkDistributor and ParallelExecutor work together."""
    # Build FileInfo list
    file_infos = []
    for py_file in sample_codebase.rglob("*.py"):
        relative = py_file.relative_to(sample_codebase)
        if py_file.name == "__init__.py":
            module_qn = f"project.{'.'.join(relative.parent.parts)}"
        else:
            module_qn = f"project.{'.'.join(relative.with_suffix('').parts)}"

        file_infos.append(
            FileInfo(
                file_path=py_file,
                relative_path=relative,
                language="python",
                module_qn=module_qn,
                container_qn="project",
                file_size_bytes=py_file.stat().st_size,
            )
        )

    # Distribute work
    distributor = WorkDistributor(worker_count=2, batch_size=2)
    batches = distributor.create_batches(file_infos)

    # Execute in parallel
    executor = ParallelExecutor(worker_count=2)
    result = executor.execute(batches)

    # Verify all files processed
    assert result.total_files == len(file_infos)
    assert result.successful_files == len(file_infos)
    assert result.failed_files == 0


def test_parallel_handles_empty_files(sample_codebase: Path) -> None:
    """Test that parallel execution handles empty files gracefully."""
    # Create an empty file
    empty_file = sample_codebase / "empty.py"
    empty_file.write_text("")

    task = FileParseTask(
        file_path=empty_file,
        relative_path=Path("empty.py"),
        language="python",
        module_qn="project.empty",
        container_qn="project",
    )

    batch = WorkBatch(batch_id=1, tasks=[task], estimated_duration_seconds=None)
    executor = ParallelExecutor(worker_count=2)
    result = executor.execute([batch])

    # Should succeed but with no definitions
    assert result.total_files == 1
    assert result.successful_files == 1
    assert result.failed_files == 0

    # Empty file should have no nodes
    assert len(result.results[0].nodes) == 0
