"""Claude Code SDK integration for Autopilot.

This module provides async integration with the Claude Agent SDK
for running Claude Code and streaming output to the TUI.
"""

import logging
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from shotgun.agents.autopilot.models import ClaudeOutput, ClaudeOutputType

logger = logging.getLogger(__name__)


class ClaudeSubprocessConfig(BaseModel):
    """Configuration for Claude SDK execution."""

    working_directory: Path = Field(
        default_factory=Path.cwd,
        description="Working directory for Claude execution",
    )
    timeout_seconds: float | None = Field(
        default=None,
        description="Maximum execution time in seconds (None for no timeout)",
    )
    model: str | None = Field(
        default=None,
        description="Model to use (defaults to Claude's default)",
    )
    system_prompt: str | None = Field(
        default=None,
        description="Optional system prompt to prepend",
    )


class ClaudeSubprocessError(Exception):
    """Error during Claude SDK execution."""


class ClaudeSubprocess:
    """Claude Agent SDK wrapper for Autopilot.

    Uses the official claude-agent-sdk to run Claude Code and stream
    output back to the TUI.
    """

    def __init__(self, config: ClaudeSubprocessConfig | None = None):
        """Initialize the SDK wrapper.

        Args:
            config: Configuration for SDK execution.
        """
        self.config = config or ClaudeSubprocessConfig()
        self._cancelled = False

    @property
    def is_running(self) -> bool:
        """Check if execution is in progress."""
        return not self._cancelled

    async def run(
        self,
        prompt: str,
        *,
        allow_permissions: bool = True,
        additional_args: list[str] | None = None,
    ) -> AsyncGenerator[ClaudeOutput, None]:
        """Run Claude Code with a prompt and stream output.

        Args:
            prompt: The prompt to send to Claude Code.
            allow_permissions: Whether to auto-accept permission prompts.
            additional_args: Additional CLI arguments (ignored, kept for compatibility).

        Yields:
            ClaudeOutput objects as output is received.
        """
        self._cancelled = False

        try:
            from claude_agent_sdk import (
                AssistantMessage,
                ClaudeAgentOptions,
                PermissionMode,
                ResultMessage,
                TextBlock,
                ToolResultBlock,
                ToolUseBlock,
                query,
            )
        except ImportError as e:
            yield ClaudeOutput(
                type=ClaudeOutputType.ERROR,
                content=f"claude-agent-sdk not installed: {e}. Run: uv add claude-agent-sdk",
            )
            return

        # Build options
        permission_mode: PermissionMode = (
            "bypassPermissions" if allow_permissions else "default"
        )

        options = ClaudeAgentOptions(
            allowed_tools=["Read", "Edit", "Write", "Glob", "Grep", "Bash"],
            permission_mode=permission_mode,
            cwd=str(self.config.working_directory),
            # Ensure fresh session - no conversation continuation
            continue_conversation=False,
        )

        if self.config.model:
            options.model = self.config.model

        if self.config.system_prompt:
            options.system_prompt = self.config.system_prompt

        logger.info(
            "Starting Claude SDK execution in %s with prompt length %d chars",
            self.config.working_directory,
            len(prompt),
        )
        logger.debug("Claude prompt: %s", prompt[:500] + "..." if len(prompt) > 500 else prompt)

        got_result = False
        message_count = 0
        tool_call_count = 0
        try:
            async for message in query(prompt=prompt, options=options):
                if self._cancelled:
                    logger.info("Claude execution cancelled by user")
                    break

                message_count += 1

                # Handle different message types
                if isinstance(message, AssistantMessage):
                    # Claude's response - content is directly on the message
                    content = getattr(message, "content", []) or []
                    for block in content:
                        if isinstance(block, TextBlock):
                            if block.text:
                                # Log significant text messages (not just whitespace)
                                text = block.text.strip()
                                if text:
                                    logger.info("Claude response: %s", text[:200] + "..." if len(text) > 200 else text)
                                yield ClaudeOutput(
                                    type=ClaudeOutputType.STDOUT,
                                    content=block.text,
                                )
                        elif isinstance(block, ToolUseBlock):
                            tool_name = getattr(block, "name", "unknown")
                            tool_input = getattr(block, "input", {}) or {}
                            tool_call_count += 1

                            logger.info("Claude tool call #%d: %s", tool_call_count, tool_name)
                            logger.debug("Tool input: %s", tool_input)

                            # Format tool call with relevant details
                            detail = self._format_tool_detail(tool_name, tool_input)
                            yield ClaudeOutput(
                                type=ClaudeOutputType.STDOUT,
                                content=detail,
                            )
                        elif isinstance(block, ToolResultBlock):
                            # Tool results can be verbose, just log
                            logger.debug("Tool result block received")

                elif isinstance(message, ResultMessage):
                    # Final result
                    got_result = True
                    subtype = getattr(message, "subtype", "completed")
                    logger.info(
                        "Claude completed with subtype '%s' after %d messages and %d tool calls",
                        subtype,
                        message_count,
                        tool_call_count,
                    )
                    yield ClaudeOutput(
                        type=ClaudeOutputType.EXIT,
                        content=f"Claude finished: {subtype}",
                        exit_code=0,
                    )

        except Exception as e:
            logger.exception("Claude SDK error")
            yield ClaudeOutput(
                type=ClaudeOutputType.ERROR,
                content=f"Claude SDK error: {e}",
            )
            yield ClaudeOutput(
                type=ClaudeOutputType.EXIT,
                content="Claude exited with error",
                exit_code=1,
            )
            return

        # If we completed normally without a ResultMessage
        if not self._cancelled and not got_result:
            yield ClaudeOutput(
                type=ClaudeOutputType.EXIT,
                content="Claude completed",
                exit_code=0,
            )

    def _format_tool_detail(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """Format tool call with relevant details.

        Args:
            tool_name: Name of the tool (Read, Edit, Bash, etc.)
            tool_input: Input arguments for the tool.

        Returns:
            Formatted string with tool details.
        """
        if tool_name == "Read":
            path = tool_input.get("file_path", "")
            # Shorten long paths
            if len(path) > 50:
                path = "..." + path[-47:]
            return f"📖 Read: {path}"

        elif tool_name == "Edit":
            path = tool_input.get("file_path", "")
            if len(path) > 50:
                path = "..." + path[-47:]
            return f"✏️ Edit: {path}"

        elif tool_name == "Write":
            path = tool_input.get("file_path", "")
            if len(path) > 50:
                path = "..." + path[-47:]
            return f"📝 Write: {path}"

        elif tool_name == "Bash":
            cmd = tool_input.get("command", "")
            # Truncate long commands
            if len(cmd) > 60:
                cmd = cmd[:57] + "..."
            return f"💻 Bash: {cmd}"

        elif tool_name == "Glob":
            pattern = tool_input.get("pattern", "")
            return f"🔍 Glob: {pattern}"

        elif tool_name == "Grep":
            pattern = tool_input.get("pattern", "")
            path = tool_input.get("path", ".")
            return f"🔎 Grep: '{pattern}' in {path}"

        else:
            return f"🔧 {tool_name}"

    async def cancel(self) -> None:
        """Cancel the running execution."""
        self._cancelled = True
        logger.info("Claude SDK execution cancelled")


async def run_claude_command(
    prompt: str,
    working_directory: Path | None = None,
    timeout_seconds: float | None = None,
) -> AsyncGenerator[ClaudeOutput, None]:
    """Convenience function to run a Claude command.

    Args:
        prompt: The prompt to send to Claude.
        working_directory: Working directory for execution.
        timeout_seconds: Optional timeout (not currently implemented with SDK).

    Yields:
        ClaudeOutput objects as output is received.
    """
    config = ClaudeSubprocessConfig(
        working_directory=working_directory or Path.cwd(),
        timeout_seconds=timeout_seconds,
    )
    sdk = ClaudeSubprocess(config)

    async for output in sdk.run(prompt):
        yield output
