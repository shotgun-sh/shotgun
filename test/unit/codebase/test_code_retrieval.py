"""Unit tests for code_retrieval module."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from shotgun.codebase.core.code_retrieval import (
    CodeSnippet,
    retrieve_code_by_qualified_name,
)


def test_code_snippet_model_creation():
    """Test CodeSnippet model creation with required fields."""
    snippet = CodeSnippet(
        qualified_name="test.module.function",
        source_code="def function(): pass",
        file_path="/path/to/file.py",
        line_start=10,
        line_end=20,
    )

    assert snippet.qualified_name == "test.module.function"
    assert snippet.source_code == "def function(): pass"
    assert snippet.file_path == "/path/to/file.py"
    assert snippet.line_start == 10
    assert snippet.line_end == 20
    assert snippet.found is True  # Default value
    assert snippet.error_message is None  # Default value
    assert snippet.docstring is None  # Default value


def test_code_snippet_model_with_error():
    """Test CodeSnippet model creation with error state."""
    snippet = CodeSnippet(
        qualified_name="test.module.missing_function",
        source_code="",
        file_path="/path/to/file.py",
        line_start=0,
        line_end=0,
        found=False,
        error_message="Function not found",
    )

    assert snippet.found is False
    assert snippet.error_message == "Function not found"
    assert snippet.source_code == ""


def test_code_snippet_model_with_docstring():
    """Test CodeSnippet model with docstring."""
    snippet = CodeSnippet(
        qualified_name="test.module.documented_function",
        source_code="def documented_function():\n    '''This is a docstring.'''\n    pass",
        file_path="/path/to/file.py",
        line_start=5,
        line_end=8,
        docstring="This is a docstring.",
    )

    assert snippet.docstring == "This is a docstring."
    assert "docstring" in snippet.source_code


@pytest.mark.asyncio
async def test_retrieve_code_by_qualified_name_function():
    """Test retrieving code for a function."""
    mock_manager = Mock()
    mock_manager._execute_query = AsyncMock()

    # Mock query results - first call for entity, second call for repo path
    mock_manager._execute_query.side_effect = [
        # First call: entity query result
        [
            {
                "name": "my_function",
                "start_line": 5,
                "end_line": 7,
                "path": "test/module.py",
                "docstring": "Test function docstring",
            }
        ],
        # Second call: repo path query result
        [{"p.repo_path": "/path/to"}],
    ]

    # Mock file reading
    file_content = """# Module header
def other_function():
    pass

def my_function():
    '''Test function docstring'''
    return "Hello World"

def another_function():
    pass
"""

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.open", mock_open_read(file_content)),
    ):
        snippet = await retrieve_code_by_qualified_name(
            mock_manager, "test-graph", "test.module.my_function"
        )

    assert snippet.found is True
    assert snippet.qualified_name == "test.module.my_function"
    assert snippet.file_path == "test/module.py"
    assert snippet.line_start == 5
    assert snippet.line_end == 7
    assert "def my_function():" in snippet.source_code
    assert snippet.docstring == "Test function docstring"

    # Verify queries were executed (entity query + repo path query)
    assert mock_manager._execute_query.call_count == 2


@pytest.mark.asyncio
async def test_retrieve_code_by_qualified_name_class():
    """Test retrieving code for a class."""
    mock_manager = Mock()
    mock_manager._execute_query = AsyncMock()

    # Mock query results - first call for entity, second call for repo path
    mock_manager._execute_query.side_effect = [
        # First call: entity query result
        [
            {
                "name": "MyClass",
                "start_line": 2,
                "end_line": 9,
                "path": "test/module.py",
                "docstring": "Test class docstring",
            }
        ],
        # Second call: repo path query result
        [{"p.repo_path": "/path/to"}],
    ]

    file_content = """# Module content
class MyClass:
    '''Test class docstring'''

    def __init__(self):
        self.value = 42

    def method(self):
        return self.value
