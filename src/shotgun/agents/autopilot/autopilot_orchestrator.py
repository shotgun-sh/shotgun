"""Autopilot orchestrator for stage-based execution.

This module provides the main orchestration logic for the Autopilot agent,
managing the execution of stages with a complete workflow:
1. Execute tasks until stage is complete
2. Create PR
3. Review and fix code
4. Run QA testing
5. Present for user approval
"""

import asyncio
import logging
import re
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
    Stage,
    StagePhase,
    StageStatus,
)
from shotgun.agents.autopilot.tasks_parser import ParsedTasksFile, TasksParser

logger = logging.getLogger(__name__)

MAX_STAGE_ITERATIONS = 5  # Max attempts to complete a stage


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
    max_iterations: int = Field(
        default=MAX_STAGE_ITERATIONS,
        description="Maximum iterations per stage before giving up",
    )


class AutopilotOrchestrator:
    """Orchestrator for Autopilot stage-based execution.

    Manages the complete execution lifecycle for each stage:
    1. Execute tasks until all are marked complete in tasks.md
    2. Create a PR for the completed work
    3. Review the PR and make any necessary fixes
    4. Run manual QA testing
    5. Present to user for approval (Accept/Reject)
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

    async def run_stage_workflow(self) -> AsyncGenerator[ClaudeOutput, None]:
        """Run the complete workflow for the current stage.

        This is the main entry point that runs through:
        1. Task execution (looping until complete)
        2. PR creation
        3. Code review and fixes
        4. QA testing
        5. Sets awaiting_approval for user decision

        Yields:
            ClaudeOutput objects as work progresses.
        """
        stage = self.state.current_stage
        if stage is None:
            yield ClaudeOutput(
                type=ClaudeOutputType.ERROR,
                content="No current stage to execute",
            )
            return

        logger.info("Starting workflow for Stage %d: %s", stage.number, stage.name)
        stage.status = StageStatus.IN_PROGRESS

        # Create branch for this stage
        async for output in self._create_stage_branch(stage.number):
            yield output
            if output.type == ClaudeOutputType.ERROR:
                stage.status = StageStatus.FAILED
                return

        # Phase 1: Execute tasks until complete
        stage.phase = StagePhase.EXECUTING
        yield ClaudeOutput(
            type=ClaudeOutputType.STDOUT,
            content=f"📋 Phase 1: Executing tasks for Stage {stage.number}",
        )

        async for output in self._execute_until_complete(stage):
            yield output
            if self._cancelled:
                return

        # Check if stage completed successfully
        self._refresh_stages()
        stage = self.state.current_stage
        if not stage or not stage.is_complete:
            yield ClaudeOutput(
                type=ClaudeOutputType.ERROR,
                content=f"Stage {stage.number if stage else '?'} failed to complete after {self.config.max_iterations} iterations",
            )
            if stage:
                stage.status = StageStatus.FAILED
            return

        # Phase 2: Create PR
        stage.phase = StagePhase.CREATING_PR
        yield ClaudeOutput(
            type=ClaudeOutputType.STDOUT,
            content=f"📝 Phase 2: Creating PR for Stage {stage.number}",
        )

        async for output in self._create_pr(stage):
            yield output
            if self._cancelled:
                return

        # Phase 3: Review and fix
        stage.phase = StagePhase.REVIEWING
        yield ClaudeOutput(
            type=ClaudeOutputType.STDOUT,
            content=f"🔍 Phase 3: Reviewing code for Stage {stage.number}",
        )

        async for output in self._review_and_fix(stage):
            yield output
            if self._cancelled:
                return

        # Phase 4: QA Testing
        stage.phase = StagePhase.QA_TESTING
        yield ClaudeOutput(
            type=ClaudeOutputType.STDOUT,
            content=f"🧪 Phase 4: Running QA tests for Stage {stage.number}",
        )

        async for output in self._run_qa_tests(stage):
            yield output
            if self._cancelled:
                return

        # Phase 5: Ready for user approval
        stage.phase = StagePhase.AWAITING_APPROVAL
        stage.status = StageStatus.COMPLETED
        self.state.awaiting_approval = True

        yield ClaudeOutput(
            type=ClaudeOutputType.STDOUT,
            content=f"✅ Stage {stage.number} ready for review. PR: {stage.pr_url or 'N/A'}",
        )

    async def _execute_until_complete(
        self, stage: Stage
    ) -> AsyncGenerator[ClaudeOutput, None]:
        """Execute stage tasks until all are marked complete.

        Args:
            stage: The stage to execute.

        Yields:
            ClaudeOutput as execution progresses.
        """
        while stage.iteration_count < self.config.max_iterations:
            if self._cancelled:
                return

            stage.iteration_count += 1
            remaining = len(stage.pending_tasks)

            yield ClaudeOutput(
                type=ClaudeOutputType.STDOUT,
                content=f"  Iteration {stage.iteration_count}: {remaining} tasks remaining",
            )

            # Build and run the prompt
            prompt = self._build_execution_prompt(stage)
            async for output in self._run_claude(prompt):
                yield output

            # Refresh and check completion
            self._refresh_stages()
            updated_stage = self.state.current_stage
            if updated_stage is None:
                return

            # Update the loop variable
            stage = updated_stage

            if stage.is_complete:
                yield ClaudeOutput(
                    type=ClaudeOutputType.STDOUT,
                    content=f"  All tasks complete after {stage.iteration_count} iteration(s)",
                )
                return

        yield ClaudeOutput(
            type=ClaudeOutputType.STDERR,
            content=f"  Max iterations ({self.config.max_iterations}) reached",
        )

    async def _create_pr(self, stage: Stage) -> AsyncGenerator[ClaudeOutput, None]:
        """Create a PR for the completed stage.

        Args:
            stage: The stage to create a PR for.

        Yields:
            ClaudeOutput with progress.
        """
        preamble = self._build_context_preamble()
        prompt = f"""{preamble}Create a pull request for the work completed in Stage {stage.number}: {stage.name}

