"""Lightweight LLM parsers for fast autopilot startup and stage status checks.

This module provides optimized parsers that extract minimal data for performance:
- Status parser: Gets stage names and completion status only (fast initial load)
- Single-stage parser: Gets detailed tasks for one specific stage only
"""

import logging
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from shotgun.agents.autopilot.models import Stage, StageStatus, Task
from shotgun.agents.config import get_provider_model

logger = logging.getLogger(__name__)


class StageCompletionStatus(StrEnum):
    """Simple completion status for a stage."""

    NOT_STARTED = "not_started"  # No tasks completed
    IN_PROGRESS = "in_progress"  # Some tasks completed
    COMPLETED = "completed"  # All tasks completed


class ParsedStageStatus(BaseModel):
    """Stage with simple status (for fast parsing)."""

    number: str = Field(description="Stage identifier (1, 2, A, 1a, etc)")
    name: str = Field(description="Stage name")
    status: StageCompletionStatus = Field(
        description="not_started if no tasks done, in_progress if some done, completed if all done"
    )
    total_tasks: int = Field(description="Total number of tasks in this stage")
    completed_tasks: int = Field(
        description="Number of completed tasks (checkboxes with [x] or [X])"
    )


class ParsedStagesStatus(BaseModel):
    """Lightweight parsing output - just stage statuses."""

    stages: list[ParsedStageStatus] = Field(description="All stages with status")


class ParsedTaskSimple(BaseModel):
    """A parsed task for single-stage parsing."""

    text: str = Field(description="Task description text")
    completed: bool = Field(description="Whether task is marked complete")


class ParsedSingleStage(BaseModel):
    """Detailed parse of a single stage."""

    number: str = Field(description="Stage identifier")
    name: str = Field(description="Stage name")
    tasks: list[ParsedTaskSimple] = Field(description="All tasks in this stage")


STATUS_PARSER_PROMPT = """You are a markdown parser that extracts stage information from a tasks.md file.

Your job is to:
1. Find all stages (marked with ## Stage N: or ### Stage N: headers)
2. For each stage, count total tasks and completed tasks
3. Determine the stage status based on task completion
4. Return the stage number, name, status, and task counts

Rules:
- Stage headers contain "Stage" followed by an identifier and name
- Tasks are checkboxes: - [ ] (incomplete) or - [x]/- [X] (complete)
- Count ALL checkbox tasks under each stage (until the next stage header)
- Status determination:
  * "not_started" if ALL tasks are incomplete (all [ ])
  * "in_progress" if SOME tasks are complete (mix of [x] and [ ])
  * "completed" if ALL tasks are complete (all [x])
- Be precise with task counts and status determination
- Preserve exact stage identifiers (can be numeric or alphanumeric)"""

SINGLE_STAGE_PARSER_PROMPT = """You are a markdown parser that extracts tasks from a SINGLE stage in a tasks.md file.

Your job is to:
1. Find the specified stage in the document
2. Extract ALL tasks (checkboxes) under that stage only
3. Return the stage info and its tasks

Rules:
- Stage headers contain "Stage" followed by an identifier and name
- Tasks are checkboxes: - [ ] (incomplete) or - [x]/- [X] (complete)
- Only extract tasks that belong to the specified stage
- Stop when you reach the next stage header
- Preserve exact task text after the checkbox
- Be precise and extract all tasks for the specified stage"""


