"""Tests for result model string formatting."""

from shotgun.agents.tools.codebase import (
    CodeSnippetResult,
    DirectoryListResult,
    FileReadResult,
    QueryGraphResult,
    ShellCommandResult,
)


def test_query_graph_result_str():
    """Test QueryGraphResult string formatting."""
    result = QueryGraphResult(
        success=True,
        query="test query",
        cypher_query="MATCH (n) RETURN n",
        results=[{"name": "TestClass", "type": "class"}],
        column_names=["name", "type"],
        row_count=1,
        execution_time_ms=50.0,
    )

    str_result = str(result)
    assert "Generated Cypher" in str_result
    assert "MATCH (n) RETURN n" in str_result
    assert "TestClass" in str_result
    assert "1 rows, 50.0ms" in str_result


def test_code_snippet_result_str():
    """Test CodeSnippetResult string formatting."""
    result = CodeSnippetResult(
        found=True,
        qualified_name="test.Class",
        file_path="test.py",
        line_start=1,
        line_end=10,
        source_code="class TestClass:\n    pass",
        docstring="Test class",
        language="python",
    )

    str_result = str(result)
    assert "test.Class" in str_result
    assert "test.py" in str_result
    assert "1-10" in str_result
    assert "```python" in str_result
    assert "class TestClass" in str_result


def test_file_read_result_str():
    """Test FileReadResult string formatting."""
    result = FileReadResult(
        success=True,
        file_path="test.py",
        content="print('hello')",
        encoding="utf-8",
        size_bytes=13,
        language="python",
    )

    str_result = str(result)
    assert "test.py" in str_result
    assert "13 bytes" in str_result
    assert "print('hello')" in str_result
    assert "```python" in str_result


def test_code_snippet_result_str_with_javascript():
    """Test CodeSnippetResult string formatting with JavaScript language."""
    result = CodeSnippetResult(
        found=True,
        qualified_name="test.Class",
        file_path="test.js",
        line_start=1,
        line_end=10,
        source_code="class TestClass {\n    constructor() {}\n}",
        docstring="Test class",
        language="javascript",
    )

    str_result = str(result)
    assert "test.Class" in str_result
    assert "test.js" in str_result
    assert "```javascript" in str_result
    assert "class TestClass" in str_result


def test_code_snippet_result_str_no_language():
    """Test CodeSnippetResult string formatting with no language detected."""
    result = CodeSnippetResult(
        found=True,
        qualified_name="test.Class",
        file_path="test.unknown",
        line_start=1,
        line_end=10,
        source_code="some code here",
        docstring="Test class",
        language="",
    )

    str_result = str(result)
    assert "test.Class" in str_result
    assert "test.unknown" in str_result
    assert "```\n" in str_result  # Empty language tag
    assert "some code here" in str_result


def test_directory_list_result_str():
    """Test DirectoryListResult string formatting."""
    result = DirectoryListResult(
        success=True,
        directory=".",
        full_path="/path/to/repo",
        directories=["subdir"],
        files=[("test.py", 1024), ("README.md", 512)],
    )

    str_result = str(result)
    assert "📁 subdir/" in str_result
    assert "📄 test.py (1.0KB)" in str_result
    assert "📄 README.md (512B)" in str_result
    assert "1 directories, 2 files" in str_result


def test_shell_command_result_str():
    """Test ShellCommandResult string formatting."""
    result = ShellCommandResult(
        success=True,
        command="ls",
        args=["-la"],
        stdout="file1.py\nfile2.py",
        stderr="",
        return_code=0,
        execution_time_ms=25.5,
    )

    str_result = str(result)
    assert "ls -la" in str_result
    assert "25.5ms" in str_result
    assert "file1.py" in str_result


def test_error_result_formatting():
    """Test error result formatting."""
    result = QueryGraphResult(
        success=False,
        query="test",
        error="Graph not found",
    )

    str_result = str(result)
    assert "Query Failed" in str_result
    assert "Graph not found" in str_result