"""

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.open", mock_open_read(file_content)),
    ):
        snippet = await retrieve_code_by_qualified_name(
            mock_manager, "test-graph", "test.module.MyClass"
        )

    assert snippet.found is True
    assert snippet.qualified_name == "test.module.MyClass"
    assert snippet.file_path == "test/module.py"
    assert snippet.line_start == 2
    assert snippet.line_end == 9
    assert "class MyClass:" in snippet.source_code
    assert snippet.docstring == "Test class docstring"

    # Verify queries were executed (entity query + repo path query)
    assert mock_manager._execute_query.call_count == 2


@pytest.mark.asyncio
async def test_retrieve_code_by_qualified_name_method():
    """Test retrieving code for a method."""
    mock_manager = Mock()
    mock_manager._execute_query = AsyncMock()

    # Mock query results - first call for entity, second call for repo path
    mock_manager._execute_query.side_effect = [
        # First call: entity query result
        [
            {
                "name": "my_method",
                "start_line": 4,
                "end_line": 6,
                "path": "test/module.py",
                "docstring": "Test method docstring",
            }
        ],
        # Second call: repo path query result
        [{"p.repo_path": "/path/to"}],
    ]

    file_content = """class MyClass:
    def __init__(self):
        pass

    def my_method(self):
        '''Test method docstring'''
        return "method result"
"""

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.open", mock_open_read(file_content)),
    ):
        snippet = await retrieve_code_by_qualified_name(
            mock_manager, "test-graph", "test.module.MyClass.my_method"
        )

    assert snippet.found is True
    assert snippet.qualified_name == "test.module.MyClass.my_method"
    assert snippet.file_path == "test/module.py"
    assert snippet.line_start == 4
    assert snippet.line_end == 6
    assert "def my_method(self):" in snippet.source_code
    assert snippet.docstring == "Test method docstring"

    # Verify queries were executed (entity query + repo path query)
    assert mock_manager._execute_query.call_count == 2


@pytest.mark.asyncio
async def test_retrieve_code_entity_not_found():
    """Test handling when entity is not found in database."""
    mock_manager = Mock()
    mock_manager._execute_query = AsyncMock()

    # Mock empty query result
    mock_manager._execute_query.return_value = []

    snippet = await retrieve_code_by_qualified_name(
        mock_manager, "test-graph", "nonexistent.module.function"
    )

    assert snippet.found is False
    assert snippet.qualified_name == "nonexistent.module.function"
    assert (
        snippet.error_message
        == "Entity 'nonexistent.module.function' not found in graph."
    )
    assert snippet.source_code == ""


@pytest.mark.asyncio
async def test_retrieve_code_file_not_found():
    """Test handling when source file doesn't exist."""
    mock_manager = Mock()
    mock_manager._execute_query = AsyncMock()

    # Mock query result with non-existent file
    mock_manager._execute_query.side_effect = [
        # First call: entity query result
        [
            {
                "name": "function",
                "start_line": 10,
                "end_line": 15,
                "path": "/nonexistent/file.py",
                "docstring": None,
            }
        ],
        # Second call: repo path query result
        [{"p.repo_path": "/path/to/repo"}],
    ]

    with patch("pathlib.Path.exists", return_value=False):
        snippet = await retrieve_code_by_qualified_name(
            mock_manager, "test-graph", "test.module.function"
        )

    assert snippet.found is False
    assert "Source file not found:" in snippet.error_message


@pytest.mark.asyncio
async def test_retrieve_code_file_read_error():
    """Test handling file read errors."""
    mock_manager = Mock()
    mock_manager._execute_query = AsyncMock()

    mock_manager._execute_query.side_effect = [
        # First call: entity query result
        [
            {
                "name": "function",
                "start_line": 10,
                "end_line": 15,
                "path": "/path/to/file.py",
                "docstring": None,
            }
        ],
        # Second call: repo path query result
        [{"p.repo_path": "/path/to/repo"}],
    ]

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.open", side_effect=PermissionError("Permission denied")),
    ):
        snippet = await retrieve_code_by_qualified_name(
            mock_manager, "test-graph", "test.module.function"
        )

    assert snippet.found is False
    assert (
        snippet.error_message and "Error reading source file" in snippet.error_message
    )


