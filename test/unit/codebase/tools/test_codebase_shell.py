"""Tests for codebase_shell tool."""

import pytest

from shotgun.agents.tools.codebase import ShellCommandResult, codebase_shell


@pytest.mark.asyncio
async def test_codebase_shell_success(
    mock_run_context, mock_codebase_service, mock_graph, tmp_path
):
    """Test successful shell command execution."""
    mock_graph.repo_path = str(tmp_path)
    mock_codebase_service.list_graphs.return_value = [mock_graph]

    # Execute simple ls command (without graph_id - uses first available)
    result = await codebase_shell(mock_run_context, "ls", ["-la"])

    # Verify
    assert isinstance(result, ShellCommandResult)
    assert result.command == "ls"
    assert result.args == ["-la"]
    # Command should execute (success depends on system)


@pytest.mark.asyncio
async def test_codebase_shell_command_not_allowed(
    mock_run_context, mock_codebase_service
):
    """Test codebase_shell rejects dangerous commands."""
    result = await codebase_shell(mock_run_context, "rm", ["-rf", "/"])

    assert isinstance(result, ShellCommandResult)
    assert result.success is False
    assert result.error and "not allowed" in result.error


@pytest.mark.asyncio
async def test_codebase_shell_dangerous_patterns(
    mock_run_context, mock_codebase_service
):
    """Test codebase_shell rejects dangerous patterns."""
    result = await codebase_shell(mock_run_context, "ls", ["-la", "|", "grep", "test"])

    assert isinstance(result, ShellCommandResult)
    assert result.success is False
    assert result.error and "dangerous patterns" in result.error


@pytest.mark.asyncio
async def test_codebase_shell_no_graphs(mock_run_context, mock_codebase_service):
    """Test codebase_shell with no graphs available."""
    mock_codebase_service.list_graphs.return_value = []

    result = await codebase_shell(mock_run_context, "ls", [])

    assert isinstance(result, ShellCommandResult)
    assert result.success is False
    assert result.error and "No codebases available" in result.error


@pytest.mark.asyncio
async def test_codebase_shell_specific_graph_id(
    mock_run_context, mock_codebase_service, mock_graph, tmp_path
):
    """Test codebase_shell with specific graph ID."""
    mock_graph.repo_path = str(tmp_path)
    mock_codebase_service.list_graphs.return_value = [mock_graph]

    # Execute command with specific graph_id
    result = await codebase_shell(
        mock_run_context, "ls", ["-la"], graph_id="test-graph-id"
    )

    assert isinstance(result, ShellCommandResult)
    assert result.command == "ls"
    assert result.args == ["-la"]


@pytest.mark.asyncio
async def test_codebase_shell_invalid_graph_id(
    mock_run_context, mock_codebase_service, mock_graph, tmp_path
):
    """Test codebase_shell with invalid graph ID."""
    mock_graph.repo_path = str(tmp_path)
    mock_codebase_service.list_graphs.return_value = [mock_graph]

    # Execute command with invalid graph_id
    result = await codebase_shell(
        mock_run_context, "ls", ["-la"], graph_id="invalid-graph-id"
    )

    assert isinstance(result, ShellCommandResult)
    assert result.success is False
    assert result.error and "Graph 'invalid-graph-id' not found" in result.error