Instructions:
1. First, commit any uncommitted changes with a clear commit message
2. Push the branch to origin
3. Use `gh pr create` to create the PR with:
   - Title: "Stage {stage.number}: {stage.name}"
   - A description summarizing what was implemented
   - Base branch: {self.state.base_branch}

Report the PR URL when done.
"""
        async for output in self._run_claude(prompt):
            yield output
            # Extract PR URL
            if output.type == ClaudeOutputType.STDOUT:
                self._extract_pr_url(output.content, stage)

    async def _review_and_fix(self, stage: Stage) -> AsyncGenerator[ClaudeOutput, None]:
        """Review the PR code and make any necessary fixes.

        Args:
            stage: The stage to review.

        Yields:
            ClaudeOutput with review progress.
        """
        preamble = self._build_context_preamble()
        prompt = f"""{preamble}Review the code changes for Stage {stage.number}: {stage.name}

Look at the git diff of all changes made and check for:
1. Code quality issues (unused variables, poor naming, etc.)
2. Potential bugs or edge cases not handled
3. Missing error handling
4. Security issues
5. Performance concerns

If you find any issues:
1. Fix them directly
2. Commit the fixes with message "fix: address review feedback for Stage {stage.number}"
3. Push the changes

Be thorough but practical - focus on real issues, not style nitpicks.
"""
        async for output in self._run_claude(prompt):
            yield output

    async def _run_qa_tests(self, stage: Stage) -> AsyncGenerator[ClaudeOutput, None]:
        """Run manual QA testing for the stage.

        Args:
            stage: The stage to test.

        Yields:
            ClaudeOutput with test progress.
        """
        preamble = self._build_context_preamble()
        prompt = f"""{preamble}Perform manual QA testing for Stage {stage.number}: {stage.name}

DO NOT run unit tests (pytest, jest, etc.) - those are separate.

Instead, do manual verification:
1. If there's a CLI tool, run it with various inputs
2. If there's an API, test endpoints with curl or similar
3. If there's a script, execute it and verify output
4. Check that files were created/modified as expected
5. Verify any configuration is correct

If you find bugs:
1. Fix them
2. Commit with message "fix: QA fixes for Stage {stage.number}"
3. Push the changes
4. Re-test to confirm the fix

Report what you tested and the results.
"""
        async for output in self._run_claude(prompt):
            yield output

    def _build_context_preamble(self) -> str:
        """Build a preamble that loads project context.

        Returns:
            Preamble text instructing Claude to load .shotgun/ context.
        """
        return f"""First, read these files to understand the project context:
1. Read {self.state.tasks_file_path} to see all stages and tasks
2. Read .shotgun/spec.md if it exists to understand the specification
3. Read .shotgun/plan.md if it exists to understand the implementation plan

This gives you fresh context about the project state.

---

"""

    def _build_execution_prompt(self, stage: Stage) -> str:
        """Build the prompt for executing stage tasks.

        Args:
            stage: The stage to build prompt for.

        Returns:
            The formatted prompt.
        """
        pending = stage.pending_tasks
        task_list = "\n".join(f"- [ ] {task.text}" for task in pending)

        preamble = self._build_context_preamble()

        return f"""{preamble}Complete the remaining tasks for Stage {stage.number}: {stage.name}

IMPORTANT: Only work on THIS stage's tasks. Do not work ahead.

Remaining tasks:
{task_list}

Instructions:
1. Complete each task thoroughly
2. After completing a task, mark it done in {self.state.tasks_file_path} by changing `- [ ]` to `- [x]`
3. Commit your changes after completing tasks
4. Focus on quality - make sure the implementation is correct

