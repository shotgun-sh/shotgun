"""CLI-based Claude Code runner for teams/multi-agent work.

Invokes `claude -p --output-format stream-json --verbose` as an async
subprocess. Parses streaming JSON and yields filtered ClaudeOutput.
Used for parallel batch execution where teams support is needed.
"""

import asyncio
import json
import logging
import os
from collections.abc import AsyncGenerator
from typing import Any

from shotgun.agents.autopilot.claude_subprocess import ClaudeSubprocessConfig
from shotgun.agents.autopilot.models import ClaudeOutput, ClaudeOutputType

logger = logging.getLogger(__name__)

# Team-related tools whose invocations we want to surface to the orchestrator
_TEAM_TOOLS = frozenset(
    {
        "Task",
        "TeamCreate",
        "TeamDelete",
        "SendMessage",
        "TaskCreate",
        "TaskUpdate",
        "TaskList",
        "TaskGet",
    }
)


class ClaudeCliSubprocess:
    """CLI-based Claude Code runner for teams/multi-agent work.

    Invokes `claude -p --output-format stream-json --verbose` as an async
    subprocess. Parses streaming JSON and yields filtered ClaudeOutput.
    Used for parallel batch execution where teams support is needed.
    """

    def __init__(self, config: ClaudeSubprocessConfig | None = None):
        self.config = config or ClaudeSubprocessConfig()
        self._process: asyncio.subprocess.Process | None = None
        self._cancelled = False

    def _build_command(self, prompt: str) -> list[str]:
        """Build the CLI command array.

        Args:
            prompt: The prompt to send to Claude Code.

        Returns:
            Command array for subprocess execution.
        """
        cmd = [
            "claude",
            "-p",
            "--output-format",
            "stream-json",
            "--verbose",
            "--permission-mode",
            "bypassPermissions",
        ]
        if self.config.model:
            cmd.extend(["--model", self.config.model])
        cmd.append(prompt)
        return cmd

    def _build_env(self) -> dict[str, str]:
        """Build environment variables for the subprocess.

        Returns:
            Merged environment dict.
        """
        env = os.environ.copy()
        env.update(self.config.env_vars)
        return env

    async def run(self, prompt: str) -> AsyncGenerator[ClaudeOutput, None]:
        """Run Claude Code CLI and stream filtered output.

        Args:
            prompt: The prompt to send to Claude Code.

        Yields:
            ClaudeOutput objects for text responses and team tool calls.
        """
        self._cancelled = False
        cmd = self._build_command(prompt)
        env = self._build_env()

        logger.info(
            "Starting Claude CLI execution in %s with prompt length %d chars",
            self.config.working_directory,
            len(prompt),
        )
        logger.debug("CLI command: %s", " ".join(cmd[:6]) + " ...")

        try:
            self._process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.config.working_directory),
                env=env,
            )

            if self._process.stdout is None:
                yield ClaudeOutput(
                    type=ClaudeOutputType.ERROR,
                    content="Claude CLI stdout not available",
                )
                return

            async for line in self._process.stdout:
                if self._cancelled:
                    logger.info("Claude CLI execution cancelled")
                    break

                decoded = line.decode("utf-8", errors="replace").strip()
                if not decoded:
                    continue

                try:
                    data = json.loads(decoded)
                except json.JSONDecodeError:
                    logger.debug("Non-JSON line from CLI: %s", decoded[:200])
                    continue

                output = self._process_message(data)
                if output is not None:
                    yield output

            # Wait for process to finish
            await self._process.wait()

            if self._cancelled:
                return

            exit_code = self._process.returncode or 0
            if exit_code != 0:
                # Read stderr for error details
                stderr_data = b""
                if self._process.stderr:
                    stderr_data = await self._process.stderr.read()
                stderr_text = stderr_data.decode("utf-8", errors="replace").strip()
                logger.error(
                    "Claude CLI exited with code %d: %s", exit_code, stderr_text[:500]
                )
                yield ClaudeOutput(
                    type=ClaudeOutputType.ERROR,
                    content=f"Claude CLI error (exit {exit_code}): {stderr_text[:500] or 'unknown error'}",
                )

            yield ClaudeOutput(
                type=ClaudeOutputType.EXIT,
                content="Claude CLI finished",
                exit_code=exit_code,
            )

        except Exception as e:
            logger.exception("Claude CLI error")
            yield ClaudeOutput(
                type=ClaudeOutputType.ERROR,
                content=f"Claude CLI error: {e}",
            )
            yield ClaudeOutput(
                type=ClaudeOutputType.EXIT,
                content="Claude CLI exited with error",
                exit_code=1,
            )
        finally:
            self._process = None

    def _process_message(self, data: dict[str, Any]) -> ClaudeOutput | None:
        """Process a single stream-json message and return filtered output.

        Args:
            data: Parsed JSON message from the CLI stream.

        Returns:
            ClaudeOutput if the message should be forwarded, None to skip.
        """
        msg_type = data.get("type", "")

        if msg_type == "system":
            # Session metadata — skip
            return None

        if msg_type == "result":
            # Final result message
            result_text = ""
            subtype = data.get("subtype", "success")
            cost_usd = data.get("cost_usd")
            if cost_usd is not None:
                result_text = f"Claude finished ({subtype}, ${cost_usd:.4f})"
            else:
                result_text = f"Claude finished ({subtype})"
            logger.info("Claude CLI result: %s", result_text)
            return ClaudeOutput(
                type=ClaudeOutputType.STDOUT,
                content=result_text,
            )

        if msg_type == "assistant":
            return self._process_assistant_message(data)

        # user messages (tool results), etc. — skip
        return None

    def _process_assistant_message(self, data: dict[str, Any]) -> ClaudeOutput | None:
        """Process an assistant message from the stream.

        Args:
            data: The assistant message data.

        Returns:
            ClaudeOutput for text and team tool calls, None for noise.
        """
        message = data.get("message", {})
        content_blocks = message.get("content", [])

        parts: list[str] = []
        for block in content_blocks:
            block_type = block.get("type", "")

            if block_type == "text":
                text = block.get("text", "").strip()
                if text:
                    parts.append(text)

            elif block_type == "tool_use":
                tool_name = block.get("name", "")
                if tool_name in _TEAM_TOOLS:
                    tool_input = block.get("input", {})
                    formatted = _format_team_tool(tool_name, tool_input)
                    parts.append(formatted)
                # Non-team tool calls (Bash, Read, Edit etc.) — skip

        if parts:
            content = "\n".join(parts)
            logger.info(
                "Claude CLI output: %s",
                content[:200] + "..." if len(content) > 200 else content,
            )
            return ClaudeOutput(
                type=ClaudeOutputType.STDOUT,
                content=content,
            )

        return None

    async def cancel(self) -> None:
        """Cancel the running CLI process."""
        self._cancelled = True
        if self._process and self._process.returncode is None:
            try:
                self._process.kill()
                logger.info("Claude CLI process killed")
            except ProcessLookupError:
                pass  # Already exited


