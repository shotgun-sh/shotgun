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
    result = await file_read(mock_run_context, file_path="test.py", graph_id="test-graph-id")

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
    result = await file_read(mock_run_context, file_path="../../../etc/passwd", graph_id="test-graph-id")

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

    result = await file_read(mock_run_context, file_path="nonexistent.py", graph_id="test-graph-id")

    assert isinstance(result, FileReadResult)
    assert result.success is False
    assert result.error and "not found" in result.error


@pytest.mark.asyncio
async def test_file_read_cwd_fallback_success(
    mock_run_context_no_codebase, tmp_path, monkeypatch
):
    """Test file_read falls back to CWD when no graph_id provided."""
    # Change to tmp_path as CWD
    monkeypatch.chdir(tmp_path)

    # Setup test file
    test_file = tmp_path / "test.txt"
    test_content = "Hello from CWD"
    test_file.write_text(test_content)

    # Execute without graph_id
    result = await file_read(mock_run_context_no_codebase, file_path="test.txt")

    # Verify
    assert isinstance(result, FileReadResult)
    assert result.success is True
    assert result.content == test_content


@pytest.mark.asyncio
async def test_file_read_cwd_fallback_nested_path(
    mock_run_context_no_codebase, tmp_path, monkeypatch
):
    """Test file_read can read nested paths from CWD."""
    monkeypatch.chdir(tmp_path)

    # Setup nested file
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    test_file = subdir / "nested.txt"
    test_file.write_text("Nested content")

    # Execute without graph_id
    result = await file_read(mock_run_context_no_codebase, file_path="subdir/nested.txt")

    assert isinstance(result, FileReadResult)
    assert result.success is True
    assert result.content == "Nested content"


@pytest.mark.asyncio
async def test_file_read_cwd_fallback_security(
    mock_run_context_no_codebase, tmp_path, monkeypatch
):
    """Test file_read prevents path traversal even with CWD fallback."""
    monkeypatch.chdir(tmp_path)

    # Try to read outside CWD
    result = await file_read(mock_run_context_no_codebase, file_path="../../../etc/passwd")

    assert isinstance(result, FileReadResult)
    assert result.success is False
    assert result.error and "Access denied" in result.error


@pytest.mark.asyncio
async def test_file_read_cwd_fallback_file_not_found(
    mock_run_context_no_codebase, tmp_path, monkeypatch
):
    """Test file_read returns error for non-existent file with CWD fallback."""
    monkeypatch.chdir(tmp_path)

    result = await file_read(mock_run_context_no_codebase, file_path="nonexistent.txt")

    assert isinstance(result, FileReadResult)
    assert result.success is False
    assert result.error and "not found" in result.error.lower()
