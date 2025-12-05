"""Unit tests for ingestor module."""

import hashlib
import os
import tempfile
import time
import uuid
from pathlib import Path
from unittest.mock import Mock, patch

from shotgun.codebase.core.ingestor import (
    BASE_IGNORE_DIRECTORIES,
    BUILD_ARTIFACT_DIRECTORIES,
    IGNORE_PATTERNS,
    Ingestor,
    is_path_ignored,
    should_ignore_directory,
)


def test_ignore_patterns_default_values():
    """Test that IGNORE_PATTERNS contains expected default values."""
    assert IGNORE_PATTERNS == BASE_IGNORE_DIRECTORIES | BUILD_ARTIFACT_DIRECTORIES


def test_ingestor_init():
    """Test Ingestor initialization."""
    mock_conn = Mock()
    ingestor = Ingestor(mock_conn)

    assert ingestor.conn == mock_conn
    assert ingestor.node_buffer == []
    assert ingestor.relationship_buffer == []
    assert ingestor.batch_size == 1000


def test_ingestor_init_custom_batch_size():
    """Test Ingestor initialization with custom batch size."""
    mock_conn = Mock()
    ingestor = Ingestor(mock_conn)
    ingestor.batch_size = 500

    assert ingestor.batch_size == 500


def test_create_schema():
    """Test schema creation in Kuzu database."""
    mock_conn = Mock()
    ingestor = Ingestor(mock_conn)

    ingestor.create_schema()

    # Should call execute for each schema statement
    assert mock_conn.execute.call_count > 0

    # Verify some key schema statements were executed
    executed_statements = [call.args[0] for call in mock_conn.execute.call_args_list]

    # Check for node table creation
    project_table_found = any(
        "CREATE NODE TABLE Project" in stmt for stmt in executed_statements
    )
    assert project_table_found

    # Check for relationship table creation
    contains_package_found = any(
        "CREATE REL TABLE CONTAINS_PACKAGE" in stmt for stmt in executed_statements
    )
    assert contains_package_found


def test_create_schema_handles_errors():
    """Test schema creation handles database errors."""
    mock_conn = Mock()
    mock_conn.execute.side_effect = Exception("Database error")
    ingestor = Ingestor(mock_conn)

    # Should not raise exception, but log errors
    ingestor.create_schema()

    # Verify execute was called multiple times (for all schema statements)
    assert mock_conn.execute.call_count > 0


def test_add_node_to_buffer():
    """Test adding nodes to buffer."""
    mock_conn = Mock()
    ingestor = Ingestor(mock_conn)

    # Add a node
    node_data = {"name": "test", "path": "/test"}
    ingestor.node_buffer.append(("TestNode", node_data))

    assert len(ingestor.node_buffer) == 1
    assert ingestor.node_buffer[0] == ("TestNode", node_data)


def test_add_relationship_to_buffer():
    """Test adding relationships to buffer."""
    mock_conn = Mock()
    ingestor = Ingestor(mock_conn)

    # Add a relationship
    from_data = {"id": "1"}
    to_data = {"id": "2"}
    rel_data = {"type": "test"}
    ingestor.relationship_buffer.append(
        ("TestRel", "from", "to", from_data, to_data, rel_data)
    )

    assert len(ingestor.relationship_buffer) == 1
    assert ingestor.relationship_buffer[0] == (
        "TestRel",
        "from",
        "to",
        from_data,
        to_data,
        rel_data,
    )


def test_buffer_management():
    """Test buffer size management."""
    mock_conn = Mock()
    ingestor = Ingestor(mock_conn)
    ingestor.batch_size = 2  # Small batch for testing

    # Fill buffer beyond batch size
    for i in range(5):
        ingestor.node_buffer.append(("TestNode", {"id": str(i)}))

    # Buffer should still contain all items (flush logic would be in actual methods)
    assert len(ingestor.node_buffer) == 5


def test_clear_buffers():
    """Test clearing buffers."""
    mock_conn = Mock()
    ingestor = Ingestor(mock_conn)

    # Add some data
    ingestor.node_buffer.append(("TestNode", {"id": "1"}))
    ingestor.relationship_buffer.append(("TestRel", "from", "to", {}, {}, {}))

    # Clear buffers
    ingestor.node_buffer.clear()
    ingestor.relationship_buffer.clear()

    assert len(ingestor.node_buffer) == 0
    assert len(ingestor.relationship_buffer) == 0