def _format_team_tool(name: str, tool_input: dict[str, Any]) -> str:
    """Format a team tool call compactly for the orchestrator log.

    Args:
        name: Tool name.
        tool_input: Tool input arguments.

    Returns:
        Formatted summary string.
    """
    if name == "TeamCreate":
        team_name = tool_input.get("team_name", "")
        return f"[Teams] Creating team: {team_name}"

    if name == "Task":
        description = tool_input.get("description", "")
        agent_name = tool_input.get("name", "")
        if agent_name:
            return f"[Teams] Spawning agent '{agent_name}': {description}"
        return f"[Teams] Task: {description}"

    if name == "SendMessage":
        recipient = tool_input.get("recipient", "")
        msg_type = tool_input.get("type", "message")
        return f"[Teams] {msg_type} → {recipient}"

    if name == "TaskCreate":
        subject = tool_input.get("subject", "")
        return f"[Teams] Created task: {subject}"

    if name == "TaskUpdate":
        task_id = tool_input.get("taskId", "")
        status = tool_input.get("status", "")
        return f"[Teams] Task {task_id} → {status}"

    if name == "TaskGet":
        task_id = tool_input.get("taskId", "")
        return f"[Teams] Getting task {task_id}"

    if name == "TaskList":
        return "[Teams] Listing tasks"

    if name == "TeamDelete":
        return "[Teams] Deleting team"

    return f"[Teams] {name}"
