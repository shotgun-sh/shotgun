"""Integration tests for codebase_shell tool."""

import pytest
from pydantic_ai import RunContext

from shotgun.agents.models import AgentDeps
from shotgun.agents.tools.codebase import codebase_shell
from shotgun.codebase.models import CodebaseGraph


@pytest.mark.integration
@pytest.mark.asyncio
async def test_codebase_shell_ls_command(
    indexed_graph: CodebaseGraph,
    run_context: RunContext[AgentDeps],
):
    """Test listing files with ls command."""
    result = await codebase_shell(
        ctx=run_context, command="ls", args=[], graph_id=indexed_graph.graph_id
    )

    # Should succeed
    assert result.success is True
    assert result.command == "ls"
    assert result.stdout is not None
    assert len(result.stdout) > 0

    # Should contain expected files
    assert "main.py" in result.stdout
    assert "calculator.py" in result.stdout
    assert "utils" in result.stdout

    # Test string representation
    result_str = str(result)
    assert isinstance(result_str, str)
    assert "ls" in result_str
    assert "main.py" in result_str


@pytest.mark.integration
@pytest.mark.asyncio
async def test_codebase_shell_ls_with_args(
    indexed_graph: CodebaseGraph,
    run_context: RunContext[AgentDeps],
):
    """Test ls command with arguments."""
    result = await codebase_shell(
        ctx=run_context, command="ls", args=["-la"], graph_id=indexed_graph.graph_id
    )

    # Should succeed
    assert result.success is True
    assert result.args == ["-la"]
    assert result.stdout is not None

    # Should contain detailed listing information
    assert "main.py" in result.stdout
    # Typically ls -la shows permissions, dates, etc.


@pytest.mark.integration
@pytest.mark.asyncio
async def test_codebase_shell_find_command(
    indexed_graph: CodebaseGraph,
    run_context: RunContext[AgentDeps],
):
    """Test find command to search for files."""
    result = await codebase_shell(
        ctx=run_context,
        command="find",
        args=[".", "-name", "*.py"],
        graph_id=indexed_graph.graph_id,
    )

    # Should succeed
    assert result.success is True
    assert result.command == "find"
    assert result.stdout is not None

    # Should find Python files
    assert "main.py" in result.stdout or "./main.py" in result.stdout
    assert "calculator.py" in result.stdout or "./calculator.py" in result.stdout


@pytest.mark.integration
@pytest.mark.asyncio
async def test_codebase_shell_grep_command(
    indexed_graph: CodebaseGraph,
    run_context: RunContext[AgentDeps],
):
    """Test grep command to search for patterns."""
    result = await codebase_shell(
        ctx=run_context,
        command="grep",
        args=["-r", "Calculator", "."],
        graph_id=indexed_graph.graph_id,
    )

    # Should succeed
    assert result.success is True
    assert result.command == "grep"
    assert result.stdout is not None

    # Should find Calculator references
    assert "Calculator" in result.stdout
    assert "calculator.py" in result.stdout or "main.py" in result.stdout


@pytest.mark.integration
@pytest.mark.asyncio
async def test_codebase_shell_cat_command(
    indexed_graph: CodebaseGraph,
    run_context: RunContext[AgentDeps],
):
    """Test cat command to display file contents."""
    result = await codebase_shell(
        ctx=run_context,
        command="cat",
        args=["main.py"],
        graph_id=indexed_graph.graph_id,
    )

    # Should succeed
    assert result.success is True
    assert result.command == "cat"
    assert result.stdout is not None

    # Should contain file content
    assert "def main()" in result.stdout
    assert "Calculator" in result.stdout


@pytest.mark.integration
@pytest.mark.asyncio
async def test_codebase_shell_head_command(
    indexed_graph: CodebaseGraph,
    run_context: RunContext[AgentDeps],
):
    """Test head command to show first lines of file."""
    result = await codebase_shell(
        ctx=run_context,
        command="head",
        args=["-5", "calculator.py"],
        graph_id=indexed_graph.graph_id,
    )

    # Should succeed
    assert result.success is True
    assert result.command == "head"
    assert result.stdout is not None

    # Should contain beginning of file
    assert '"""' in result.stdout or "Calculator" in result.stdout