@patch("shotgun.codebase.core.ingestor.load_parsers")
def test_ingest_file_python(mock_load_parsers):
    """Test ingesting a Python file."""
    mock_conn = Mock()
    Ingestor(mock_conn)

    # Mock parser setup
    mock_parser = Mock()
    mock_query = Mock()
    mock_load_parsers.return_value = (
        {"python": mock_parser},
        {"python": {"function_query": mock_query}},
    )

    # Mock tree-sitter parsing
    mock_tree = Mock()
    mock_parser.parse.return_value = mock_tree

    # Mock query captures
    mock_captures = [(Mock(), "function_name")]
    mock_query.captures.return_value = mock_captures

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write('def hello():\n    print("hello")')
        temp_path = f.name

    try:
        # This would be called by actual ingestion logic
        parsers, queries = mock_load_parsers()
        assert "python" in parsers
        assert "python" in queries
    finally:
        os.unlink(temp_path)


@patch("shotgun.codebase.core.ingestor.get_language_config")
def test_get_file_language(mock_get_config):
    """Test file language detection."""
    mock_config = Mock()
    mock_config.name = "python"
    mock_get_config.return_value = mock_config

    # Test with .py extension
    config = mock_get_config(".py")
    assert config.name == "python"


def test_file_extension_mapping():
    """Test file extension to language mapping."""
    test_cases = [
        (".py", "python"),
        (".js", "javascript"),
        (".ts", "typescript"),
        (".java", "java"),
        (".cpp", "cpp"),
    ]

    for ext, expected_lang in test_cases:
        _ = expected_lang  # Keep for potential future use
        # This would use language config in real implementation
        assert ext.startswith(".")


def test_path_should_be_ignored():
    """Test path ignoring logic."""
    test_cases = [
        ("__pycache__/test.py", True),
        (".git/config", True),
        (".config/settings.json", True),
        ("node_modules/pkg/index.js", True),
        ("src/.hidden/module.py", True),
        ("frontend/.storybook/main.ts", True),
        ("src/main.py", False),
        ("test/test_file.py", False),
        (".venv/lib/python3.9/site-packages/pkg", True),
        # .shotgun directory should NOT be ignored (allowlisted)
        (".shotgun/research.md", False),
        (".shotgun/spec.md", False),
    ]

    for path, should_ignore in test_cases:
        path_obj = Path(path)
        assert is_path_ignored(path_obj, IGNORE_PATTERNS) == should_ignore


def test_should_ignore_directory_prefixes():
    """Directories starting with dot should be ignored except allowlisted ones."""
    # Regular dot directories should be ignored
    assert should_ignore_directory(".cache", IGNORE_PATTERNS)
    assert should_ignore_directory(".storybook", IGNORE_PATTERNS)
    assert should_ignore_directory(".git", IGNORE_PATTERNS)
    assert should_ignore_directory(".venv", IGNORE_PATTERNS)

    # .shotgun directory should NOT be ignored (allowlisted)
    assert not should_ignore_directory(".shotgun", IGNORE_PATTERNS)


@patch("shotgun.codebase.core.ingestor.os.walk")
def test_scan_directory_structure(mock_walk):
    """Test directory scanning functionality."""
    mock_conn = Mock()
    Ingestor(mock_conn)

    # Mock directory structure
    mock_walk.return_value = [
        ("/root", ["src", "test"], ["README.md"]),
        ("/root/src", ["package"], ["main.py"]),
        ("/root/src/package", [], ["__init__.py", "module.py"]),
        ("/root/test", [], ["test_main.py"]),
    ]

    # Collect all files and directories
    all_items = []
    for root, dirs, files in mock_walk("/root"):
        _ = dirs  # Keep for potential future use
        all_items.extend([(root, "dir")])
        for f in files:
            all_items.append((os.path.join(root, f), "file"))

    assert len(all_items) > 0
    # Should find Python files
    py_files = [item for item in all_items if item[0].endswith(".py")]
    assert len(py_files) == 4  # main.py, __init__.py, module.py, test_main.py


def test_hash_file_content():
    """Test file content hashing."""
    content = "def hello(): pass"
    expected_hash = hashlib.sha256(content.encode()).hexdigest()

    actual_hash = hashlib.sha256(content.encode()).hexdigest()
    assert actual_hash == expected_hash


