"""Execute safe shell commands in codebase context."""

import asyncio
import re
import time
from pathlib import Path

from pydantic_ai import RunContext

from shotgun.agents.models import AgentDeps
from shotgun.logging_config import get_logger

from .models import ShellCommandResult

# Output size limits
MAX_OUTPUT_SIZE = 50000  # Maximum characters allowed in combined stdout/stderr

logger = get_logger(__name__)

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

    Example: Use grep patterns like this so you limit the
    number of results while also getting the total count
    in one command. So as not to exceed output limits.
      `command`:
    ```
    # first 10 hits + grand total
    grep -m 10 -nH "foo" src/main.cpp
    echo "-----"
    echo "total: $(grep -c 'foo' src/main.cpp)"

    # case-insensitive, whole word, with totals
    grep -iw -nH "foo" src/*.cpp | tee /dev/tty | wc -l
    ```

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

            # Check if output is too large
            combined_output_size = len(stdout) + len(stderr)
            if combined_output_size > MAX_OUTPUT_SIZE:
                # Format size info
                if combined_output_size < 1024 * 1024:
                    size_str = f"{combined_output_size / 1024:.1f}KB"
                else:
                    size_str = f"{combined_output_size / (1024 * 1024):.1f}MB"

                guidance_msg = (
                    f"Command output is very large ({size_str}). "
                    "Consider using more targeted commands:\n"
                    "• Use 'head' or 'tail' to limit lines: `head -50 file.txt`\n"
                    "• Add filters to grep: `grep -n 'pattern' file.txt`\n"
                    "• Use find with specific criteria: `find . -name '*.py' -type f`\n"
                    "• Limit directory depth: `find . -maxdepth 2 -type f`\n"
                    "• Use wc to get counts: `wc -l *.py`"
                )

                return ShellCommandResult(
                    success=False,
                    command=command,
                    args=args,
                    error=guidance_msg,
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
