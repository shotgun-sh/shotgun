"""Integration tests for file_read codebase tool."""

import pytest
from pydantic_ai import RunContext

from shotgun.agents.models import AgentDeps
from shotgun.agents.tools.codebase import file_read
from shotgun.codebase.models import CodebaseGraph


@pytest.mark.integration
@pytest.mark.asyncio
async def test_file_read_main_file(
    indexed_graph: CodebaseGraph,
    run_context: RunContext[AgentDeps],
):
    """Test reading the main.py file."""
    result = await file_read(
        ctx=run_context, graph_id=indexed_graph.graph_id, file_path="main.py"
    )

    # Should succeed
    assert result.success is True
    assert result.file_path == "main.py"
    assert result.content is not None
    assert len(result.content) > 0

    # Should contain expected content
    assert "def main()" in result.content
    assert "Calculator" in result.content
    assert 'if __name__ == "__main__":' in result.content

    # Should have file size
    assert result.size_bytes is not None
    assert result.size_bytes > 0

    # Test string representation
    result_str = str(result)
    assert isinstance(result_str, str)
    assert "main.py" in result_str
    assert "def main()" in result_str


@pytest.mark.integration
@pytest.mark.asyncio
async def test_file_read_calculator_file(
    indexed_graph: CodebaseGraph,
    run_context: RunContext[AgentDeps],
):
    """Test reading the calculator.py file."""
    result = await file_read(
        ctx=run_context, graph_id=indexed_graph.graph_id, file_path="calculator.py"
    )

    # Should succeed
    assert result.success is True
    assert result.file_path == "calculator.py"
    assert result.content is not None

    # Should contain class definitions
    assert "class Calculator:" in result.content
    assert "class ScientificCalculator" in result.content
    assert "def add(self" in result.content
    assert "def calculate_factorial" in result.content

    # Should have reasonable file size
    assert result.size_bytes is not None
    assert result.size_bytes > 1000  # It's a substantial file


@pytest.mark.integration
@pytest.mark.asyncio
async def test_file_read_subdirectory_file(
    indexed_graph: CodebaseGraph,
    run_context: RunContext[AgentDeps],
):
    """Test reading a file in a subdirectory."""
    result = await file_read(
        ctx=run_context, graph_id=indexed_graph.graph_id, file_path="utils/helpers.py"
    )

    # Should succeed
    assert result.success is True
    assert result.file_path == "utils/helpers.py"
    assert result.content is not None

    # Should contain expected content
    assert "def format_number" in result.content
    assert "class InputValidator" in result.content
    assert "def validate_input" in result.content

    # Should have file size
    assert result.size_bytes is not None
    assert result.size_bytes > 100


@pytest.mark.integration
@pytest.mark.asyncio
async def test_file_read_init_file(
    indexed_graph: CodebaseGraph,
    run_context: RunContext[AgentDeps],
):
    """Test reading an __init__.py file."""
    result = await file_read(
        ctx=run_context, graph_id=indexed_graph.graph_id, file_path="utils/__init__.py"
    )

    # Should succeed (even if empty)
    assert result.success is True
    assert result.file_path == "utils/__init__.py"
    assert result.content is not None  # May be empty string

    # Should have file size (may be 0)
    assert result.size_bytes is not None
    assert result.size_bytes >= 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_file_read_markdown_file(
    indexed_graph: CodebaseGraph,
    run_context: RunContext[AgentDeps],
):
    """Test reading a markdown file."""
    result = await file_read(
        ctx=run_context, graph_id=indexed_graph.graph_id, file_path="README.md"
    )

    # Should succeed
    assert result.success is True
    assert result.file_path == "README.md"
    assert result.content is not None

    # Should contain markdown content
    assert "# Test Codebase" in result.content
    assert "## Features" in result.content
    assert "Calculator" in result.content

    # Should have file size
    assert result.size_bytes is not None
    assert result.size_bytes > 50


@pytest.mark.integration
@pytest.mark.asyncio
async def test_file_read_config_file(
    indexed_graph: CodebaseGraph,
    run_context: RunContext[AgentDeps],
):
    """Test reading a configuration file."""
    result = await file_read(
        ctx=run_context, graph_id=indexed_graph.graph_id, file_path="config.py"
    )

    # Should succeed
    assert result.success is True
    assert result.file_path == "config.py"
    assert result.content is not None

    # Should contain config content
    assert "DEFAULT_PRECISION" in result.content
    assert "class Config" in result.content
    assert "SUPPORTED_OPERATIONS" in result.content


