"""Autopilot orchestrator for stage-based execution.

This module provides the main orchestration logic for the Autopilot agent,
managing the execution of stages, Claude Code subprocess runs, and PR creation.
"""

import asyncio
import logging
from collections.abc import AsyncGenerator, Callable
from pathlib import Path

from pydantic import BaseModel, Field

from shotgun.agents.autopilot.claude_subprocess import (
    ClaudeSubprocess,
    ClaudeSubprocessConfig,
)
from shotgun.agents.autopilot.models import (
    AutopilotMode,
    AutopilotState,
    ClaudeOutput,
    ClaudeOutputType,
    StageStatus,
)
from shotgun.agents.autopilot.tasks_parser import ParsedTasksFile, TasksParser

logger = logging.getLogger(__name__)


class AutopilotConfig(BaseModel):
    """Configuration for the Autopilot orchestrator."""

    working_directory: Path = Field(
        default_factory=Path.cwd,
        description="Working directory for execution",
    )
    tasks_file_path: str = Field(
        default=".shotgun/tasks.md",
        description="Path to the tasks.md file",
    )
    base_branch: str = Field(
        default="main",
        description="Base branch for creating stage branches",
    )
    branch_prefix: str = Field(
        default="autopilot/stage-",
        description="Prefix for stage branch names",
    )