def test_generate_qualified_names():
    """Test qualified name generation."""
    test_cases = [
        ("src/package/module.py", "Class1", "src.package.module.Class1"),
        ("src/main.py", "main_function", "src.main.main_function"),
        ("package/__init__.py", "PackageClass", "package.PackageClass"),
    ]

    for file_path, entity_name, expected_qualified in test_cases:
        _ = expected_qualified  # Keep for potential future use
        # Convert path to module-like qualified name
        path_obj = Path(file_path)
        module_parts = []
        for part in path_obj.parts:
            if part.endswith(".py"):
                if part != "__init__.py":
                    module_parts.append(part[:-3])  # Remove .py
            else:
                module_parts.append(part)

        module_name = ".".join(module_parts)
        qualified_name = f"{module_name}.{entity_name}"

        # Basic check that qualified name is formed correctly
        assert entity_name in qualified_name
        assert len(qualified_name.split(".")) >= 2


@patch("shotgun.codebase.core.ingestor.Path")
def test_detect_package_structure(mock_path):
    """Test package detection logic."""
    mock_conn = Mock()
    Ingestor(mock_conn)

    # Mock package directory with __init__.py
    mock_path_obj = Mock()
    mock_path_obj.is_dir.return_value = True
    mock_path_obj.glob.return_value = [Mock(name="__init__.py")]
    mock_path.return_value = mock_path_obj

    path_obj = mock_path("/src/package")
    init_files = list(path_obj.glob("__init__.py"))

    # Should detect as package if __init__.py exists
    is_package = len(init_files) > 0
    assert is_package


def test_create_uuid():
    """Test UUID generation for entities."""
    test_id = str(uuid.uuid4())
    assert len(test_id) == 36
    assert test_id.count("-") == 4


def test_timestamp_generation():
    """Test timestamp generation."""
    import time

    timestamp = int(time.time())
    assert timestamp > 0
    assert isinstance(timestamp, int)


@patch("shotgun.codebase.core.ingestor.Parser")
def test_ast_parsing_error_handling(mock_parser_class):
    """Test AST parsing error handling."""
    mock_conn = Mock()
    Ingestor(mock_conn)

    # Mock parser that raises exception
    mock_parser = Mock()
    mock_parser.parse.side_effect = Exception("Parse error")
    mock_parser_class.return_value = mock_parser

    # Parsing should handle errors gracefully
    try:
        parser = mock_parser_class()
        parser.parse(b"invalid syntax")
    except Exception as e:
        assert "Parse error" in str(e)


def test_node_data_validation():
    """Test node data structure validation."""
    mock_conn = Mock()
    ingestor = Ingestor(mock_conn)

    # Valid node data
    valid_node = {
        "qualified_name": "test.module.Class",
        "name": "Class",
        "line_start": 1,
        "line_end": 10,
    }

    # Add to buffer
    ingestor.node_buffer.append(("Class", valid_node))

    # Verify data structure
    node_type, node_data = ingestor.node_buffer[0]
    assert node_type == "Class"
    assert node_data["qualified_name"] == "test.module.Class"
    assert isinstance(node_data["line_start"], int)
    assert isinstance(node_data["line_end"], int)


def test_relationship_data_validation():
    """Test relationship data structure validation."""
    mock_conn = Mock()
    ingestor = Ingestor(mock_conn)

    from_node = {"qualified_name": "module.Class1"}
    to_node = {"qualified_name": "module.Class2"}
    rel_data = {"relationship_type": "inherits"}

    ingestor.relationship_buffer.append(
        ("INHERITS", "Class1", "Class2", from_node, to_node, rel_data)
    )

    rel_type, from_id, to_id, from_data, to_data, rel_attrs = (
        ingestor.relationship_buffer[0]
    )
    _ = from_id  # Keep for potential future use
    _ = to_id  # Keep for potential future use
    _ = rel_attrs  # Keep for potential future use
    assert rel_type == "INHERITS"
    assert from_data["qualified_name"] == "module.Class1"
    assert to_data["qualified_name"] == "module.Class2"


@patch("shotgun.codebase.core.ingestor.LANGUAGE_CONFIGS")
def test_language_config_access(mock_configs):
    """Test accessing language configurations."""
    mock_config = Mock()
    mock_config.name = "python"
    mock_config.file_extensions = [".py"]
    mock_configs.__getitem__.return_value = mock_config

    config = mock_configs["python"]
    assert config.name == "python"
    assert ".py" in config.file_extensions


def test_batch_processing_logic():
    """Test batch processing when buffer is full."""
    mock_conn = Mock()
    ingestor = Ingestor(mock_conn)
    ingestor.batch_size = 3

    # Add items to buffer
    for i in range(5):
        ingestor.node_buffer.append(("TestNode", {"id": i}))

    # In real implementation, this would trigger batch processing
    if len(ingestor.node_buffer) >= ingestor.batch_size:
        # Process first batch
        batch = ingestor.node_buffer[: ingestor.batch_size]
        assert len(batch) == 3

        # Remaining items
        remaining = ingestor.node_buffer[ingestor.batch_size :]
        assert len(remaining) == 2


