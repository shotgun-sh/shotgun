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
    result = await directory_lister(mock_run_context, "test-graph-id", ".")

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

    result = await directory_lister(mock_run_context, "test-graph-id", "../../../etc")

    assert isinstance(result, DirectoryListResult)
    assert result.success is False
    assert result.error and "Access denied" in result.error
