"""Execute safe shell commands in codebase context."""

import asyncio
import re
import time
from pathlib import Path

from pydantic_ai import RunContext

from shotgun.agents.models import AgentDeps
from shotgun.logging_config import setup_logger

from .models import ShellCommandResult

logger = setup_logger(__name__)

# Whitelist of safe read-only commands
ALLOWED_COMMANDS = {
    "ls",
    "grep",
    "find",
    "git",
    "cat",
    "head",
    "tail",
    "wc",
    "tree",
    "rg",
    "fd",
    "ag",
    "awk",
    "sed",
    "sort",
    "uniq",
    "cut",
    "pwd",
}

# Patterns that indicate command injection attempts
DANGEROUS_PATTERNS = [
    r"[|&;`$]",  # Pipes, background, command termination, backticks, variable expansion
    r"[<>]",  # Redirections
    r"\$\(",  # Command substitution
    r"^\s*\w+\s*=",  # Variable assignment
]


async def codebase_shell(
    ctx: RunContext[AgentDeps],
    command: str,
    args: list[str],
    graph_id: str | None = None,
) -> ShellCommandResult:
    """Execute safe shell commands in codebase context.

    Args:
        ctx: RunContext containing AgentDeps with codebase service
        command: Command to execute (must be in whitelist)
        args: List of command arguments
        graph_id: Optional graph ID to use (defaults to first available graph)

    Returns:
        ShellCommandResult with formatted output via __str__
    """
    logger.debug("🔧 Executing shell command: %s with args: %s", command, args)

    try:
        if not ctx.deps.codebase_service:
            return ShellCommandResult(
                success=False,
                command=command,
                args=args,
                error="No codebase service available in context",
            )

        # Security validation
        if command not in ALLOWED_COMMANDS:
            return ShellCommandResult(
                success=False,
                command=command,
                args=args,
                error=f"Command '{command}' is not allowed. Allowed commands: {', '.join(sorted(ALLOWED_COMMANDS))}",
            )

        # Validate arguments for dangerous patterns
        full_command_str = f"{command} {' '.join(args)}"
        for pattern in DANGEROUS_PATTERNS:
            if re.search(pattern, full_command_str):
                return ShellCommandResult(
                    success=False,
                    command=command,
                    args=args,
                    error="Command contains dangerous patterns. No piping, redirection, or command substitution allowed.",
                )

        # Validate each argument individually
        for arg in args:
            if any(re.search(pattern, arg) for pattern in DANGEROUS_PATTERNS):
                return ShellCommandResult(
                    success=False,
                    command=command,
                    args=args,
                    error=f"Argument '{arg}' contains dangerous patterns.",
                )

        # Get repository path from specified graph or first available graph
        try:
            graphs = await ctx.deps.codebase_service.list_graphs()

            if not graphs:
                return ShellCommandResult(
                    success=False,
                    command=command,
                    args=args,
                    error="No codebases available. Add a codebase first using graph management tools.",
                )

            # Select the appropriate graph
            if graph_id:
                # Find specific graph by ID
                graph = next((g for g in graphs if g.graph_id == graph_id), None)
                if not graph:
                    return ShellCommandResult(
                        success=False,
                        command=command,
                        args=args,
                        error=f"Graph '{graph_id}' not found",
                    )
            else:
                # Use the first available graph
                graph = graphs[0]

            repo_path = Path(graph.repo_path)
            if not repo_path.exists():
                return ShellCommandResult(
                    success=False,
                    command=command,
                    args=args,
                    error=f"Repository path '{repo_path}' does not exist",
                )

        except Exception as e:
            logger.error("Error getting graphs: %s", e)
            return ShellCommandResult(
                success=False,
                command=command,
                args=args,
                error="Could not access codebase information",
            )

        # Execute command asynchronously
        start_time = time.time()
        try:
            # Use asyncio subprocess for proper async execution
            process = await asyncio.create_subprocess_exec(
                command,
                *args,
                cwd=repo_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(), timeout=30.0
                )
                stdout = stdout_bytes.decode("utf-8", errors="replace")
                stderr = stderr_bytes.decode("utf-8", errors="replace")
                return_code = process.returncode or 0
            except asyncio.TimeoutError:
                # Kill the process and return timeout error
                process.kill()
                return ShellCommandResult(
                    success=False,
                    command=command,
                    args=args,
                    error="Command timed out after 30 seconds",
                )

            execution_time_ms = (time.time() - start_time) * 1000
            success = return_code == 0

            logger.debug(
                "📄 Command completed: %s with exit code %d in %.1fms",
                "success" if success else "failed",
                return_code,
                execution_time_ms,
            )

            return ShellCommandResult(
                success=success,
                command=command,
                args=args,
                stdout=stdout,
                stderr=stderr,
                return_code=return_code,
                execution_time_ms=execution_time_ms,
            )

        except FileNotFoundError:
            return ShellCommandResult(
                success=False,
                command=command,
                args=args,
                error=f"Command '{command}' not found on system",
            )

    except Exception as e:
        error_msg = f"Error executing command: {str(e)}"
        logger.error("❌ Shell command failed: %s", str(e))
        return ShellCommandResult(
            success=False, command=command, args=args, error=error_msg
        )
