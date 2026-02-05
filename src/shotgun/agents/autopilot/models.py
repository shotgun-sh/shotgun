"""Data models for the Autopilot agent.

These models define the state and structures used by the Autopilot
agent to orchestrate stage-based execution of tasks.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class AutopilotMode(StrEnum):
    """Execution modes for Autopilot."""

    PAUSE_BETWEEN = "pause_between"  # Stop after each stage for user approval
    AUTO_CONTINUE = "auto_continue"  # Create stacked PRs without pausing


class StageStatus(StrEnum):
    """Status of a stage in the execution plan."""

    PENDING = "pending"  # Not yet started
    IN_PROGRESS = "in_progress"  # Currently executing
    COMPLETED = "completed"  # Successfully completed
    FAILED = "failed"  # Execution failed
    SKIPPED = "skipped"  # Skipped by user


class StagePhase(StrEnum):
    """Current phase within a stage's execution workflow."""

    EXECUTING = "executing"  # Running tasks
    CREATING_PR = "creating_pr"  # Creating the PR
    REVIEWING = "reviewing"  # Reviewing code and making fixes
    QA_TESTING = "qa_testing"  # Running manual QA tests
    AWAITING_APPROVAL = "awaiting_approval"  # Waiting for user Accept/Reject


class Task(BaseModel):
    """A single task within a stage.

    Tasks are parsed from checkbox lines in tasks.md:
    - [ ] Task description (incomplete)
    - [x] Task description (completed)
    """

    text: str = Field(description="The task description text")
    completed: bool = Field(
        default=False, description="Whether the task is marked complete"
    )
    line_number: int = Field(description="Line number in tasks.md for this task")


class Stage(BaseModel):
    """A stage containing multiple tasks.

    Stages are parsed from ### Stage N: Name headings in tasks.md.
    """

    number: int = Field(description="Stage number (1-indexed)")
    name: str = Field(description="Stage name/title")
    tasks: list[Task] = Field(
        default_factory=list, description="List of tasks in this stage"
    )
    status: StageStatus = Field(
        default=StageStatus.PENDING, description="Current status of this stage"
    )
    phase: StagePhase | None = Field(
        default=None, description="Current phase in the stage workflow"
    )
    branch_name: str | None = Field(
        default=None, description="Git branch created for this stage"
    )
    pr_url: str | None = Field(
        default=None, description="URL of the PR created for this stage"
    )
    iteration_count: int = Field(
        default=0, description="Number of execution iterations for this stage"
    )

    @property
    def pending_tasks(self) -> list[Task]:
        """Get tasks that haven't been completed."""
        return [task for task in self.tasks if not task.completed]

    @property
    def completed_tasks(self) -> list[Task]:
        """Get tasks that have been completed."""
        return [task for task in self.tasks if task.completed]

    @property
    def is_complete(self) -> bool:
        """Check if all tasks in this stage are complete."""
        return all(task.completed for task in self.tasks) if self.tasks else False

    @property
    def task_count(self) -> int:
        """Total number of tasks in this stage."""
        return len(self.tasks)

    @property
    def completed_count(self) -> int:
        """Number of completed tasks."""
        return len(self.completed_tasks)

    def format_task_list(self) -> str:
        """Format tasks as a bullet list for prompting Claude."""
        lines = []
        for task in self.tasks:
            marker = "[x]" if task.completed else "[ ]"
            lines.append(f"- {marker} {task.text}")
        return "\n".join(lines)


class AutopilotState(BaseModel):
    """Complete state of the Autopilot execution.

    This model tracks the full execution state including mode,
    current progress, and all stage information.
    """

    mode: AutopilotMode = Field(
        default=AutopilotMode.PAUSE_BETWEEN,
        description="Execution mode (pause or auto-continue)",
    )
    current_stage_index: int = Field(
        default=0, description="Index of the currently executing stage (0-indexed)"
    )
    stages: list[Stage] = Field(
        default_factory=list, description="All stages parsed from tasks.md"
    )
    base_branch: str = Field(
        default="main", description="Base branch to create stage branches from"
    )
    current_branch: str | None = Field(
        default=None, description="Currently checked out branch"
    )
    pr_urls: list[str] = Field(
        default_factory=list, description="URLs of all PRs created"
    )
    awaiting_approval: bool = Field(
        default=False, description="Whether we're waiting for user approval"
    )
    started_at: datetime | None = Field(
        default=None, description="When autopilot execution started"
    )
    tasks_file_path: str = Field(
        default=".shotgun/tasks.md", description="Path to the tasks.md file"
    )

    @property
    def current_stage(self) -> Stage | None:
        """Get the current stage being executed."""
        if 0 <= self.current_stage_index < len(self.stages):
            return self.stages[self.current_stage_index]
        return None

    @property
    def next_stage(self) -> Stage | None:
        """Get the next stage to execute."""
        next_idx = self.current_stage_index + 1
        if next_idx < len(self.stages):
            return self.stages[next_idx]
        return None

    @property
    def is_complete(self) -> bool:
        """Check if all stages are complete."""
        return (
            all(stage.status == StageStatus.COMPLETED for stage in self.stages)
            if self.stages
            else False
        )

    @property
    def pending_stages(self) -> list[Stage]:
        """Get stages that haven't been completed."""
        return [
            stage
            for stage in self.stages
            if stage.status not in (StageStatus.COMPLETED, StageStatus.SKIPPED)
        ]

    def advance_to_next_stage(self) -> bool:
        """Advance to the next stage.

        Returns:
            True if advanced successfully, False if no more stages.
        """
        if self.current_stage_index + 1 < len(self.stages):
            self.current_stage_index += 1
            return True
        return False

    def format_stages_summary(self) -> str:
        """Format all stages for display."""
        lines = []
        for i, stage in enumerate(self.stages):
            status_icon = {
                StageStatus.PENDING: "⬜",
                StageStatus.IN_PROGRESS: "🔄",
                StageStatus.COMPLETED: "✅",
                StageStatus.FAILED: "❌",
                StageStatus.SKIPPED: "⏭️",
            }.get(stage.status, "⬜")
            current = " ◀" if i == self.current_stage_index else ""
            lines.append(
                f"{status_icon} Stage {stage.number}: {stage.name} "
                f"({stage.completed_count}/{stage.task_count} tasks){current}"
            )
        return "\n".join(lines)