@pytest.mark.integration
@pytest.mark.asyncio
async def test_codebase_shell_wc_command(
    indexed_graph: CodebaseGraph,
    run_context: RunContext[AgentDeps],
):
    """Test wc command for word/line count."""
    result = await codebase_shell(
        ctx=run_context,
        command="wc",
        args=["-l", "main.py"],
        graph_id=indexed_graph.graph_id,
    )

    # Should succeed
    assert result.success is True
    assert result.command == "wc"
    assert result.stdout is not None

    # Should contain line count
    assert "main.py" in result.stdout
    # Should have some number in the output
    assert any(char.isdigit() for char in result.stdout)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_codebase_shell_tree_command(
    indexed_graph: CodebaseGraph,
    run_context: RunContext[AgentDeps],
):
    """Test tree command if available."""
    result = await codebase_shell(
        ctx=run_context, command="tree", args=["."], graph_id=indexed_graph.graph_id
    )

    # May succeed or fail depending on system
    assert isinstance(result.success, bool)
    assert result.command == "tree"

    if result.success:
        assert result.stdout is not None
        # Should show directory structure
        assert "main.py" in result.stdout or "calculator.py" in result.stdout
    else:
        # If tree is not available, should fail gracefully
        assert result.error is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_codebase_shell_git_status(
    indexed_graph: CodebaseGraph,
    run_context: RunContext[AgentDeps],
):
    """Test git status command."""
    result = await codebase_shell(
        ctx=run_context,
        command="git",
        args=["status", "--porcelain"],
        graph_id=indexed_graph.graph_id,
    )

    # May succeed or fail depending on if directory is a git repo
    assert isinstance(result.success, bool)
    assert result.command == "git"

    if result.success:
        assert result.stdout is not None
        # Git status output (may be empty for clean repo)
    else:
        # If not a git repo, should fail gracefully with stderr
        assert result.stderr is not None
        assert result.return_code != 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_codebase_shell_dangerous_command_blocked(
    indexed_graph: CodebaseGraph,
    run_context: RunContext[AgentDeps],
):
    """Test that dangerous commands are blocked."""
    # Test rm command (should be blocked)
    result = await codebase_shell(
        ctx=run_context,
        command="rm",
        args=["somefile.txt"],
        graph_id=indexed_graph.graph_id,
    )

    # Should fail
    assert result.success is False
    assert result.command == "rm"
    assert result.error is not None
    assert "not allowed" in result.error.lower() or "blocked" in result.error.lower()

    # Test string representation shows error
    result_str = str(result)
    assert "Error" in result_str or "not allowed" in result_str


