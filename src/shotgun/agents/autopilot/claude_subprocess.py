"""Claude Code CLI subprocess manager.

This module provides async subprocess management for running Claude Code
commands and streaming their output line-by-line to the TUI.
"""

import asyncio
import logging
import shutil
from collections.abc import AsyncGenerator
from pathlib import Path

from pydantic import BaseModel, Field

from shotgun.agents.autopilot.models import ClaudeOutput, ClaudeOutputType

logger = logging.getLogger(__name__)


class ClaudeSubprocessConfig(BaseModel):
    """Configuration for Claude subprocess execution."""

    working_directory: Path = Field(
        default_factory=Path.cwd,
        description="Working directory for Claude execution",
    )
    timeout_seconds: float | None = Field(
        default=None,
        description="Maximum execution time in seconds (None for no timeout)",
    )
    claude_command: str = Field(
        default="claude",
        description="Claude CLI command/path to use",
    )


class ClaudeSubprocessError(Exception):
    """Error during Claude subprocess execution."""


class ClaudeSubprocess:
    """Async subprocess manager for Claude Code CLI.

    Handles spawning the Claude Code CLI as a subprocess, streaming its
    output line-by-line, and supporting cancellation.
    """

    def __init__(self, config: ClaudeSubprocessConfig | None = None):
        """Initialize the subprocess manager.

        Args:
            config: Configuration for subprocess execution.
        """
        self.config = config or ClaudeSubprocessConfig()
        self._process: asyncio.subprocess.Process | None = None
        self._cancelled = False

    @property
    def is_running(self) -> bool:
        """Check if a subprocess is currently running."""
        return self._process is not None and self._process.returncode is None

    def _find_claude_command(self) -> str:
        """Find the Claude CLI command.

        Returns:
            Path to the claude command.

        Raises:
            ClaudeSubprocessError: If claude is not found.
        """
        # Check if configured command exists
        command = self.config.claude_command

        # If it's a path, check if it exists
        if "/" in command or "\\" in command:
            if Path(command).exists():
                return command
            raise ClaudeSubprocessError(f"Claude command not found at: {command}")

        # Otherwise, look in PATH
        claude_path = shutil.which(command)
        if claude_path:
            return claude_path

        raise ClaudeSubprocessError(
            f"Claude CLI not found. Please install it or set the path in config. "
            f"Tried: {command}"
        )

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
            additional_args: Additional CLI arguments to pass.

        Yields:
            ClaudeOutput objects as output is received.

        Raises:
            ClaudeSubprocessError: If the subprocess fails to start.
        """
        self._cancelled = False

        # Find the claude command
        try:
            claude_cmd = self._find_claude_command()
        except ClaudeSubprocessError as e:
            yield ClaudeOutput(
                type=ClaudeOutputType.ERROR,
                content=str(e),
            )
            return

        # Build command arguments
        args = ["--print"]  # Use print mode for non-interactive output

        if allow_permissions:
            args.append("--dangerously-skip-permissions")

        if additional_args:
            args.extend(additional_args)

        # Add the prompt
        args.extend(["--prompt", prompt])

        logger.info(
            "Starting Claude subprocess: %s %s",
            claude_cmd,
            " ".join(args[:5]) + "...",
        )

        # Start the subprocess
        try:
            self._process = await asyncio.create_subprocess_exec(
                claude_cmd,
                *args,
                cwd=self.config.working_directory,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except Exception as e:
            logger.error("Failed to start Claude subprocess: %s", e)
            yield ClaudeOutput(
                type=ClaudeOutputType.ERROR,
                content=f"Failed to start Claude: {e}",
            )
            return

        # Stream output from both stdout and stderr
        async for output in self._stream_output():
            yield output

    async def _stream_output(self) -> AsyncGenerator[ClaudeOutput, None]:
        """Stream output from the running subprocess.

        Yields:
            ClaudeOutput objects for each line of output.
        """
        if self._process is None:
            return

        stdout = self._process.stdout
        stderr = self._process.stderr

        if stdout is None or stderr is None:
            yield ClaudeOutput(
                type=ClaudeOutputType.ERROR,
                content="Failed to capture subprocess output",
            )
            return

        # Create tasks to read from both streams
        async def read_stream(
            stream: asyncio.StreamReader, output_type: ClaudeOutputType
        ) -> AsyncGenerator[ClaudeOutput, None]:
            """Read lines from a stream and yield output objects."""
            while True:
                if self._cancelled:
                    break

                try:
                    line = await asyncio.wait_for(
                        stream.readline(),
                        timeout=1.0,  # Check for cancellation periodically
                    )
                except asyncio.TimeoutError:
                    # Check if process is still running
                    if self._process and self._process.returncode is not None:
                        break
                    continue

                if not line:
                    break

                content = line.decode("utf-8", errors="replace").rstrip("\n\r")
                if content:  # Only yield non-empty lines
                    yield ClaudeOutput(
                        type=output_type,
                        content=content,
                    )

        # Interleave stdout and stderr using asyncio.Queue
        output_queue: asyncio.Queue[ClaudeOutput | None] = asyncio.Queue()

        async def reader_task(
            stream: asyncio.StreamReader, output_type: ClaudeOutputType
        ) -> None:
            """Task to read from a stream and put items in queue."""
            async for output in read_stream(stream, output_type):
                await output_queue.put(output)
            await output_queue.put(None)  # Signal done

        # Start reader tasks
        stdout_task = asyncio.create_task(reader_task(stdout, ClaudeOutputType.STDOUT))
        stderr_task = asyncio.create_task(reader_task(stderr, ClaudeOutputType.STDERR))

        # Yield outputs as they arrive
        done_count = 0
        while done_count < 2:
            if self._cancelled:
                stdout_task.cancel()
                stderr_task.cancel()
                break

            try:
                output = await asyncio.wait_for(
                    output_queue.get(),
                    timeout=self.config.timeout_seconds,
                )
            except asyncio.TimeoutError:
                logger.warning("Claude subprocess timed out")
                yield ClaudeOutput(
                    type=ClaudeOutputType.ERROR,
                    content=f"Claude timed out after {self.config.timeout_seconds} seconds",
                )
                await self.cancel()
                break

            if output is None:
                done_count += 1
            else:
                yield output

        # Wait for process to complete
        if self._process and self._process.returncode is None:
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self._process.kill()
                await self._process.wait()

        # Yield exit status
        exit_code = self._process.returncode if self._process else -1
        yield ClaudeOutput(
            type=ClaudeOutputType.EXIT,
            content=f"Claude exited with code {exit_code}",
            exit_code=exit_code,
        )

        # Cleanup
        self._process = None

    async def cancel(self) -> None:
        """Cancel the running subprocess."""
        self._cancelled = True

        if self._process and self._process.returncode is None:
            logger.info("Cancelling Claude subprocess")
            try:
                self._process.terminate()
                try:
                    await asyncio.wait_for(self._process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning("Process did not terminate, killing")
                    self._process.kill()
                    await self._process.wait()
            except ProcessLookupError:
                pass  # Process already terminated

        self._process = None


async def run_claude_command(
    prompt: str,
    working_directory: Path | None = None,
    timeout_seconds: float | None = None,
) -> AsyncGenerator[ClaudeOutput, None]:
    """Convenience function to run a Claude command.

    Args:
        prompt: The prompt to send to Claude.
        working_directory: Working directory for execution.
        timeout_seconds: Optional timeout.

    Yields:
        ClaudeOutput objects as output is received.
    """
    config = ClaudeSubprocessConfig(
        working_directory=working_directory or Path.cwd(),
        timeout_seconds=timeout_seconds,
    )
    subprocess = ClaudeSubprocess(config)

    async for output in subprocess.run(prompt):
        yield output