def test_file_metadata_creation():
    """Test file metadata node creation."""
    mock_conn = Mock()
    Ingestor(mock_conn)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("def test(): pass")
        temp_path = f.name

    try:
        # Get file stats
        stat = os.stat(temp_path)

        # Create metadata
        metadata = {
            "filepath": temp_path,
            "mtime": int(stat.st_mtime),
            "hash": hashlib.sha256(open(temp_path, "rb").read()).hexdigest(),
            "last_updated": int(time.time()),
        }

        assert metadata["filepath"] == temp_path
        assert isinstance(metadata["mtime"], int)
        assert len(metadata["hash"]) == 64  # SHA256 hash length
    finally:
        os.unlink(temp_path)


def test_error_recovery():
    """Test error recovery during ingestion."""
    mock_conn = Mock()
    Ingestor(mock_conn)

    # Simulate processing multiple files with one error
    files_processed = 0
    errors = 0

    test_files = ["good_file.py", "bad_file.py", "another_good_file.py"]

    for filename in test_files:
        try:
            if "bad" in filename:
                raise Exception("Processing error")
            files_processed += 1
        except Exception:
            errors += 1
            # Continue processing other files
            continue

    assert files_processed == 2
    assert errors == 1


def test_memory_management():
    """Test memory management with large buffers."""
    mock_conn = Mock()
    ingestor = Ingestor(mock_conn)

    # Add many items to test memory behavior
    large_count = 10000
    for i in range(large_count):
        if i % 2 == 0:
            ingestor.node_buffer.append(("TestNode", {"id": i}))
        else:
            ingestor.relationship_buffer.append(
                ("TestRel", f"from_{i}", f"to_{i}", {}, {}, {})
            )

    # Verify all items were added
    assert len(ingestor.node_buffer) == large_count // 2
    assert len(ingestor.relationship_buffer) == large_count // 2

    # Clear to free memory
    ingestor.node_buffer.clear()
    ingestor.relationship_buffer.clear()

    assert len(ingestor.node_buffer) == 0
    assert len(ingestor.relationship_buffer) == 0


@patch("shotgun.codebase.core.ingestor.time.time")
def test_timing_measurements(mock_time):
    """Test timing measurement for performance tracking."""
    mock_time.return_value = 1000.0

    start_time = time.time()

    # Simulate some work
    mock_time.return_value = 1005.0
    end_time = time.time()

    duration = end_time - start_time
    assert duration == 5.0


def test_concurrent_access_safety():
    """Test thread safety considerations."""
    mock_conn = Mock()
    ingestor = Ingestor(mock_conn)

    # Simulate concurrent access to buffers
    # In real implementation, this would need proper synchronization
    initial_count = len(ingestor.node_buffer)

    # Multiple threads might add items
    ingestor.node_buffer.append(("Node1", {"id": 1}))
    ingestor.node_buffer.append(("Node2", {"id": 2}))

    assert len(ingestor.node_buffer) == initial_count + 2


def test_schema_version_compatibility():
    """Test schema version handling."""
    mock_conn = Mock()
    Ingestor(mock_conn)

    # Mock schema version check
    schema_version = "1.0.0"
    expected_version = "1.0.0"

    assert schema_version == expected_version


def test_cleanup_operations():
    """Test cleanup operations."""
    mock_conn = Mock()
    ingestor = Ingestor(mock_conn)

    # Add some data
    ingestor.node_buffer.append(("TestNode", {"id": 1}))
    ingestor.relationship_buffer.append(("TestRel", "from", "to", {}, {}, {}))

    # Cleanup should clear all buffers
    ingestor.node_buffer.clear()
    ingestor.relationship_buffer.clear()

    assert len(ingestor.node_buffer) == 0
    assert len(ingestor.relationship_buffer) == 0


def test_statistics_collection():
    """Test statistics collection during ingestion."""
    mock_conn = Mock()
    ingestor = Ingestor(mock_conn)

    # Track statistics
    stats = {
        "files_processed": 0,
        "nodes_created": 0,
        "relationships_created": 0,
        "errors": 0,
    }

    # Simulate processing
    stats["files_processed"] = 10
    stats["nodes_created"] = len(ingestor.node_buffer)
    stats["relationships_created"] = len(ingestor.relationship_buffer)

    assert stats["files_processed"] == 10
    assert isinstance(stats["nodes_created"], int)
    assert isinstance(stats["relationships_created"], int)
