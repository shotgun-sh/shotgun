"""Tests for ClaudeCliSubprocess."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shotgun.agents.autopilot.claude_cli_subprocess import (
    ClaudeCliSubprocess,
    _format_team_tool,
)
from shotgun.agents.autopilot.claude_subprocess import ClaudeSubprocessConfig
from shotgun.agents.autopilot.models import ClaudeOutputType


def _make_stream_line(data: dict) -> bytes:
    """Encode a dict as a JSON line (as stdout would produce)."""
    return (json.dumps(data) + "\n").encode("utf-8")


def _make_mock_process(
    stdout_lines: list[bytes],
    returncode: int = 0,
) -> MagicMock:
    """Create a mock asyncio subprocess with controlled stdout."""
    proc = MagicMock()
    proc.returncode = returncode

    # Make stdout an async iterator over lines
    async def _iter_lines():
        for line in stdout_lines:
            yield line

    proc.stdout = _iter_lines()
    proc.stderr = AsyncMock()
    proc.stderr.read = AsyncMock(return_value=b"")

    async def _wait():
        proc.returncode = returncode

    proc.wait = _wait
    proc.kill = MagicMock()
    return proc


@pytest.mark.asyncio
async def test_cli_subprocess_builds_correct_command():
    """Verify the command array includes required flags and the prompt."""
    config = ClaudeSubprocessConfig(model="claude-sonnet-4-6")
    cli = ClaudeCliSubprocess(config)

    cmd = cli._build_command("Do something")

    assert cmd[0] == "claude"
    assert "-p" in cmd
    assert "--output-format" in cmd
    assert cmd[cmd.index("--output-format") + 1] == "stream-json"
    assert "--verbose" in cmd
    assert "--permission-mode" in cmd
    assert cmd[cmd.index("--permission-mode") + 1] == "bypassPermissions"
    assert "--model" in cmd
    assert cmd[cmd.index("--model") + 1] == "claude-sonnet-4-6"
    # Prompt is the last argument
    assert cmd[-1] == "Do something"


@pytest.mark.asyncio
async def test_cli_subprocess_builds_command_without_model():
    """Verify command omits --model when not configured."""
    config = ClaudeSubprocessConfig()
    cli = ClaudeCliSubprocess(config)

    cmd = cli._build_command("test prompt")

    assert "--model" not in cmd
    assert cmd[-1] == "test prompt"


@pytest.mark.asyncio
async def test_cli_subprocess_passes_env_vars():
    """Verify env vars are merged into the subprocess environment."""
    config = ClaudeSubprocessConfig(
        env_vars={"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1", "FOO": "bar"}
    )
    cli = ClaudeCliSubprocess(config)

    env = cli._build_env()

    assert env["CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"] == "1"
    assert env["FOO"] == "bar"
    # Should also include inherited env vars (PATH etc.)
    assert "PATH" in env


@pytest.mark.asyncio
async def test_cli_subprocess_filters_noise():
    """Verify that system messages and non-team tool calls are dropped."""
    stdout_lines = [
        # System message — should be skipped
        _make_stream_line({"type": "system", "subtype": "init", "session_id": "abc"}),
        # Assistant with text — should be forwarded
        _make_stream_line(
            {
                "type": "assistant",
                "message": {
                    "content": [{"type": "text", "text": "Working on it..."}],
                },
            }
        ),
        # Assistant with non-team tool use (Bash) — should be skipped
        _make_stream_line(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Bash",
                            "input": {"command": "ls"},
                        },
                    ],
                },
            }
        ),
        # User message (tool result) — should be skipped
        _make_stream_line(
            {
                "type": "user",
                "message": {"content": [{"type": "tool_result", "output": "file1.py"}]},
            }
        ),
        # Result — should be forwarded as STDOUT
        _make_stream_line(
            {
                "type": "result",
                "subtype": "success",
                "cost_usd": 0.05,
            }
        ),
    ]

    proc = _make_mock_process(stdout_lines, returncode=0)

    config = ClaudeSubprocessConfig()
    cli = ClaudeCliSubprocess(config)

    outputs = []
    with patch("asyncio.create_subprocess_exec", return_value=proc):
        async for output in cli.run("test prompt"):
            outputs.append(output)

    # Should have: text message, result message, EXIT
    assert len(outputs) == 3

    assert outputs[0].type == ClaudeOutputType.STDOUT
    assert "Working on it..." in outputs[0].content

    assert outputs[1].type == ClaudeOutputType.STDOUT
    assert "success" in outputs[1].content
    assert "$0.0500" in outputs[1].content

    assert outputs[2].type == ClaudeOutputType.EXIT
    assert outputs[2].exit_code == 0


@pytest.mark.asyncio
async def test_cli_subprocess_forwards_team_tools():
    """Verify Task/TeamCreate/SendMessage tool_use blocks yield formatted output."""
    stdout_lines = [
        _make_stream_line(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "TeamCreate",
                            "input": {"team_name": "parallel-stages"},
                        },
                    ],
                },
            }
        ),
        _make_stream_line(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Task",
                            "input": {
                                "description": "Build auth",
                                "name": "stage-1-worker",
                            },
                        },
                    ],
                },
            }
        ),
        _make_stream_line(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "SendMessage",
                            "input": {
                                "type": "message",
                                "recipient": "stage-1-worker",
                            },
                        },
                    ],
                },
            }
        ),
        _make_stream_line(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "TaskCreate",
                            "input": {"subject": "Implement login"},
                        },
                    ],
                },
            }
        ),
        _make_stream_line(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "TaskUpdate",
                            "input": {"taskId": "1", "status": "completed"},
                        },
                    ],
                },
            }
        ),
    ]

    proc = _make_mock_process(stdout_lines, returncode=0)

    config = ClaudeSubprocessConfig()
    cli = ClaudeCliSubprocess(config)

    outputs = []
    with patch("asyncio.create_subprocess_exec", return_value=proc):
        async for output in cli.run("test"):
            outputs.append(output)

    # 5 team tool outputs + 1 EXIT
    stdout_outputs = [o for o in outputs if o.type == ClaudeOutputType.STDOUT]
    assert len(stdout_outputs) == 5

    assert "[Teams] Creating team: parallel-stages" in stdout_outputs[0].content
    assert "[Teams] Spawning agent 'stage-1-worker'" in stdout_outputs[1].content
    assert "[Teams] message → stage-1-worker" in stdout_outputs[2].content
    assert "[Teams] Created task: Implement login" in stdout_outputs[3].content
    assert "[Teams] Task 1 → completed" in stdout_outputs[4].content


@pytest.mark.asyncio
async def test_cli_subprocess_handles_nonzero_exit():
    """Non-zero exit yields ERROR then EXIT."""
    stdout_lines = [
        _make_stream_line(
            {
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": "Starting..."}]},
            }
        ),
    ]

    proc = _make_mock_process(stdout_lines, returncode=1)
    proc.stderr.read = AsyncMock(return_value=b"Something went wrong")

    config = ClaudeSubprocessConfig()
    cli = ClaudeCliSubprocess(config)

    outputs = []
    with patch("asyncio.create_subprocess_exec", return_value=proc):
        async for output in cli.run("test"):
            outputs.append(output)

    # text + ERROR + EXIT
    assert len(outputs) == 3
    assert outputs[0].type == ClaudeOutputType.STDOUT
    assert outputs[1].type == ClaudeOutputType.ERROR
    assert "Something went wrong" in outputs[1].content
    assert outputs[2].type == ClaudeOutputType.EXIT
    assert outputs[2].exit_code == 1


@pytest.mark.asyncio
async def test_cli_subprocess_cancel():
    """Cancellation kills the process."""
    # Create a process that blocks on stdout
    proc = MagicMock()
    proc.returncode = None

    # Simulate a slow stream — yield one line then hang
    event = asyncio.Event()

    async def _slow_iter():
        yield _make_stream_line(
            {
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": "Starting..."}]},
            }
        )
        # Wait until cancelled
        await event.wait()

    proc.stdout = _slow_iter()
    proc.stderr = AsyncMock()
    proc.stderr.read = AsyncMock(return_value=b"")

    async def _wait():
        proc.returncode = -9

    proc.wait = _wait
    proc.kill = MagicMock()

    config = ClaudeSubprocessConfig()
    cli = ClaudeCliSubprocess(config)

    outputs = []

    async def _run_and_cancel():
        async for output in cli.run("test"):
            outputs.append(output)
            if output.type == ClaudeOutputType.STDOUT:
                # Cancel after first output
                await cli.cancel()
                event.set()  # Unblock the iterator

    with patch("asyncio.create_subprocess_exec", return_value=proc):
        await _run_and_cancel()

    assert cli._cancelled is True
    proc.kill.assert_called_once()


@pytest.mark.asyncio
async def test_cli_subprocess_mixed_text_and_team_tools():
    """Assistant message with both text and team tools yields combined output."""
    stdout_lines = [
        _make_stream_line(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "text", "text": "Setting up the team now."},
                        {
                            "type": "tool_use",
                            "name": "TeamCreate",
                            "input": {"team_name": "my-team"},
                        },
                        # Non-team tool — should be dropped from output
                        {
                            "type": "tool_use",
                            "name": "Read",
                            "input": {"file_path": "/foo/bar.py"},
                        },
                    ],
                },
            }
        ),
    ]

    proc = _make_mock_process(stdout_lines, returncode=0)

    config = ClaudeSubprocessConfig()
    cli = ClaudeCliSubprocess(config)

    outputs = []
    with patch("asyncio.create_subprocess_exec", return_value=proc):
        async for output in cli.run("test"):
            outputs.append(output)

    stdout_outputs = [o for o in outputs if o.type == ClaudeOutputType.STDOUT]
    assert len(stdout_outputs) == 1
    assert "Setting up the team now." in stdout_outputs[0].content
    assert "[Teams] Creating team: my-team" in stdout_outputs[0].content
    # Non-team tool should NOT appear
    assert "Read" not in stdout_outputs[0].content
    assert "bar.py" not in stdout_outputs[0].content


def test_format_team_tool_team_create():
    result = _format_team_tool("TeamCreate", {"team_name": "test-team"})
    assert result == "[Teams] Creating team: test-team"


def test_format_team_tool_task_with_name():
    result = _format_team_tool("Task", {"description": "Build API", "name": "worker-1"})
    assert result == "[Teams] Spawning agent 'worker-1': Build API"


def test_format_team_tool_task_without_name():
    result = _format_team_tool("Task", {"description": "Build API"})
    assert result == "[Teams] Task: Build API"


def test_format_team_tool_send_message():
    result = _format_team_tool(
        "SendMessage", {"type": "shutdown_request", "recipient": "worker-1"}
    )
    assert result == "[Teams] shutdown_request → worker-1"


def test_format_team_tool_task_list():
    result = _format_team_tool("TaskList", {})
    assert result == "[Teams] Listing tasks"