@pytest.mark.asyncio
async def test_retrieve_code_invalid_line_numbers():
    """Test handling invalid line numbers."""
    mock_manager = Mock()
    mock_manager._execute_query = AsyncMock()

    mock_manager._execute_query.side_effect = [
        # First call: entity query result
        [
            {
                "name": "function",
                "start_line": 100,  # Beyond file length
                "end_line": 110,
                "path": "/path/to/file.py",
                "docstring": None,
            }
        ],
        # Second call: repo path query result
        [{"p.repo_path": "/path/to/repo"}],
    ]

    file_content = "def small_function():\n    return 42"  # Only 2 lines

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.open", mock_open_read(file_content)),
    ):
        snippet = await retrieve_code_by_qualified_name(
            mock_manager, "test-graph", "test.module.function"
        )

    assert (
        snippet.found is True
    )  # Function successfully extracts, but returns empty content
    assert (
        snippet.source_code == ""
    )  # Line numbers beyond file length result in empty content


@pytest.mark.asyncio
async def test_retrieve_code_database_error():
    """Test handling database query errors."""
    mock_manager = Mock()
    mock_manager._execute_query = AsyncMock()

    # Mock database error
    mock_manager._execute_query.side_effect = Exception("Database connection failed")

    snippet = await retrieve_code_by_qualified_name(
        mock_manager, "test-graph", "test.module.function"
    )

    assert snippet.found is False
    assert (
        snippet.error_message and "Database connection failed" in snippet.error_message
    )


@pytest.mark.asyncio
async def test_retrieve_code_with_unicode_content():
    """Test handling files with unicode characters."""
    mock_manager = Mock()
    mock_manager._execute_query = AsyncMock()

    mock_manager._execute_query.side_effect = [
        # First call: entity query result
        [
            {
                "name": "unicode_function",
                "start_line": 2,
                "end_line": 4,
                "path": "/path/to/unicode_file.py",
                "docstring": "Function with unicode: café",
            }
        ],
        # Second call: repo path query result
        [{"p.repo_path": "/path/to/repo"}],
    ]

    unicode_content = """# -*- coding: utf-8 -*-
def unicode_function():
    '''Function with unicode: café'''
    return "Hello 世界"
"""

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.open", mock_open_read(unicode_content)),
    ):
        snippet = await retrieve_code_by_qualified_name(
            mock_manager, "test-graph", "test.module.unicode_function"
        )

    assert snippet.found is True
    assert "世界" in snippet.source_code
    assert snippet.docstring and "café" in snippet.docstring


@pytest.mark.asyncio
async def test_retrieve_code_empty_file():
    """Test handling empty source files."""
    mock_manager = Mock()
    mock_manager._execute_query = AsyncMock()

    mock_manager._execute_query.side_effect = [
        # First call: entity query result
        [
            {
                "name": "function",
                "start_line": 1,
                "end_line": 1,
                "path": "/path/to/empty_file.py",
                "docstring": None,
            }
        ],
        # Second call: repo path query result
        [{"p.repo_path": "/path/to/repo"}],
    ]

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.open", mock_open_read("")),
    ):
        snippet = await retrieve_code_by_qualified_name(
            mock_manager, "test-graph", "test.module.function"
        )

    assert snippet.found is True  # Function successfully processes empty file
    assert snippet.source_code == ""  # Empty file results in empty content


