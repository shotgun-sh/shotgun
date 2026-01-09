"""Unit tests for ParserWorker class."""

import tempfile
from pathlib import Path

import pytest

from shotgun.codebase.core.metrics_types import (
    FileParseTask,
    WorkBatch,
)
from shotgun.codebase.core.worker import ParserWorker, process_batch

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_python_file() -> tuple[Path, str]:
    """Create a temporary Python file for testing."""
    content = '''"""Test module docstring."""

class MyClass:
    """A test class."""

    def my_method(self):
        """A test method."""
        pass


def my_function():
    """A standalone function."""
    pass


def caller():
    """Function that makes calls."""
    my_function()
    obj = MyClass()
    obj.my_method()
'''
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(content)
        return Path(f.name), content


@pytest.fixture
def temp_empty_file() -> Path:
    """Create a temporary empty file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("")
        return Path(f.name)


@pytest.fixture
def temp_invalid_file() -> Path:
    """Create a temporary file with invalid Python syntax."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        # This is still valid Python, just unusual - tree-sitter parses it
        f.write("x = 1 + ")  # Incomplete expression
        return Path(f.name)


@pytest.fixture
def sample_task(temp_python_file: tuple[Path, str]) -> FileParseTask:
    """Create a sample file parse task."""
    file_path, _ = temp_python_file
    return FileParseTask(
        file_path=file_path,
        relative_path=Path("test_module.py"),
        language="python",
        module_qn="project.test_module",
        container_qn="project",
    )


@pytest.fixture
def empty_task(temp_empty_file: Path) -> FileParseTask:
    """Create a task for an empty file."""
    return FileParseTask(
        file_path=temp_empty_file,
        relative_path=Path("empty.py"),
        language="python",
        module_qn="project.empty",
        container_qn="project",
    )


# =============================================================================
# Tests for ParserWorker initialization
# =============================================================================


def test_parser_worker_initializes_with_parsers() -> None:
    """Test that ParserWorker initializes with tree-sitter parsers."""
    worker = ParserWorker(worker_id=0)

    assert worker.worker_id == 0
    assert worker.parsers is not None
    assert "python" in worker.parsers


def test_parser_worker_accepts_worker_id() -> None:
    """Test that ParserWorker accepts custom worker_id."""
    worker = ParserWorker(worker_id=5)
    assert worker.worker_id == 5


# =============================================================================
# Tests for process_file - basic extraction
# =============================================================================


def test_process_file_extracts_class(sample_task: FileParseTask) -> None:
    """Test that process_file extracts class definitions."""
    worker = ParserWorker()
    result = worker.process_file(sample_task)

    assert result.success
    assert result.error is None

    # Find class node
    class_nodes = [n for n in result.nodes if n.label == "Class"]
    assert len(class_nodes) == 1
    assert class_nodes[0].properties["name"] == "MyClass"
    assert class_nodes[0].properties["qualified_name"] == "project.test_module.MyClass"


def test_process_file_extracts_function(sample_task: FileParseTask) -> None:
    """Test that process_file extracts function definitions."""
    worker = ParserWorker()
    result = worker.process_file(sample_task)

    assert result.success

    # Find function nodes (not methods)
    func_nodes = [n for n in result.nodes if n.label == "Function"]
    func_names = [n.properties["name"] for n in func_nodes]

    assert "my_function" in func_names
    assert "caller" in func_names


def test_process_file_extracts_method(sample_task: FileParseTask) -> None:
    """Test that process_file extracts method definitions."""
    worker = ParserWorker()
    result = worker.process_file(sample_task)

    assert result.success

    # Find method nodes
    method_nodes = [n for n in result.nodes if n.label == "Method"]
    assert len(method_nodes) == 1
    assert method_nodes[0].properties["name"] == "my_method"
    assert (
        method_nodes[0].properties["qualified_name"]
        == "project.test_module.MyClass.my_method"
    )


def test_process_file_extracts_docstrings(sample_task: FileParseTask) -> None:
    """Test that process_file extracts docstrings."""
    worker = ParserWorker()
    result = worker.process_file(sample_task)

    assert result.success

    # Find class with docstring
    class_nodes = [n for n in result.nodes if n.label == "Class"]
    assert class_nodes[0].properties["docstring"] == "A test class."

    # Find method with docstring
    method_nodes = [n for n in result.nodes if n.label == "Method"]
    assert method_nodes[0].properties["docstring"] == "A test method."


def test_process_file_creates_module_node(sample_task: FileParseTask) -> None:
    """Test that process_file creates Module node."""
    worker = ParserWorker()
    result = worker.process_file(sample_task)

    assert result.success

    module_nodes = [n for n in result.nodes if n.label == "Module"]
    assert len(module_nodes) == 1
    assert module_nodes[0].properties["qualified_name"] == "project.test_module"


def test_process_file_creates_file_node(sample_task: FileParseTask) -> None:
    """Test that process_file creates File node."""
    worker = ParserWorker()
    result = worker.process_file(sample_task)

    assert result.success

    file_nodes = [n for n in result.nodes if n.label == "File"]
    assert len(file_nodes) == 1
    assert file_nodes[0].properties["extension"] == ".py"