class AutopilotOrchestrator:
    """Orchestrator for Autopilot stage-based execution.

    Manages the execution lifecycle:
    1. Parse tasks.md to extract stages
    2. Create git branches for each stage
    3. Run Claude Code to complete stage tasks
    4. Create PRs for completed stages
    5. Handle user approval (in pause mode)
    """

    def __init__(
        self,
        config: AutopilotConfig | None = None,
        on_output: Callable[[ClaudeOutput], None] | None = None,
    ):
        """Initialize the orchestrator.

        Args:
            config: Configuration for autopilot execution.
            on_output: Callback for Claude output (for TUI streaming).
        """
        self.config = config or AutopilotConfig()
        self.on_output = on_output
        self.state = AutopilotState(
            tasks_file_path=self.config.tasks_file_path,
            base_branch=self.config.base_branch,
        )
        self._parser = TasksParser(self.config.working_directory)
        self._claude: ClaudeSubprocess | None = None
        self._cancelled = False

    async def initialize(self) -> ParsedTasksFile:
        """Initialize autopilot by parsing tasks.md.

        Returns:
            ParsedTasksFile with stages and any parse errors.
        """
        logger.info("Initializing autopilot from %s", self.config.tasks_file_path)

        parsed = self._parser.parse(self.config.tasks_file_path)

        if parsed.is_valid:
            self.state.stages = parsed.stages
            logger.info(
                "Parsed %d stages with %d total tasks",
                len(parsed.stages),
                parsed.total_tasks,
            )
        else:
            logger.warning("Failed to parse tasks.md: %s", parsed.parse_errors)

        return parsed

    def set_mode(self, mode: AutopilotMode) -> None:
        """Set the execution mode.

        Args:
            mode: The execution mode to use.
        """
        self.state.mode = mode
        logger.info("Autopilot mode set to: %s", mode.value)

    async def run_next_stage(self) -> AsyncGenerator[ClaudeOutput, None]:
        """Run the next pending stage.

        Yields:
            ClaudeOutput objects as Claude Code executes.

        This method:
        1. Creates a git branch for the stage (in auto-continue mode)
        2. Runs Claude Code with a prompt to complete the stage tasks
        3. Refreshes task completion status from tasks.md
        4. Updates stage status
        """
        stage = self.state.current_stage
        if stage is None:
            yield ClaudeOutput(
                type=ClaudeOutputType.ERROR,
                content="No current stage to execute",
            )
            return

        logger.info("Starting execution of Stage %d: %s", stage.number, stage.name)
        stage.status = StageStatus.IN_PROGRESS

        # In auto-continue mode, create a branch for this stage
        if self.state.mode == AutopilotMode.AUTO_CONTINUE:
            async for output in self._create_stage_branch(stage.number):
                yield output
                if output.type == ClaudeOutputType.ERROR:
                    stage.status = StageStatus.FAILED
                    return

        # Build the prompt for Claude Code
        prompt = self._build_stage_prompt(stage)

        # Run Claude Code
        config = ClaudeSubprocessConfig(
            working_directory=self.config.working_directory,
        )
        self._claude = ClaudeSubprocess(config)

        try:
            async for output in self._claude.run(prompt):
                yield output

                # Check if execution failed
                if output.type == ClaudeOutputType.EXIT and output.exit_code != 0:
                    logger.warning(
                        "Claude exited with non-zero code: %d", output.exit_code
                    )

        except Exception as e:
            logger.error("Error running Claude: %s", e)
            yield ClaudeOutput(
                type=ClaudeOutputType.ERROR,
                content=f"Error running Claude: {e}",
            )
            stage.status = StageStatus.FAILED
            return
        finally:
            self._claude = None

        # Refresh stages from tasks.md to check completion
        self.state.stages = self._parser.refresh_stages(
            self.state.stages,
            self.config.tasks_file_path,
        )

        # Get the updated stage
        updated_stage = self.state.current_stage
        if updated_stage and updated_stage.is_complete:
            updated_stage.status = StageStatus.COMPLETED
            logger.info("Stage %d completed successfully", stage.number)
        else:
            # Stage not fully complete - may need another iteration
            remaining = len(updated_stage.pending_tasks) if updated_stage else 0
            logger.info("Stage %d has %d remaining tasks", stage.number, remaining)

    def _build_stage_prompt(self, stage: "Stage") -> str:
        """Build the prompt for Claude Code to work on a stage.

        Args:
            stage: The stage to build a prompt for.

        Returns:
            The formatted prompt string.
        """
        task_list = stage.format_task_list()

        prompt = f"""Work on Stage {stage.number}: {stage.name}

Complete the following tasks. As you complete each task, mark it as done in {self.state.tasks_file_path} by changing `- [ ]` to `- [x]`.

Tasks:
{task_list}

Important:
- Focus only on tasks for this stage
- Mark each task complete in {self.state.tasks_file_path} as you finish it
- Commit your changes when you complete tasks
- Be thorough but efficient
"""
        return prompt

    async def _create_stage_branch(
        self, stage_number: int
    ) -> AsyncGenerator[ClaudeOutput, None]:
        """Create a git branch for a stage.

        Args:
            stage_number: The stage number to create a branch for.

        Yields:
            ClaudeOutput with the result.
        """
        branch_name = f"{self.config.branch_prefix}{stage_number}"
        stage = self.state.stages[stage_number - 1]

        # Determine the base branch
        if stage_number == 1:
            base = self.state.base_branch
        else:
            # Stack on previous stage's branch
            base = f"{self.config.branch_prefix}{stage_number - 1}"

        logger.info("Creating branch %s from %s", branch_name, base)

        # Use git to create and checkout the branch
        try:
            process = await asyncio.create_subprocess_exec(
                "git",
                "checkout",
                "-b",
                branch_name,
                base,
                cwd=self.config.working_directory,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                # Branch might already exist, try just checking it out
                process = await asyncio.create_subprocess_exec(
                    "git",
                    "checkout",
                    branch_name,
                    cwd=self.config.working_directory,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await process.communicate()

                if process.returncode != 0:
                    error_msg = stderr.decode("utf-8", errors="replace")
                    yield ClaudeOutput(
                        type=ClaudeOutputType.ERROR,
                        content=f"Failed to create/checkout branch: {error_msg}",
                    )
                    return

            stage.branch_name = branch_name
            self.state.current_branch = branch_name

            yield ClaudeOutput(
                type=ClaudeOutputType.STDOUT,
                content=f"Created and checked out branch: {branch_name}",
            )

        except Exception as e:
            yield ClaudeOutput(
                type=ClaudeOutputType.ERROR,
                content=f"Git error: {e}",
            )

    async def create_pr(self) -> AsyncGenerator[ClaudeOutput, None]:
        """Create a PR for the current stage.

        Yields:
            ClaudeOutput with progress and result.
        """
        stage = self.state.current_stage
        if stage is None:
            yield ClaudeOutput(
                type=ClaudeOutputType.ERROR,
                content="No current stage for PR creation",
            )
            return

        logger.info("Creating PR for Stage %d", stage.number)

        # Build the prompt for Claude to create a PR
        prompt = f"""Create a pull request for Stage {stage.number}: {stage.name}

Use `gh pr create` to create the PR with:
- A clear title mentioning Stage {stage.number}
- A description summarizing the work completed
- Target the appropriate base branch

Just create the PR and report the URL.
"""

        config = ClaudeSubprocessConfig(
            working_directory=self.config.working_directory,
        )
        self._claude = ClaudeSubprocess(config)

        try:
            async for output in self._claude.run(prompt):
                yield output

                # Try to extract PR URL from output
                if output.type == ClaudeOutputType.STDOUT:
                    if "github.com" in output.content and "/pull/" in output.content:
                        # Extract URL
                        import re

                        url_match = re.search(
                            r"https://github\.com/[^\s]+/pull/\d+",
                            output.content,
                        )
                        if url_match:
                            pr_url = url_match.group(0)
                            stage.pr_url = pr_url
                            self.state.pr_urls.append(pr_url)
                            logger.info("PR created: %s", pr_url)

        except Exception as e:
            yield ClaudeOutput(
                type=ClaudeOutputType.ERROR,
                content=f"Error creating PR: {e}",
            )
        finally:
            self._claude = None

    async def review_pr(self) -> AsyncGenerator[ClaudeOutput, None]:
        """Have Claude review the current stage's PR.

        Yields:
            ClaudeOutput with the review results.
        """
        stage = self.state.current_stage
        if stage is None or stage.pr_url is None:
            yield ClaudeOutput(
                type=ClaudeOutputType.ERROR,
                content="No PR to review",
            )
            return

        logger.info("Reviewing PR for Stage %d", stage.number)

        prompt = f"""Review the changes in the current PR.

PR URL: {stage.pr_url}

Provide a brief review of:
1. Code quality and correctness
2. Any potential issues or improvements
3. Whether the stage tasks appear complete
"""

        config = ClaudeSubprocessConfig(
            working_directory=self.config.working_directory,
        )
        self._claude = ClaudeSubprocess(config)

        try:
            async for output in self._claude.run(prompt):
                yield output

        except Exception as e:
            yield ClaudeOutput(
                type=ClaudeOutputType.ERROR,
                content=f"Error reviewing PR: {e}",
            )
        finally:
            self._claude = None

    def advance_to_next_stage(self) -> bool:
        """Advance to the next stage.

        Returns:
            True if advanced successfully, False if no more stages.
        """
        result = self.state.advance_to_next_stage()
        if result:
            logger.info(
                "Advanced to Stage %d: %s",
                self.state.current_stage.number if self.state.current_stage else 0,
                self.state.current_stage.name if self.state.current_stage else "",
            )
        else:
            logger.info("All stages complete")
        return result

    async def cancel(self) -> None:
        """Cancel the current execution."""
        self._cancelled = True
        if self._claude:
            await self._claude.cancel()
        logger.info("Autopilot cancelled")

    @property
    def is_complete(self) -> bool:
        """Check if all stages are complete."""
        return self.state.is_complete

    @property
    def requires_approval(self) -> bool:
        """Check if we need user approval to continue.

        Returns True in pause mode after stage completion.
        """
        if self.state.mode != AutopilotMode.PAUSE_BETWEEN:
            return False

        current = self.state.current_stage
        if current is None:
            return False

        return current.status == StageStatus.COMPLETED


# Import Stage here to avoid circular imports
from shotgun.agents.autopilot.models import Stage  # noqa: E402