class FileStatus(BaseModel):
    """Status of a prerequisite file."""

    path: str = Field(description="Path to the file")
    exists: bool = Field(description="Whether the file exists")
    is_empty: bool = Field(default=True, description="Whether the file is empty or missing")
    size_bytes: int = Field(default=0, description="File size in bytes")


class PrerequisiteValidation(BaseModel):
    """Result of validating autopilot prerequisites.

    Checks that required .shotgun/ files exist before starting autopilot.
    """

    tasks_file: FileStatus = Field(description="Status of tasks.md (REQUIRED)")
    spec_file: FileStatus = Field(description="Status of specification.md (recommended)")
    plan_file: FileStatus = Field(description="Status of plan.md (recommended)")

    @property
    def can_proceed(self) -> bool:
        """Check if we have the minimum required files to proceed.

        tasks.md is required. specification.md and plan.md are recommended but optional.
        """
        return self.tasks_file.exists and not self.tasks_file.is_empty

    @property
    def missing_required(self) -> list[str]:
        """Get list of missing required files."""
        missing = []
        if not self.tasks_file.exists:
            missing.append(self.tasks_file.path)
        elif self.tasks_file.is_empty:
            missing.append(f"{self.tasks_file.path} (empty)")
        return missing

    @property
    def missing_recommended(self) -> list[str]:
        """Get list of missing recommended files."""
        missing = []
        if not self.spec_file.exists or self.spec_file.is_empty:
            missing.append(self.spec_file.path)
        if not self.plan_file.exists or self.plan_file.is_empty:
            missing.append(self.plan_file.path)
        return missing

    def format_status(self) -> str:
        """Format the validation status for display."""
        lines = []

        # Tasks file (required)
        if self.tasks_file.exists and not self.tasks_file.is_empty:
            lines.append(f"✅ {self.tasks_file.path}")
        elif self.tasks_file.exists:
            lines.append(f"❌ {self.tasks_file.path} (empty)")
        else:
            lines.append(f"❌ {self.tasks_file.path} (missing)")

        # Spec file (recommended)
        if self.spec_file.exists and not self.spec_file.is_empty:
            lines.append(f"✅ {self.spec_file.path}")
        elif self.spec_file.exists:
            lines.append(f"⚠️  {self.spec_file.path} (empty)")
        else:
            lines.append(f"⚠️  {self.spec_file.path} (missing)")

        # Plan file (recommended)
        if self.plan_file.exists and not self.plan_file.is_empty:
            lines.append(f"✅ {self.plan_file.path}")
        elif self.plan_file.exists:
            lines.append(f"⚠️  {self.plan_file.path} (empty)")
        else:
            lines.append(f"⚠️  {self.plan_file.path} (missing)")

        return "\n".join(lines)


class ClaudeOutputType(StrEnum):
    """Types of output from Claude Code subprocess."""

    STDOUT = "stdout"
    STDERR = "stderr"
    EXIT = "exit"
    ERROR = "error"


class ClaudeOutput(BaseModel):
    """Output from the Claude Code subprocess.

    Used for streaming Claude Code output to the TUI.
    """

    type: ClaudeOutputType = Field(description="Type of output")
    content: str = Field(description="The output content")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="When this output was received"
    )
    exit_code: int | None = Field(default=None, description="Exit code if type is EXIT")


# LLM Parser models (used for structured output parsing of tasks.md)


class ParsedTask(BaseModel):
    """A parsed task from the markdown file (LLM parser output)."""

    text: str = Field(description="The task description text")
    completed: bool = Field(
        description="Whether the task is marked complete ([x] or [X])"
    )


class ParsedStage(BaseModel):
    """A parsed stage from the markdown file (LLM parser output)."""

    number: int = Field(description="Stage number (e.g., 1, 2, 3)")
    name: str = Field(description="Stage name/title")
    tasks: list[ParsedTask] = Field(description="List of tasks in this stage")


class ParsedTasksOutput(BaseModel):
    """Structured output from the LLM parser."""

    stages: list[ParsedStage] = Field(
        description="All stages found in the file, in order"
    )