class LightweightTasksParser:
    """Fast LLM parsers for autopilot startup and stage-by-stage execution."""

    def __init__(self, working_directory: Path | None = None):
        """Initialize the lightweight parsers.

        Args:
            working_directory: Base directory for resolving relative paths.
        """
        self.working_directory = working_directory or Path.cwd()
        self._status_agent: Agent[None, ParsedStagesStatus] | None = None
        self._single_stage_agent: Agent[None, ParsedSingleStage] | None = None

    async def _get_status_agent(self) -> Agent[None, ParsedStagesStatus]:
        """Get or create the status parsing agent."""
        if self._status_agent is not None:
            return self._status_agent

        model_config = await get_provider_model(for_sub_agent=True)
        logger.debug("Status parser using model: %s", model_config.name)

        self._status_agent = Agent(
            model_config.model_instance,
            output_type=ParsedStagesStatus,
            system_prompt=STATUS_PARSER_PROMPT,
            retries=2,
        )

        return self._status_agent

    async def _get_single_stage_agent(self) -> Agent[None, ParsedSingleStage]:
        """Get or create the single-stage parsing agent."""
        if self._single_stage_agent is not None:
            return self._single_stage_agent

        model_config = await get_provider_model(for_sub_agent=True)
        logger.debug("Single-stage parser using model: %s", model_config.name)

        self._single_stage_agent = Agent(
            model_config.model_instance,
            output_type=ParsedSingleStage,
            system_prompt=SINGLE_STAGE_PARSER_PROMPT,
            retries=2,
        )

        return self._single_stage_agent

    async def parse_status(
        self, file_path: str | Path = ".shotgun/tasks.md"
    ) -> list[Stage]:
        """Parse tasks.md to get stage names and completion status only.

        This is fast (~4-5 seconds) and used for:
        - Initial autopilot modal display
        - Finding the next incomplete stage

        Args:
            file_path: Path to the tasks.md file.

        Returns:
            List of Stage objects with minimal data (no individual tasks).
        """
        # Resolve file path
        if isinstance(file_path, str):
            file_path = Path(file_path)

        if not file_path.is_absolute():
            file_path = self.working_directory / file_path

        if not file_path.exists():
            logger.error("tasks.md not found at %s", file_path)
            return []

        content = file_path.read_text(encoding="utf-8")

        # Parse with status agent
        agent = await self._get_status_agent()
        result = await agent.run(
            f"Parse the following tasks.md file and extract stage statuses:\n\n{content}"
        )

        # Convert to Stage objects
        stages: list[Stage] = []
        for parsed_stage in result.output.stages:
            # Convert status enum to StageStatus
            if parsed_stage.status == StageCompletionStatus.COMPLETED:
                stage_status = StageStatus.COMPLETED
            elif parsed_stage.status == StageCompletionStatus.IN_PROGRESS:
                stage_status = StageStatus.IN_PROGRESS
            else:
                stage_status = StageStatus.PENDING

            stage = Stage(
                number=parsed_stage.number,
                name=parsed_stage.name,
                tasks=[],  # No individual tasks in status parse
                status=stage_status,
                task_count_override=parsed_stage.total_tasks,
                completed_count_override=parsed_stage.completed_tasks,
            )
            stages.append(stage)

        logger.info(
            "Status parser found %d stages (%d completed, %d in progress, %d pending)",
            len(stages),
            sum(1 for s in stages if s.status == StageStatus.COMPLETED),
            sum(1 for s in stages if s.status == StageStatus.IN_PROGRESS),
            sum(1 for s in stages if s.status == StageStatus.PENDING),
        )

        return stages

    async def parse_single_stage(
        self,
        stage_number: str,
        file_path: str | Path = ".shotgun/tasks.md",
    ) -> Stage | None:
        """Parse tasks.md to get detailed tasks for ONE specific stage only.

        This is fast (~2-3 seconds) and used when executing a specific stage.

        Args:
            stage_number: The stage identifier to parse (e.g., "1", "2", "3a").
            file_path: Path to the tasks.md file.

        Returns:
            Stage object with full task details, or None if stage not found.
        """
        # Resolve file path
        if isinstance(file_path, str):
            file_path = Path(file_path)

        if not file_path.is_absolute():
            file_path = self.working_directory / file_path

        if not file_path.exists():
            logger.error("tasks.md not found at %s", file_path)
            return None

        content = file_path.read_text(encoding="utf-8")

        # Parse with single-stage agent
        agent = await self._get_single_stage_agent()
        result = await agent.run(
            f"Extract all tasks from Stage {stage_number} in the following tasks.md file:\n\n{content}"
        )

        parsed = result.output

        # Convert to Stage object
        tasks = [
            Task(text=t.text, completed=t.completed, line_number=0)
            for t in parsed.tasks
        ]

        stage = Stage(
            number=parsed.number,
            name=parsed.name,
            tasks=tasks,
            status=StageStatus.PENDING,
        )

        logger.info(
            "Single-stage parser extracted Stage %s: %s (%d tasks, %d completed)",
            stage.number,
            stage.name,
            len(tasks),
            sum(1 for t in tasks if t.completed),
        )

        return stage