@pytest.mark.integration
@pytest.mark.asyncio
async def test_file_read_nonexistent_file(
    indexed_graph: CodebaseGraph,
    run_context: RunContext[AgentDeps],
):
    """Test reading a non-existent file."""
    result = await file_read(
        ctx=run_context, graph_id=indexed_graph.graph_id, file_path="nonexistent.py"
    )

    # Should fail gracefully
    assert result.success is False
    assert result.file_path == "nonexistent.py"
    assert result.content is None
    assert result.error is not None
    assert (
        "not found" in result.error.lower() or "does not exist" in result.error.lower()
    )

    # String representation should show error
    result_str = str(result)
    assert "Error" in result_str or "not found" in result_str
    assert "nonexistent.py" in result_str


@pytest.mark.integration
@pytest.mark.asyncio
async def test_file_read_invalid_graph_id(
    run_context: RunContext[AgentDeps],
):
    """Test reading file with invalid graph ID."""
    result = await file_read(
        ctx=run_context, graph_id="nonexistent-graph-id", file_path="main.py"
    )

    # Should fail gracefully
    assert result.success is False
    assert result.file_path == "main.py"
    assert result.content is None
    assert result.error is not None
    assert "graph" in result.error.lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_file_read_no_codebase_service(
    indexed_graph: CodebaseGraph,
):
    """Test reading file when no codebase service is available."""

    # Create run context without codebase service
    class MockRunContextNoService:
        def __init__(self):
            self.deps = type("MockDeps", (), {"codebase_service": None})()

    context = MockRunContextNoService()

    result = await file_read(
        ctx=context, graph_id=indexed_graph.graph_id, file_path="main.py"
    )

    # Should fail gracefully
    assert result.success is False
    assert result.error is not None
    assert "codebase service" in result.error.lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_file_read_absolute_path_attempt(
    indexed_graph: CodebaseGraph,
    run_context: RunContext[AgentDeps],
):
    """Test reading with absolute path (should be handled gracefully)."""
    result = await file_read(
        ctx=run_context,
        graph_id=indexed_graph.graph_id,
        file_path="/absolute/path/to/file.py",
    )

    # Should fail gracefully or convert to relative path
    assert isinstance(result.success, bool)
    assert result.file_path == "/absolute/path/to/file.py"

    if not result.success:
        assert result.error is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_file_read_directory_path(
    indexed_graph: CodebaseGraph,
    run_context: RunContext[AgentDeps],
):
    """Test reading a directory path instead of file."""
    result = await file_read(
        ctx=run_context, graph_id=indexed_graph.graph_id, file_path="utils"
    )

    # Should fail gracefully
    assert result.success is False
    assert result.file_path == "utils"
    assert result.content is None
    assert result.error is not None
    assert "directory" in result.error.lower() or "not a file" in result.error.lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_file_read_string_representation_success(
    indexed_graph: CodebaseGraph,
    run_context: RunContext[AgentDeps],
):
    """Test string representation of successful file read."""
    result = await file_read(
        ctx=run_context, graph_id=indexed_graph.graph_id, file_path="main.py"
    )

    assert result.success is True

    result_str = str(result)
    assert isinstance(result_str, str)
    assert len(result_str) > 0

    # Should contain file path and content
    assert "main.py" in result_str
    assert "def main()" in result_str

    # Should show file size
    assert f"{result.size_bytes} bytes" in result_str

    # Should not show raw field names
    assert "file_path:" not in result_str
    assert "content:" not in result_str


@pytest.mark.integration
@pytest.mark.asyncio
async def test_file_read_string_representation_failure(
    indexed_graph: CodebaseGraph,
    run_context: RunContext[AgentDeps],
):
    """Test string representation of failed file read."""
    result = await file_read(
        ctx=run_context, graph_id=indexed_graph.graph_id, file_path="nonexistent.py"
    )

    assert result.success is False

    result_str = str(result)
    assert isinstance(result_str, str)
    assert len(result_str) > 0

    # Should show error message
    assert "Error" in result_str or "not found" in result_str
    assert "nonexistent.py" in result_str


@pytest.mark.integration
@pytest.mark.asyncio
async def test_file_read_empty_file_path(
    indexed_graph: CodebaseGraph,
    run_context: RunContext[AgentDeps],
):
    """Test reading with empty file path."""
    result = await file_read(
        ctx=run_context, graph_id=indexed_graph.graph_id, file_path=""
    )

    # Should fail gracefully
    assert result.success is False
    assert result.file_path == ""
    assert result.content is None
    assert result.error is not None
