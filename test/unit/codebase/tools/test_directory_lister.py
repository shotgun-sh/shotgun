"""Tests for directory_lister tool."""

import pytest

from shotgun.agents.tools.codebase import DirectoryListResult, directory_lister


@pytest.mark.asyncio
async def test_directory_lister_success(
    mock_run_context, mock_codebase_service, mock_graph, tmp_path
):
    """Test successful directory listing."""
    # Create test directory structure
    (tmp_path / "subdir").mkdir()
    (tmp_path / "file.py").write_text("test")
    (tmp_path / "README.md").write_text("readme")

    mock_graph.repo_path = str(tmp_path)
    mock_codebase_service.list_graphs.return_value = [mock_graph]

    # Execute
    result = await directory_lister(
        mock_run_context, directory=".", graph_id="test-graph-id"
    )

    # Verify
    assert isinstance(result, DirectoryListResult)
    assert result.success is True
    assert result.directory == "."
    assert "subdir" in result.directories
    assert any(fname == "file.py" for fname, _ in result.files)
    assert "📁 subdir/" in str(result)
    assert "📄 file.py" in str(result)


@pytest.mark.asyncio
async def test_directory_lister_security_violation(
    mock_run_context, mock_codebase_service, mock_graph, tmp_path
):
    """Test directory_lister prevents path traversal."""
    mock_graph.repo_path = str(tmp_path)
    mock_codebase_service.list_graphs.return_value = [mock_graph]

    result = await directory_lister(
        mock_run_context, directory="../../../etc", graph_id="test-graph-id"
    )

    assert isinstance(result, DirectoryListResult)
    assert result.success is False
    assert result.error and "Access denied" in result.error


@pytest.mark.asyncio
async def test_directory_lister_cwd_fallback_success(
    mock_run_context_no_codebase, tmp_path, monkeypatch
):
    """Test directory_lister falls back to CWD when no graph_id provided."""
    monkeypatch.chdir(tmp_path)

    # Create test directory structure
    (tmp_path / "subdir").mkdir()
    (tmp_path / "file.txt").write_text("test")

    # Execute without graph_id
    result = await directory_lister(mock_run_context_no_codebase, directory=".")

    assert isinstance(result, DirectoryListResult)
    assert result.success is True
    assert "subdir" in result.directories
    assert any(fname == "file.txt" for fname, _ in result.files)


@pytest.mark.asyncio
async def test_directory_lister_cwd_fallback_nested(
    mock_run_context_no_codebase, tmp_path, monkeypatch
):
    """Test directory_lister can list nested directories from CWD."""
    monkeypatch.chdir(tmp_path)

    # Create nested structure
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    (subdir / "nested.txt").write_text("nested")
    (subdir / "inner").mkdir()

    # Execute without graph_id
    result = await directory_lister(mock_run_context_no_codebase, directory="subdir")

    assert isinstance(result, DirectoryListResult)
    assert result.success is True
    assert "inner" in result.directories
    assert any(fname == "nested.txt" for fname, _ in result.files)


@pytest.mark.asyncio
async def test_directory_lister_cwd_fallback_security(
    mock_run_context_no_codebase, tmp_path, monkeypatch
):
    """Test directory_lister prevents path traversal even with CWD fallback."""
    monkeypatch.chdir(tmp_path)

    result = await directory_lister(
        mock_run_context_no_codebase, directory="../../../etc"
    )

    assert isinstance(result, DirectoryListResult)
    assert result.success is False
    assert result.error and "Access denied" in result.error


@pytest.mark.asyncio
async def test_directory_lister_cwd_fallback_not_found(
    mock_run_context_no_codebase, tmp_path, monkeypatch
):
    """Test directory_lister returns error for non-existent directory with CWD fallback."""
    monkeypatch.chdir(tmp_path)

    result = await directory_lister(
        mock_run_context_no_codebase, directory="nonexistent"
    )

    assert isinstance(result, DirectoryListResult)
    assert result.success is False
    assert result.error and "not found" in result.error.lower()
