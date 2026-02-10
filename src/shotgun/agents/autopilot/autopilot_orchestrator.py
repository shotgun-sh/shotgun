"""Autopilot orchestrator for stage-based execution.

This module provides the main orchestration logic for the Autopilot agent,
managing the execution of stages with a complete workflow:
1. Execute tasks until stage is complete
2. Create PR
3. Review and fix code
4. Run QA testing
5. Present for user approval
"""

import logging
import re
from collections.abc import AsyncGenerator, Callable
from pathlib import Path

from pydantic import BaseModel, Field

from shotgun.agents.autopilot.claude_subprocess import (
    ClaudeSubprocess,
    ClaudeSubprocessConfig,
)
from shotgun.agents.autopilot.dependency_graph import (
    compute_execution_batches,
    validate_dependencies,
)
from shotgun.agents.autopilot.lightweight_parser import LightweightTasksParser
from shotgun.agents.autopilot.models import (
    AutopilotMode,
    AutopilotState,
    ClaudeOutput,
    ClaudeOutputType,
    FileStatus,
    PrerequisiteValidation,
    Stage,
    StagePhase,
    StageStatus,
)
from shotgun.agents.autopilot.prompts import (
    _ParallelStageInfo,
    render_create_pr,
    render_execute_parallel_stages,
    render_execute_stage,
    render_qa_testing,
    render_review_code,
)
from shotgun.posthog_telemetry import track_event

logger = logging.getLogger(__name__)