@pytest.mark.asyncio
async def test_retrieve_code_line_extraction():
    """Test correct line extraction from source code."""
    mock_manager = Mock()
    mock_manager._execute_query = AsyncMock()

    mock_manager._execute_query.side_effect = [
        # First call: entity query result
        [
            {
                "name": "target_function",
                "start_line": 3,
                "end_line": 5,
                "path": "/path/to/file.py",
                "docstring": None,
            }
        ],
        # Second call: repo path query result
        [{"p.repo_path": "/path/to/repo"}],
    ]

    file_content = """# Line 1
# Line 2
def target_function():
    # Line 4
    return "target"
# Line 6
def other_function():
    return "other"
"""

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.open", mock_open_read(file_content)),
    ):
        snippet = await retrieve_code_by_qualified_name(
            mock_manager, "test-graph", "test.module.target_function"
        )

    assert snippet.found is True
    lines = snippet.source_code.split("\n")
    assert "def target_function():" in lines[0]
    assert 'return "target"' in lines[2]
    # Note: join includes trailing newline, so we get 4 lines instead of 3
    assert len([line for line in lines if line]) == 3  # Three non-empty lines


def mock_open_read(content):
    """Helper to mock file reading with specific content."""
    from unittest.mock import mock_open

    return mock_open(read_data=content)


def test_code_snippet_serialization():
    """Test CodeSnippet model serialization."""
    snippet = CodeSnippet(
        qualified_name="test.module.function",
        source_code="def function(): pass",
        file_path="/path/to/file.py",
        line_start=10,
        line_end=12,
    )

    # Test model_dump (Pydantic v2)
    data = snippet.model_dump()

    assert data["qualified_name"] == "test.module.function"
    assert data["source_code"] == "def function(): pass"
    assert data["found"] is True


def test_code_snippet_validation():
    """Test CodeSnippet model validation."""
    # Valid snippet
    snippet = CodeSnippet(
        qualified_name="valid.name",
        source_code="code",
        file_path="/valid/path",
        line_start=1,
        line_end=5,
    )
    assert snippet.line_start < snippet.line_end

    # Test with equal line numbers (single line)
    single_line_snippet = CodeSnippet(
        qualified_name="valid.name",
        source_code="single line",
        file_path="/valid/path",
        line_start=10,
        line_end=10,
    )
    assert single_line_snippet.line_start == single_line_snippet.line_end


@pytest.mark.asyncio
async def test_retrieve_code_query_structure():
    """Test that the correct query structure is used."""
    mock_manager = Mock()
    mock_manager._execute_query = AsyncMock()
    mock_manager._execute_query.return_value = []

    await retrieve_code_by_qualified_name(
        mock_manager, "test-graph-id", "test.module.function"
    )

    # Verify query was called with correct parameters
    mock_manager._execute_query.assert_called_once()
    call_args = mock_manager._execute_query.call_args

    assert call_args[0][0] == "test-graph-id"  # graph_id is first positional arg
    assert "MATCH" in call_args[0][1]  # query is second positional arg
    assert (
        call_args[0][2]["qualified_name"] == "test.module.function"
    )  # parameters is third positional arg


@pytest.mark.asyncio
async def test_retrieve_code_multiple_results():
    """Test handling multiple query results (should take first)."""
    mock_manager = Mock()
    mock_manager._execute_query = AsyncMock()

    # Mock multiple results - first query returns first result, second query returns repo path
    mock_manager._execute_query.side_effect = [
        # First call: entity query result (only first result is used)
        [
            {
                "name": "function",
                "start_line": 10,
                "end_line": 15,
                "path": "/path/to/file1.py",
                "docstring": "First result",
            },
            {
                "name": "function",
                "start_line": 20,
                "end_line": 25,
                "path": "/path/to/file2.py",
                "docstring": "Second result",
            },
        ],
        # Second call: repo path query result
        [{"p.repo_path": "/path/to/repo"}],
    ]

    file_content = "def function(): pass"

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.open", mock_open_read(file_content)),
    ):
        snippet = await retrieve_code_by_qualified_name(
            mock_manager, "test-graph", "test.module.function"
        )

    # Should use first result
    assert snippet.file_path == "/path/to/file1.py"
    assert snippet.line_start == 10
    assert snippet.docstring == "First result"
