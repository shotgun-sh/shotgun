"""Tests for file_read tool."""

import pytest

from shotgun.agents.tools.codebase import FileReadResult, file_read


@pytest.mark.asyncio
async def test_file_read_success(
    mock_run_context, mock_codebase_service, mock_graph, tmp_path
):
    """Test successful file reading."""
    # Setup test file
    test_file = tmp_path / "test.py"
    test_content = "# Test file\nprint('hello')"
    test_file.write_text(test_content)

    # Mock graph with tmp_path as repo
    mock_graph.repo_path = str(tmp_path)
    mock_codebase_service.list_graphs.return_value = [mock_graph]

    # Execute
    result = await file_read(mock_run_context, "test-graph-id", "test.py")

    # Verify
    assert isinstance(result, FileReadResult)
    assert result.success is True
    assert result.file_path == "test.py"
    assert result.content == test_content
    assert test_content in str(result)


@pytest.mark.asyncio
async def test_file_read_security_violation(
    mock_run_context, mock_codebase_service, mock_graph, tmp_path
):
    """Test file_read prevents path traversal."""
    mock_graph.repo_path = str(tmp_path)
    mock_codebase_service.list_graphs.return_value = [mock_graph]

    # Try to read outside repo
    result = await file_read(mock_run_context, "test-graph-id", "../../../etc/passwd")

    assert isinstance(result, FileReadResult)
    assert result.success is False
    assert result.error and "Access denied" in result.error


@pytest.mark.asyncio
async def test_file_read_file_not_found(
    mock_run_context, mock_codebase_service, mock_graph, tmp_path
):
    """Test file_read with non-existent file."""
    mock_graph.repo_path = str(tmp_path)
    mock_codebase_service.list_graphs.return_value = [mock_graph]

    result = await file_read(mock_run_context, "test-graph-id", "nonexistent.py")

    assert isinstance(result, FileReadResult)
    assert result.success is False
    assert result.error and "not found" in result.error