MAX_STAGE_ITERATIONS = 20  # Max attempts to complete a stage


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
    use_teams: bool = Field(
        default=True,
        description="Use Claude Code Teams for parallel batch execution",
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
        # LLM parser for all parsing (handles various formats flexibly)
        self._lightweight_parser = LightweightTasksParser(self.config.working_directory)
        self._claude: ClaudeSubprocess | None = None
        self._cancelled = False
        self._last_claude_output: str | None = (
            None  # Capture Claude's final output for context
        )

    def validate_prerequisites(self) -> PrerequisiteValidation:
        """Validate that required .shotgun/ files exist before starting.

        Checks for:
        - tasks.md (REQUIRED) - cannot proceed without this
        - specification.md (recommended) - specification document
        - plan.md (recommended) - implementation plan

        Returns:
            PrerequisiteValidation with status of each file.
        """
        working_dir = self.config.working_directory

        def check_file(path: str) -> FileStatus:
            """Check if a file exists and is not empty."""
            full_path = working_dir / path
            exists = full_path.exists()
            size = 0
            is_empty = True

            if exists:
                size = full_path.stat().st_size
                # Consider files with only whitespace as empty
                if size > 0:
                    content = full_path.read_text().strip()
                    is_empty = len(content) == 0

            return FileStatus(
                path=path,
                exists=exists,
                is_empty=is_empty,
                size_bytes=size,
            )

        validation = PrerequisiteValidation(
            tasks_file=check_file(self.config.tasks_file_path),
            spec_file=check_file(".shotgun/specification.md"),
            plan_file=check_file(".shotgun/plan.md"),
        )

        logger.info(
            "Prerequisite validation: can_proceed=%s, missing_required=%s, missing_recommended=%s",
            validation.can_proceed,
            validation.missing_required,
            validation.missing_recommended,
        )

        # Track validation result (no PII - just counts)
        track_event(
            "autopilot_validation",
            {
                "can_proceed": validation.can_proceed,
                "has_tasks_file": validation.tasks_file.exists
                and not validation.tasks_file.is_empty,
                "has_spec_file": validation.spec_file.exists
                and not validation.spec_file.is_empty,
                "has_plan_file": validation.plan_file.exists
                and not validation.plan_file.is_empty,
            },
        )

        return validation

    async def initialize(self) -> list[Stage]:
        """Initialize autopilot by parsing tasks.md using lightweight status parser.

        Uses fast status parser to get all stages with completion status.

        Returns:
            List of Stage objects with status.
        """
        logger.info("Initializing autopilot from %s", self.config.tasks_file_path)

        # Use lightweight status parser for fast initialization
        stages = await self._lightweight_parser.parse_status(
            self.config.tasks_file_path
        )

        if stages:
            self.state.stages = stages
            # Initialize state based on task completion - skip completed stages
            self.state.initialize_from_tasks()
            logger.info(
                "Status parser found %d stages (starting at stage %d)",
                len(stages),
                self.state.current_stage_index + 1,  # 1-indexed for display
            )
        else:
            logger.warning("No stages found in tasks.md")

        return stages

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

        # If stage has no tasks (only status from status parser), load full tasks
        if not stage.tasks:
            logger.info(
                "Stage %s has no tasks loaded, loading from tasks.md...",
                stage.number,
            )
            detailed_stage = await self._lightweight_parser.parse_single_stage(
                stage.number,
                self.config.tasks_file_path,
            )
            if detailed_stage:
                # Update stage with tasks, preserving metadata
                detailed_stage.status = stage.status
                detailed_stage.phase = stage.phase
                detailed_stage.branch_name = stage.branch_name
                detailed_stage.pr_url = stage.pr_url
                detailed_stage.iteration_count = stage.iteration_count
                self.state.stages[self.state.current_stage_index] = detailed_stage
                stage = detailed_stage
                logger.info(
                    "Loaded %d tasks for Stage %s",
                    len(stage.tasks),
                    stage.number,
                )
            else:
                yield ClaudeOutput(
                    type=ClaudeOutputType.ERROR,
                    content=f"Failed to load tasks for Stage {stage.number}",
                )
                return

        logger.info(
            "Starting workflow for Stage %s: %s (tasks: %d pending, %d completed)",
            stage.number,
            stage.name,
            len(stage.pending_tasks),
            len(stage.completed_tasks),
        )

        # Signal stage change to TUI so it can update spinner
        yield ClaudeOutput(
            type=ClaudeOutputType.STAGE_CHANGE,
            content=f"Stage {stage.number}: {stage.name}",
        )

        # Track stage start (no PII - just counts and numbers)
        track_event(
            "autopilot_stage_started",
            {
                "stage_number": stage.number,
                "total_stages": len(self.state.stages),
                "pending_tasks": len(stage.pending_tasks),
                "completed_tasks": len(stage.completed_tasks),
                "mode": self.state.mode.value,
            },
        )

        stage.status = StageStatus.IN_PROGRESS

        # Phase 1: Execute tasks until complete
        stage.phase = StagePhase.EXECUTING
        logger.info("Entering Phase 1: EXECUTING for Stage %s", stage.number)
        yield ClaudeOutput(
            type=ClaudeOutputType.STDOUT,
            content=f"📋 Phase 1: Executing tasks for Stage {stage.number}",
        )

        async for output in self._execute_until_complete(stage):
            yield output
            if self._cancelled:
                return

        # Check if stage completed successfully
        await self._refresh_stages()
        stage = self.state.current_stage
        if not stage or not stage.is_complete:
            yield ClaudeOutput(
                type=ClaudeOutputType.ERROR,
                content=f"Stage {stage.number if stage else '?'} failed to complete after {self.config.max_iterations} iterations",
            )
            if stage:
                stage.status = StageStatus.FAILED
            return

        # Cowboy mode: self-review but skip PR creation and human approval
        if self.state.mode == AutopilotMode.COWBOY:
            # Self-review phase
            stage.phase = StagePhase.REVIEWING
            logger.info("Cowboy mode: Self-reviewing Stage %s", stage.number)
            yield ClaudeOutput(
                type=ClaudeOutputType.STDOUT,
                content=f"🔍 Self-reviewing Stage {stage.number}...",
            )

            async for output in self._review_and_fix(stage):
                yield output
                if self._cancelled:
                    return

            # Mark complete and move on (no PR, no human approval)
            stage.status = StageStatus.COMPLETED
            stage.phase = None

            logger.info(
                "Stage %s complete (cowboy mode - no PR, no human review)",
                stage.number,
            )

            # Track stage completion
            track_event(
                "autopilot_stage_completed",
                {
                    "stage_number": stage.number,
                    "total_stages": len(self.state.stages),
                    "iterations_used": stage.iteration_count,
                    "has_pr": False,
                    "mode": self.state.mode.value,
                },
            )

            yield ClaudeOutput(
                type=ClaudeOutputType.STDOUT,
                content=f"✅ Stage {stage.number} complete",
            )

            # Auto-advance to next stage
            if self.advance_to_next_stage():
                yield ClaudeOutput(
                    type=ClaudeOutputType.STDOUT,
                    content=f"🤠 Moving to Stage {self.state.current_stage.number if self.state.current_stage else '?'}...",
                )
                # Recursively run the next stage
                async for output in self.run_stage_workflow():
                    yield output
            else:
                yield ClaudeOutput(
                    type=ClaudeOutputType.STDOUT,
                    content="🎉 All stages complete!",
                )
            return

        # Phase 2: Create PR
        stage.phase = StagePhase.CREATING_PR
        logger.info("Entering Phase 2: CREATING_PR for Stage %s", stage.number)
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
        logger.info("Entering Phase 3: REVIEWING for Stage %s", stage.number)
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
        logger.info("Entering Phase 4: QA_TESTING for Stage %s", stage.number)
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

        logger.info(
            "Stage %s workflow complete - entering Phase 5: AWAITING_APPROVAL (PR: %s)",
            stage.number,
            stage.pr_url or "no PR",
        )

        # Track stage completion (no PII - just counts)
        track_event(
            "autopilot_stage_completed",
            {
                "stage_number": stage.number,
                "total_stages": len(self.state.stages),
                "iterations_used": stage.iteration_count,
                "has_pr": stage.pr_url is not None,
                "mode": self.state.mode.value,
            },
        )

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
        logger.info(
            "Starting execution loop for Stage %s with %d pending tasks",
            stage.number,
            len(stage.pending_tasks),
        )

        while stage.iteration_count < self.config.max_iterations:
            if self._cancelled:
                logger.info("Execution cancelled for Stage %s", stage.number)
                return

            stage.iteration_count += 1
            remaining = len(stage.pending_tasks)

            logger.info(
                "Stage %s iteration %d/%d - %d tasks remaining: %s",
                stage.number,
                stage.iteration_count,
                self.config.max_iterations,
                remaining,
                [t.text[:50] for t in stage.pending_tasks],
            )

            yield ClaudeOutput(
                type=ClaudeOutputType.STDOUT,
                content=f"  Iteration {stage.iteration_count}: {remaining} tasks remaining",
            )

            # Build and run the prompt
            prompt = self._build_execution_prompt(stage)
            async for output in self._run_claude(prompt):
                yield output
                # Capture text output for context in task parsing
                if output.type == ClaudeOutputType.STDOUT:
                    self._last_claude_output = output.content

            # Refresh and check completion
            await self._refresh_stages()
            updated_stage = self.state.current_stage
            if updated_stage is None:
                logger.warning("Stage became None after refresh - aborting")
                return

            # Log task progress
            completed_count = len(updated_stage.completed_tasks)
            pending_count = len(updated_stage.pending_tasks)
            logger.info(
                "Stage %s after iteration %d: %d completed, %d pending",
                updated_stage.number,
                stage.iteration_count,
                completed_count,
                pending_count,
            )

            # Update the loop variable
            stage = updated_stage

            if stage.is_complete:
                logger.info(
                    "Stage %s COMPLETE after %d iteration(s)",
                    stage.number,
                    stage.iteration_count,
                )
                yield ClaudeOutput(
                    type=ClaudeOutputType.STDOUT,
                    content=f"  All tasks complete after {stage.iteration_count} iteration(s)",
                )
                return

        logger.warning(
            "Stage %s reached max iterations (%d) without completing",
            stage.number,
            self.config.max_iterations,
        )

        # Track stage failure (no PII - just counts)
        track_event(
            "autopilot_stage_failed",
            {
                "stage_number": stage.number,
                "total_stages": len(self.state.stages),
                "max_iterations": self.config.max_iterations,
                "pending_tasks": len(stage.pending_tasks),
                "completed_tasks": len(stage.completed_tasks),
                "mode": self.state.mode.value,
            },
        )

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
        branch_name = f"{self.config.branch_prefix}{stage.number}"
        prompt = render_create_pr(
            tasks_file_path=self.state.tasks_file_path,
            stage_number=stage.number,
            stage_name=stage.name,
            branch_name=branch_name,
            base_branch=self.state.base_branch,
        )
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
        prompt = render_review_code(
            tasks_file_path=self.state.tasks_file_path,
            stage_number=stage.number,
            stage_name=stage.name,
        )
        async for output in self._run_claude(prompt):
            yield output

    async def _run_qa_tests(self, stage: Stage) -> AsyncGenerator[ClaudeOutput, None]:
        """Run manual QA testing for the stage.

        Args:
            stage: The stage to test.

        Yields:
            ClaudeOutput with test progress.
        """
        prompt = render_qa_testing(
            tasks_file_path=self.state.tasks_file_path,
            stage_number=stage.number,
            stage_name=stage.name,
        )
        async for output in self._run_claude(prompt):
            yield output

    def _build_execution_prompt(self, stage: Stage) -> str:
        """Build the prompt for executing stage tasks.

        Args:
            stage: The stage to build prompt for.

        Returns:
            The formatted prompt.
        """
        pending_tasks = [task.text for task in stage.pending_tasks]

        # Determine branch names
        branch_name = f"{self.config.branch_prefix}{stage.number}"
        # For the first stage, use main base branch; otherwise, stack on previous stage
        if self.state.current_stage_index == 0:
            base_branch = self.state.base_branch
        else:
            prev_stage = self.state.stages[self.state.current_stage_index - 1]
            base_branch = f"{self.config.branch_prefix}{prev_stage.number}"

        return render_execute_stage(
            tasks_file_path=self.state.tasks_file_path,
            stage_number=stage.number,
            stage_name=stage.name,
            pending_tasks=pending_tasks,
            branch_name=branch_name,
            base_branch=base_branch,
        )

    async def _run_claude(self, prompt: str) -> AsyncGenerator[ClaudeOutput, None]:
        """Run Claude Code with a prompt.

        Args:
            prompt: The prompt to send.

        Yields:
            ClaudeOutput as execution progresses.
        """
        subprocess_config = ClaudeSubprocessConfig(
            working_directory=self.config.working_directory,
        )
        self._claude = ClaudeSubprocess(subprocess_config)

        logger.debug("Invoking Claude Code with prompt (%d chars)", len(prompt))

        try:
            async for output in self._claude.run(prompt):
                # Log significant outputs
                if output.type == ClaudeOutputType.ERROR:
                    logger.error("Claude error output: %s", output.content)
                elif output.type == ClaudeOutputType.EXIT:
                    logger.info(
                        "Claude session ended: %s (exit code: %s)",
                        output.content,
                        output.exit_code,
                    )
                yield output
        except Exception as e:
            logger.exception("Error running Claude")
            yield ClaudeOutput(
                type=ClaudeOutputType.ERROR,
                content=f"Claude error: {e}",
            )
        finally:
            self._claude = None

    async def _refresh_stages(self) -> None:
        """Refresh stage task completion status from tasks.md.

        Uses lightweight parsers:
        1. Status parser to check overall stage completion
        2. Single-stage parser to get detailed tasks for current stage
        """
        # Get current stage before refresh
        current_stage = self.state.current_stage
        if current_stage is None:
            logger.warning("No current stage to refresh")
            return

        # Parse the current stage's tasks to check completion status
        refreshed_stage = await self._lightweight_parser.parse_single_stage(
            current_stage.number,
            self.config.tasks_file_path,
        )

        if refreshed_stage:
            # Update the current stage with refreshed task data
            # Preserve metadata (status, phase, branch_name, pr_url, iteration_count)
            refreshed_stage.status = current_stage.status
            refreshed_stage.phase = current_stage.phase
            refreshed_stage.branch_name = current_stage.branch_name
            refreshed_stage.pr_url = current_stage.pr_url
            refreshed_stage.iteration_count = current_stage.iteration_count

            # Replace the stage in the list
            self.state.stages[self.state.current_stage_index] = refreshed_stage

            logger.info(
                "Refreshed Stage %s: %d/%d tasks completed",
                refreshed_stage.number,
                refreshed_stage.completed_count,
                refreshed_stage.task_count,
            )
        else:
            logger.warning("Failed to refresh stage %s", current_stage.number)

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
            # Track approval decision (no PII - no feedback content)
            track_event(
                "autopilot_stage_approval",
                {
                    "stage_number": stage.number,
                    "total_stages": len(self.state.stages),
                    "approved": approved,
                    "has_feedback": feedback is not None and len(feedback) > 0,
                    "mode": self.state.mode.value,
                },
            )

            if approved:
                logger.info("User approved Stage %s", stage.number)
                stage.phase = None  # Clear phase
            else:
                logger.info("User rejected Stage %s: %s", stage.number, feedback)
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
                "Advanced to Stage %s: %s",
                stage.number if stage else 0,
                stage.name if stage else "",
            )
        else:
            # Track autopilot completion (no PII - just counts)
            completed_stages = sum(
                1 for s in self.state.stages if s.status == StageStatus.COMPLETED
            )
            track_event(
                "autopilot_completed",
                {
                    "total_stages": len(self.state.stages),
                    "completed_stages": completed_stages,
                    "mode": self.state.mode.value,
                },
            )
            logger.info("All stages complete")
        return result

    async def run_batch_workflow(self) -> AsyncGenerator[ClaudeOutput, None]:
        """Run stages using dependency-aware batch execution.

        This is the teams-aware entry point that:
        1. Validates the dependency graph
        2. Computes execution batches from pending stages
        3. For each batch:
           - Single stage -> normal run_stage_workflow()
           - Multiple stages + use_teams -> _run_parallel_batch()
        4. After each batch, computes the next batch

        Yields:
            ClaudeOutput objects as work progresses.
        """
        # Validate dependency graph
        errors = validate_dependencies(self.state.stages)
        if errors:
            for error in errors:
                yield ClaudeOutput(
                    type=ClaudeOutputType.ERROR,
                    content=f"Dependency error ({error.error_type}): {error.details}",
                )
            yield ClaudeOutput(
                type=ClaudeOutputType.STDERR,
                content="Falling back to sequential execution due to dependency errors",
            )
            # Fall back to sequential execution
            async for output in self.run_stage_workflow():
                yield output
            return

        # Compute execution batches from pending stages
        plan = compute_execution_batches(self.state.stages)

        if not plan.batches:
            yield ClaudeOutput(
                type=ClaudeOutputType.STDOUT,
                content="No pending stages to execute",
            )
            return

        logger.info(
            "Batch workflow: %d batches, %d total stages",
            plan.total_batches,
            plan.total_stages,
        )

        # Track batch workflow start
        track_event(
            "autopilot_batch_workflow_started",
            {
                "total_batches": plan.total_batches,
                "total_stages": plan.total_stages,
                "use_teams": self.config.use_teams,
                "mode": self.state.mode.value,
            },
        )

        for batch in plan.batches:
            if self._cancelled:
                return

            yield ClaudeOutput(
                type=ClaudeOutputType.STDOUT,
                content=f"--- Batch {batch.level}: stages {', '.join(batch.stage_numbers)} ---",
            )

            if len(batch.stage_numbers) == 1 or not self.config.use_teams:
                # Single stage or teams disabled -> sequential execution
                for stage_num in batch.stage_numbers:
                    if self._cancelled:
                        return
                    # Set current stage index to this stage
                    stage_idx = next(
                        (
                            i
                            for i, s in enumerate(self.state.stages)
                            if s.number == stage_num
                        ),
                        None,
                    )
                    if stage_idx is not None:
                        self.state.current_stage_index = stage_idx
                        async for output in self.run_stage_workflow():
                            yield output
            else:
                # Multiple stages with teams enabled -> parallel execution
                async for output in self._run_parallel_batch(batch.stage_numbers):
                    yield output

    async def _run_parallel_batch(
        self, stage_numbers: list[str]
    ) -> AsyncGenerator[ClaudeOutput, None]:
        """Execute multiple stages in parallel using Claude Code Teams.

        Args:
            stage_numbers: Stage identifiers to execute in parallel.

        Yields:
            ClaudeOutput as execution progresses.
        """
        # Build stage lookup
        stage_map = {s.number: s for s in self.state.stages}
        batch_stages = [stage_map[num] for num in stage_numbers if num in stage_map]

        if not batch_stages:
            yield ClaudeOutput(
                type=ClaudeOutputType.ERROR,
                content=f"No stages found for batch: {stage_numbers}",
            )
            return

        # Load tasks for stages that don't have them
        for stage in batch_stages:
            if not stage.tasks:
                detailed = await self._lightweight_parser.parse_single_stage(
                    stage.number, self.config.tasks_file_path
                )
                if detailed:
                    idx = next(
                        i
                        for i, s in enumerate(self.state.stages)
                        if s.number == stage.number
                    )
                    detailed.status = stage.status
                    detailed.phase = stage.phase
                    detailed.branch_name = stage.branch_name
                    detailed.pr_url = stage.pr_url
                    detailed.iteration_count = stage.iteration_count
                    self.state.stages[idx] = detailed
                    stage_map[stage.number] = detailed

        # Build parallel stage info for the template
        parallel_stages = []
        for stage in batch_stages:
            stage = stage_map[stage.number]  # Re-fetch in case it was updated
            branch_name = f"{self.config.branch_prefix}{stage.number}"
            parallel_stages.append(
                _ParallelStageInfo(
                    number=stage.number,
                    name=stage.name,
                    branch_name=branch_name,
                    pending_tasks=[t.text for t in stage.pending_tasks],
                )
            )

        # Determine base branch (all stages in a batch branch from the same base)
        base_branch = self.state.base_branch

        # Render the parallel execution prompt
        prompt = render_execute_parallel_stages(
            tasks_file_path=self.state.tasks_file_path,
            stages=parallel_stages,
            base_branch=base_branch,
            batch_level=0,
        )

        # Mark all batch stages as in progress
        for stage in batch_stages:
            stage_map[stage.number].status = StageStatus.IN_PROGRESS
            stage_map[stage.number].phase = StagePhase.EXECUTING

        yield ClaudeOutput(
            type=ClaudeOutputType.STDOUT,
            content=f"Executing {len(batch_stages)} stages in parallel via Claude Code Teams",
        )

        # Track parallel batch start
        track_event(
            "autopilot_parallel_batch_started",
            {
                "batch_size": len(batch_stages),
                "stage_numbers": stage_numbers,
                "mode": self.state.mode.value,
            },
        )

        # Run Claude with teams enabled
        async for output in self._run_claude_with_teams(prompt):
            yield output

        # After parallel execution, refresh all batch stages
        for stage in batch_stages:
            refreshed = await self._lightweight_parser.parse_single_stage(
                stage.number, self.config.tasks_file_path
            )
            if refreshed:
                idx = next(
                    i
                    for i, s in enumerate(self.state.stages)
                    if s.number == stage.number
                )
                refreshed.status = self.state.stages[idx].status
                refreshed.phase = self.state.stages[idx].phase
                refreshed.branch_name = self.state.stages[idx].branch_name
                refreshed.pr_url = self.state.stages[idx].pr_url
                refreshed.iteration_count = self.state.stages[idx].iteration_count
                self.state.stages[idx] = refreshed

                if refreshed.is_complete:
                    self.state.stages[idx].status = StageStatus.COMPLETED
                    self.state.stages[idx].phase = None

        # Run post-execution workflow for each stage in the batch
        for stage_num in stage_numbers:
            if self._cancelled:
                return
            stage_idx = next(
                (i for i, s in enumerate(self.state.stages) if s.number == stage_num),
                -1,
            )
            if stage_idx >= 0:
                self.state.current_stage_index = stage_idx
                stage = self.state.stages[stage_idx]
                if stage.status == StageStatus.COMPLETED:
                    async for output in self._post_execution_workflow(stage):
                        yield output

    async def _run_claude_with_teams(
        self, prompt: str
    ) -> AsyncGenerator[ClaudeOutput, None]:
        """Run Claude Code with teams feature enabled.

        Creates a ClaudeSubprocess with the CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS
        environment variable set, and without tool restrictions (teams need
        TeamCreate, TaskCreate, SendMessage, Task, etc.).

        Args:
            prompt: The prompt to send.

        Yields:
            ClaudeOutput as execution progresses.
        """
        subprocess_config = ClaudeSubprocessConfig(
            working_directory=self.config.working_directory,
            env_vars={"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"},
        )
        self._claude = ClaudeSubprocess(subprocess_config)

        logger.info("Invoking Claude Code with teams enabled (%d chars)", len(prompt))

        try:
            async for output in self._claude.run(prompt):
                if output.type == ClaudeOutputType.ERROR:
                    logger.error("Claude teams error: %s", output.content)
                elif output.type == ClaudeOutputType.EXIT:
                    logger.info(
                        "Claude teams session ended: %s (exit code: %s)",
                        output.content,
                        output.exit_code,
                    )
                yield output
        except Exception as e:
            logger.exception("Error running Claude with teams")
            yield ClaudeOutput(
                type=ClaudeOutputType.ERROR,
                content=f"Claude teams error: {e}",
            )
        finally:
            self._claude = None

    async def _post_execution_workflow(
        self, stage: Stage
    ) -> AsyncGenerator[ClaudeOutput, None]:
        """Run the post-execution workflow for a completed stage.

        Handles PR creation, review, QA, and approval based on mode.
        Shared by both sequential and parallel execution flows.

        Args:
            stage: The completed stage.

        Yields:
            ClaudeOutput as the workflow progresses.
        """
        if self.state.mode == AutopilotMode.COWBOY:
            # Self-review only
            stage.phase = StagePhase.REVIEWING
            yield ClaudeOutput(
                type=ClaudeOutputType.STDOUT,
                content=f"Self-reviewing Stage {stage.number}...",
            )
            async for output in self._review_and_fix(stage):
                yield output
                if self._cancelled:
                    return

            stage.status = StageStatus.COMPLETED
            stage.phase = None

            track_event(
                "autopilot_stage_completed",
                {
                    "stage_number": stage.number,
                    "total_stages": len(self.state.stages),
                    "iterations_used": stage.iteration_count,
                    "has_pr": False,
                    "mode": self.state.mode.value,
                    "parallel": True,
                },
            )

            yield ClaudeOutput(
                type=ClaudeOutputType.STDOUT,
                content=f"Stage {stage.number} complete (parallel)",
            )
            return

        # Non-cowboy modes: PR creation, review, QA
        stage.phase = StagePhase.CREATING_PR
        yield ClaudeOutput(
            type=ClaudeOutputType.STDOUT,
            content=f"Creating PR for Stage {stage.number}",
        )
        async for output in self._create_pr(stage):
            yield output
            if self._cancelled:
                return

        stage.phase = StagePhase.REVIEWING
        yield ClaudeOutput(
            type=ClaudeOutputType.STDOUT,
            content=f"Reviewing Stage {stage.number}",
        )
        async for output in self._review_and_fix(stage):
            yield output
            if self._cancelled:
                return

        stage.phase = StagePhase.QA_TESTING
        yield ClaudeOutput(
            type=ClaudeOutputType.STDOUT,
            content=f"QA testing Stage {stage.number}",
        )
        async for output in self._run_qa_tests(stage):
            yield output
            if self._cancelled:
                return

        # Mark ready for approval
        stage.phase = StagePhase.AWAITING_APPROVAL
        stage.status = StageStatus.COMPLETED
        self.state.awaiting_approval = True

        track_event(
            "autopilot_stage_completed",
            {
                "stage_number": stage.number,
                "total_stages": len(self.state.stages),
                "iterations_used": stage.iteration_count,
                "has_pr": stage.pr_url is not None,
                "mode": self.state.mode.value,
                "parallel": True,
            },
        )

        yield ClaudeOutput(
            type=ClaudeOutputType.STDOUT,
            content=f"Stage {stage.number} ready for review. PR: {stage.pr_url or 'N/A'}",
        )

    async def cancel(self) -> None:
        """Cancel current execution."""
        self._cancelled = True
        if self._claude:
            await self._claude.cancel()

        # Track cancellation (no PII - just state info)
        stage = self.state.current_stage
        track_event(
            "autopilot_cancelled",
            {
                "stage_number": stage.number if stage else 0,
                "total_stages": len(self.state.stages),
                "phase": stage.phase.value if stage and stage.phase else None,
                "mode": self.state.mode.value,
            },
        )

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