@pytest.mark.integration
@pytest.mark.asyncio
async def test_codebase_shell_command_injection_blocked(
    indexed_graph: CodebaseGraph,
    run_context: RunContext[AgentDeps],
):
    """Test that command injection attempts are blocked."""
    # Test command with pipe
    result = await codebase_shell(
        ctx=run_context,
        command="ls",
        args=["|", "rm", "-rf", "/"],
        graph_id=indexed_graph.graph_id,
    )

    # Should fail due to dangerous characters
    assert result.success is False
    assert result.error is not None
    assert "dangerous" in result.error.lower() or "not allowed" in result.error.lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_codebase_shell_invalid_graph_id(
    run_context: RunContext[AgentDeps],
):
    """Test shell command with invalid graph ID."""
    result = await codebase_shell(
        ctx=run_context, command="ls", args=[], graph_id="nonexistent-graph-id"
    )

    # Should fail gracefully
    assert result.success is False
    assert result.command == "ls"
    assert result.error is not None
    assert "graph" in result.error.lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_codebase_shell_no_codebase_service(
    indexed_graph: CodebaseGraph,
):
    """Test shell command when no codebase service is available."""

    # Create run context without codebase service
    class MockRunContextNoService:
        def __init__(self):
            self.deps = type("MockDeps", (), {"codebase_service": None})()

    context = MockRunContextNoService()

    result = await codebase_shell(
        ctx=context, command="ls", args=[], graph_id=indexed_graph.graph_id
    )

    # Should fail gracefully
    assert result.success is False
    assert result.error is not None
    assert "codebase service" in result.error.lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_codebase_shell_nonexistent_file(
    indexed_graph: CodebaseGraph,
    run_context: RunContext[AgentDeps],
):
    """Test shell command on non-existent file."""
    result = await codebase_shell(
        ctx=run_context,
        command="cat",
        args=["nonexistent.py"],
        graph_id=indexed_graph.graph_id,
    )

    # Should fail (file not found)
    assert result.success is False
    assert result.command == "cat"
    assert result.stderr is not None
    assert (
        "not found" in result.stderr.lower() or "no such file" in result.stderr.lower()
    )
    assert result.return_code != 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_codebase_shell_empty_command(
    indexed_graph: CodebaseGraph,
    run_context: RunContext[AgentDeps],
):
    """Test shell command with empty command string."""
    result = await codebase_shell(
        ctx=run_context, command="", args=[], graph_id=indexed_graph.graph_id
    )

    # Should fail gracefully
    assert result.success is False
    assert result.command == ""
    assert result.error is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_codebase_shell_long_running_command(
    indexed_graph: CodebaseGraph,
    run_context: RunContext[AgentDeps],
):
    """Test that long-running commands are handled properly."""
    result = await codebase_shell(
        ctx=run_context,
        command="find",
        args=[".", "-type", "f"],  # Should complete quickly but tests timeout handling
        graph_id=indexed_graph.graph_id,
    )

    # Should succeed and complete in reasonable time
    assert result.success is True
    assert result.command == "find"
    assert result.stdout is not None
    assert result.execution_time_ms is not None
    assert result.execution_time_ms > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_codebase_shell_string_representation_success(
    indexed_graph: CodebaseGraph,
    run_context: RunContext[AgentDeps],
):
    """Test string representation of successful shell command."""
    result = await codebase_shell(
        ctx=run_context, command="ls", args=["-l"], graph_id=indexed_graph.graph_id
    )

    assert result.success is True

    result_str = str(result)
    assert isinstance(result_str, str)
    assert len(result_str) > 0

    # Should contain command and output
    assert "ls -l" in result_str or "Command: ls" in result_str
    assert "main.py" in result_str

    # Should show execution time
    assert "ms" in result_str or "time" in result_str

    # Should not show raw field names
    assert "command:" not in result_str
    assert "output:" not in result_str


@pytest.mark.integration
@pytest.mark.asyncio
async def test_codebase_shell_string_representation_failure(
    indexed_graph: CodebaseGraph,
    run_context: RunContext[AgentDeps],
):
    """Test string representation of failed shell command."""
    result = await codebase_shell(
        ctx=run_context,
        command="rm",  # Blocked command
        args=["test.txt"],
        graph_id=indexed_graph.graph_id,
    )

    assert result.success is False

    result_str = str(result)
    assert isinstance(result_str, str)
    assert len(result_str) > 0

    # Should show error message
    assert "Error" in result_str or "not allowed" in result_str
    assert "rm" in result_str


@pytest.mark.integration
@pytest.mark.asyncio
async def test_codebase_shell_working_directory_context(
    indexed_graph: CodebaseGraph,
    run_context: RunContext[AgentDeps],
):
    """Test that shell commands run in the correct working directory."""
    result = await codebase_shell(
        ctx=run_context, command="pwd", args=[], graph_id=indexed_graph.graph_id
    )

    # Should succeed and show current directory
    assert result.success is True
    assert result.command == "pwd"
    assert result.stdout is not None

    # Output should contain some path
    assert "/" in result.stdout or "\\" in result.stdout


@pytest.mark.integration
@pytest.mark.asyncio
async def test_codebase_shell_multiple_args(
    indexed_graph: CodebaseGraph,
    run_context: RunContext[AgentDeps],
):
    """Test shell command with multiple arguments."""
    result = await codebase_shell(
        ctx=run_context,
        command="grep",
        args=["-n", "-i", "calculator", "main.py"],
        graph_id=indexed_graph.graph_id,
    )

    # Should succeed
    assert result.success is True
    assert result.command == "grep"
    assert result.args == ["-n", "-i", "calculator", "main.py"]
    assert result.stdout is not None

    # Should find calculator references with line numbers (due to -n)
    if "calculator" in result.stdout.lower():
        # If found, should show line numbers due to -n flag
        assert any(char.isdigit() for char in result.stdout)