You MUST mark tasks as complete in {self.state.tasks_file_path} when done.
"""

    async def _create_stage_branch(
        self, stage_number: int
    ) -> AsyncGenerator[ClaudeOutput, None]:
        """Create a git branch for a stage.

        Args:
            stage_number: The stage number.

        Yields:
            ClaudeOutput with result.
        """
        branch_name = f"{self.config.branch_prefix}{stage_number}"
        stage = self.state.stages[stage_number - 1]

        # Determine base branch
        if stage_number == 1:
            base = self.state.base_branch
        else:
            base = f"{self.config.branch_prefix}{stage_number - 1}"

        logger.info("Creating branch %s from %s", branch_name, base)

        try:
            # Try to create new branch
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
            await process.communicate()

            if process.returncode != 0:
                # Branch might exist, try checking it out
                process = await asyncio.create_subprocess_exec(
                    "git",
                    "checkout",
                    branch_name,
                    cwd=self.config.working_directory,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, stderr = await process.communicate()

                if process.returncode != 0:
                    yield ClaudeOutput(
                        type=ClaudeOutputType.ERROR,
                        content=f"Failed to checkout branch: {stderr.decode()}",
                    )
                    return

            stage.branch_name = branch_name
            self.state.current_branch = branch_name

            yield ClaudeOutput(
                type=ClaudeOutputType.STDOUT,
                content=f"On branch: {branch_name}",
            )

        except Exception as e:
            yield ClaudeOutput(
                type=ClaudeOutputType.ERROR,
                content=f"Git error: {e}",
            )

    async def _run_claude(self, prompt: str) -> AsyncGenerator[ClaudeOutput, None]:
        """Run Claude Code with a prompt.

        Args:
            prompt: The prompt to send.

        Yields:
            ClaudeOutput as execution progresses.
        """
        config = ClaudeSubprocessConfig(
            working_directory=self.config.working_directory,
        )
        self._claude = ClaudeSubprocess(config)

        try:
            async for output in self._claude.run(prompt):
                yield output
        except Exception as e:
            logger.exception("Error running Claude")
            yield ClaudeOutput(
                type=ClaudeOutputType.ERROR,
                content=f"Claude error: {e}",
            )
        finally:
            self._claude = None

    def _refresh_stages(self) -> None:
        """Refresh stage task completion status from tasks.md."""
        self.state.stages = self._parser.refresh_stages(
            self.state.stages,
            self.config.tasks_file_path,
        )

    def _extract_pr_url(self, content: str, stage: Stage) -> None:
        """Extract PR URL from output content.

        Args:
            content: The output content to search.
            stage: The stage to update with PR URL.
        """
        if "github.com" in content and "/pull/" in content:
            match = re.search(r"https://github\.com/[^\s]+/pull/\d+", content)
            if match:
                pr_url = match.group(0)
                stage.pr_url = pr_url
                self.state.pr_urls.append(pr_url)
                logger.info("PR created: %s", pr_url)

    def handle_user_approval(self, approved: bool, feedback: str | None = None) -> None:
        """Handle user's Accept/Reject decision.

        Args:
            approved: True if user accepted, False if rejected.
            feedback: Optional feedback if rejected.
        """
        self.state.awaiting_approval = False
        stage = self.state.current_stage

        if stage:
            if approved:
                logger.info("User approved Stage %d", stage.number)
                stage.phase = None  # Clear phase
            else:
                logger.info("User rejected Stage %d: %s", stage.number, feedback)
                # Reset to allow re-work
                stage.phase = StagePhase.EXECUTING
                stage.status = StageStatus.IN_PROGRESS

    def advance_to_next_stage(self) -> bool:
        """Advance to the next stage.

        Returns:
            True if advanced, False if no more stages.
        """
        result = self.state.advance_to_next_stage()
        if result:
            stage = self.state.current_stage
            logger.info(
                "Advanced to Stage %d: %s",
                stage.number if stage else 0,
                stage.name if stage else "",
            )
        else:
            logger.info("All stages complete")
        return result

    async def cancel(self) -> None:
        """Cancel current execution."""
        self._cancelled = True
        if self._claude:
            await self._claude.cancel()
        logger.info("Autopilot cancelled")

    @property
    def is_complete(self) -> bool:
        """Check if all stages are complete."""
        return self.state.is_complete

    @property
    def awaiting_approval(self) -> bool:
        """Check if waiting for user approval."""
        return self.state.awaiting_approval

    # Legacy method for compatibility
    async def run_next_stage(self) -> AsyncGenerator[ClaudeOutput, None]:
        """Legacy method - use run_stage_workflow instead."""
        async for output in self.run_stage_workflow():
            yield output