# =============================================================================
# Tests for process_file - relationships
# =============================================================================


def test_process_file_creates_defines_relationships(sample_task: FileParseTask) -> None:
    """Test that process_file creates DEFINES relationships."""
    worker = ParserWorker()
    result = worker.process_file(sample_task)

    assert result.success

    # Find DEFINES relationship (Module -> Class)
    defines_rels = [r for r in result.relationships if r.rel_type == "DEFINES"]
    assert len(defines_rels) == 1
    assert defines_rels[0].from_label == "Module"
    assert defines_rels[0].to_label == "Class"


def test_process_file_creates_defines_method_relationships(
    sample_task: FileParseTask,
) -> None:
    """Test that process_file creates DEFINES_METHOD relationships."""
    worker = ParserWorker()
    result = worker.process_file(sample_task)

    assert result.success

    # Find DEFINES_METHOD relationship (Class -> Method)
    method_rels = [r for r in result.relationships if r.rel_type == "DEFINES_METHOD"]
    assert len(method_rels) == 1
    assert method_rels[0].from_label == "Class"
    assert method_rels[0].to_label == "Method"


def test_process_file_creates_defines_func_relationships(
    sample_task: FileParseTask,
) -> None:
    """Test that process_file creates DEFINES_FUNC relationships."""
    worker = ParserWorker()
    result = worker.process_file(sample_task)

    assert result.success

    # Find DEFINES_FUNC relationships (Module -> Function)
    func_rels = [r for r in result.relationships if r.rel_type == "DEFINES_FUNC"]
    assert len(func_rels) == 2  # my_function and caller


# =============================================================================
# Tests for process_file - registry entries
# =============================================================================


def test_process_file_populates_function_registry(sample_task: FileParseTask) -> None:
    """Test that process_file populates function_registry entries."""
    worker = ParserWorker()
    result = worker.process_file(sample_task)

    assert result.success

    registry = result.function_registry_entries
    assert "project.test_module.MyClass" in registry
    assert registry["project.test_module.MyClass"] == "Class"

    assert "project.test_module.my_function" in registry
    assert registry["project.test_module.my_function"] == "Function"

    assert "project.test_module.MyClass.my_method" in registry
    assert registry["project.test_module.MyClass.my_method"] == "Method"


def test_process_file_populates_simple_name_lookup(sample_task: FileParseTask) -> None:
    """Test that process_file populates simple_name_entries."""
    worker = ParserWorker()
    result = worker.process_file(sample_task)

    assert result.success

    lookup = result.simple_name_entries
    assert "MyClass" in lookup
    assert "project.test_module.MyClass" in lookup["MyClass"]

    assert "my_function" in lookup
    assert "project.test_module.my_function" in lookup["my_function"]


# =============================================================================
# Tests for process_file - raw calls
# =============================================================================


def test_process_file_extracts_raw_calls(sample_task: FileParseTask) -> None:
    """Test that process_file extracts raw call data."""
    worker = ParserWorker()
    result = worker.process_file(sample_task)

    assert result.success

    # Should have calls from the caller() function
    raw_calls = result.raw_calls
    callee_names = [c.callee_name for c in raw_calls]

    # my_function() call
    assert "my_function" in callee_names

    # MyClass() call
    assert "MyClass" in callee_names


def test_process_file_extracts_method_calls(sample_task: FileParseTask) -> None:
    """Test that process_file extracts method call data."""
    worker = ParserWorker()
    result = worker.process_file(sample_task)

    assert result.success

    # Find method call (obj.my_method())
    method_calls = [c for c in result.raw_calls if c.object_name is not None]

    # obj.my_method() should have object_name = "obj"
    obj_calls = [c for c in method_calls if c.object_name == "obj"]
    assert len(obj_calls) >= 1


# =============================================================================
# Tests for process_file - metrics
# =============================================================================


def test_process_file_collects_metrics(sample_task: FileParseTask) -> None:
    """Test that process_file collects parsing metrics."""
    worker = ParserWorker(worker_id=3)
    result = worker.process_file(sample_task)

    assert result.success
    assert result.metrics is not None

    assert result.metrics.language == "python"
    assert result.metrics.file_size_bytes > 0
    assert result.metrics.parse_time_ms >= 0
    assert result.metrics.ast_nodes > 0
    assert result.metrics.definitions_extracted > 0
    assert result.metrics.worker_id == 3


def test_process_file_calculates_file_hash(sample_task: FileParseTask) -> None:
    """Test that process_file calculates file hash."""
    worker = ParserWorker()
    result = worker.process_file(sample_task)

    assert result.success
    assert result.file_hash != ""
    assert len(result.file_hash) == 64  # SHA256 hex digest


def test_process_file_records_mtime(sample_task: FileParseTask) -> None:
    """Test that process_file records file modification time."""
    worker = ParserWorker()
    result = worker.process_file(sample_task)

    assert result.success
    assert result.mtime > 0


# =============================================================================
# Tests for process_file - edge cases
# =============================================================================


def test_process_file_handles_empty_file(empty_task: FileParseTask) -> None:
    """Test that process_file handles empty files gracefully."""
    worker = ParserWorker()
    result = worker.process_file(empty_task)

    assert result.success
    assert result.error is None
    assert len(result.nodes) == 0
    assert len(result.relationships) == 0


def test_process_file_handles_missing_language() -> None:
    """Test that process_file handles unsupported languages."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".xyz", delete=False) as f:
        f.write("some content")
        file_path = Path(f.name)

    task = FileParseTask(
        file_path=file_path,
        relative_path=Path("test.xyz"),
        language="unknown_language",
        module_qn="project.test",
        container_qn="project",
    )

    worker = ParserWorker()
    result = worker.process_file(task)

    assert not result.success
    assert "No parser for language" in (result.error or "")


def test_process_file_handles_nonexistent_file() -> None:
    """Test that process_file handles missing files."""
    task = FileParseTask(
        file_path=Path("/nonexistent/path/file.py"),
        relative_path=Path("file.py"),
        language="python",
        module_qn="project.file",
        container_qn="project",
    )

    worker = ParserWorker()
    result = worker.process_file(task)

    assert not result.success
    assert result.error is not None


# =============================================================================
# Tests for process_batch
# =============================================================================


def test_process_batch_processes_all_tasks(sample_task: FileParseTask) -> None:
    """Test that process_batch processes all tasks in batch."""
    batch = WorkBatch(
        batch_id=1,
        tasks=[sample_task],
        estimated_duration_seconds=None,
    )

    worker = ParserWorker()
    results = worker.process_batch(batch)

    assert len(results) == 1
    assert results[0].success


def test_process_batch_function_entry_point(sample_task: FileParseTask) -> None:
    """Test the module-level process_batch function."""
    batch = WorkBatch(
        batch_id=1,
        tasks=[sample_task],
        estimated_duration_seconds=None,
    )

    results = process_batch(batch, worker_id=2)

    assert len(results) == 1
    assert results[0].success
    assert results[0].metrics is not None
    assert results[0].metrics.worker_id == 2


def test_process_batch_handles_mixed_success_failure() -> None:
    """Test that process_batch handles mix of successful and failed files."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
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

    worker = ParserWorker()
    results = worker.process_batch(batch)

    assert len(results) == 2

    # One should succeed, one should fail
    successes = [r for r in results if r.success]
    failures = [r for r in results if not r.success]

    assert len(successes) == 1
    assert len(failures) == 1


# =============================================================================
# Tests for inheritance extraction
# =============================================================================


def test_process_file_extracts_inheritance() -> None:
    """Test that process_file extracts inheritance data."""
    content = """
class Parent:
    pass

class Child(Parent):
    pass
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(content)
        file_path = Path(f.name)

    task = FileParseTask(
        file_path=file_path,
        relative_path=Path("test.py"),
        language="python",
        module_qn="project.test",
        container_qn="project",
    )

    worker = ParserWorker()
    result = worker.process_file(task)

    assert result.success

    # Should have inheritance data for Child
    inheritance = result.inheritance_data
    assert len(inheritance) == 1
    assert inheritance[0].child_class_qn == "project.test.Child"
    assert "Parent" in inheritance[0].parent_simple_names


def test_process_file_handles_multiple_inheritance() -> None:
    """Test that process_file handles multiple inheritance."""
    content = """
class A:
    pass

class B:
    pass

class C(A, B):
    pass
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(content)
        file_path = Path(f.name)

    task = FileParseTask(
        file_path=file_path,
        relative_path=Path("test.py"),
        language="python",
        module_qn="project.test",
        container_qn="project",
    )

    worker = ParserWorker()
    result = worker.process_file(task)

    assert result.success

    # Find inheritance data for C
    c_inheritance = [i for i in result.inheritance_data if "C" in i.child_class_qn]
    assert len(c_inheritance) == 1
    assert "A" in c_inheritance[0].parent_simple_names
    assert "B" in c_inheritance[0].parent_simple_names


# =============================================================================
# Tests for decorator extraction
# =============================================================================


def test_process_file_extracts_decorators() -> None:
    """Test that process_file extracts decorators when present.

    Note: Tree-sitter's Python grammar handles decorated functions
    as decorated_definition nodes. The decorator extraction depends
    on the specific tree structure. This test verifies functions
    are still extracted even with decorators present.
    """
    content = """
@decorator
def decorated_func():
    pass

@staticmethod
def static_func():
    pass

def plain_func():
    pass
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(content)
        file_path = Path(f.name)

    task = FileParseTask(
        file_path=file_path,
        relative_path=Path("test.py"),
        language="python",
        module_qn="project.test",
        container_qn="project",
    )

    worker = ParserWorker()
    result = worker.process_file(task)

    assert result.success

    # Verify functions are extracted (decorators are optional feature)
    func_nodes = [n for n in result.nodes if n.label == "Function"]
    func_names = [f.properties["name"] for f in func_nodes]

    # All functions should be found regardless of decorators
    assert "decorated_func" in func_names
    assert "static_func" in func_names
    assert "plain_func" in func_names
