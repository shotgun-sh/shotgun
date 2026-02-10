"""Parser for .shotgun/tasks.md files.

This module parses the tasks.md file to extract stages and tasks
for the Autopilot agent to execute.

Expected format:
    ### Stage 1: Stage Name
    - [ ] Task description
    - [x] Completed task
    - [ ] Another task

    ### Stage 2: Another Stage
    - [ ] Task in stage 2
"""

import logging
import re
from pathlib import Path

from pydantic import BaseModel, Field

from shotgun.agents.autopilot.models import Stage, Task

logger = logging.getLogger(__name__)


def merge_stages_with_parsed_tasks(
    state_stages: list[Stage],
    parsed_stages: list[Stage],
) -> list[Stage]:
    """Merge parsed stages with existing state stages, preserving metadata.

    This utility function is used by the LLM parser to update
    task completion status while preserving stage metadata (status, phase,
    branch_name, pr_url, iteration_count).

    Args:
        state_stages: Existing stages from AutopilotState with metadata.
        parsed_stages: Freshly parsed stages with updated task completion.

    Returns:
        Updated list of stages with refreshed tasks but preserved metadata.
    """
    # Create a map of stage number to parsed stage for lookup
    parsed_stage_map = {stage.number: stage for stage in parsed_stages}

    # Update each existing stage with new task completion status
    updated_stages: list[Stage] = []
    for state_stage in state_stages:
        if state_stage.number in parsed_stage_map:
            parsed_stage = parsed_stage_map[state_stage.number]

            # Use the parsed tasks - they have the current completion status
            updated_tasks = parsed_stage.tasks.copy()

            # Log completion status
            completed = sum(1 for t in updated_tasks if t.completed)
            logger.info(
                "Stage %s refresh: %d/%d tasks completed",
                state_stage.number,
                completed,
                len(updated_tasks),
            )

            # Create updated stage preserving metadata
            # Use parsed depends_on if available, fall back to existing
            depends_on = (
                parsed_stage.depends_on
                if parsed_stage.depends_on is not None
                else state_stage.depends_on
            )
            updated_stage = Stage(
                number=state_stage.number,
                name=state_stage.name,
                depends_on=depends_on,
                tasks=updated_tasks,
                status=state_stage.status,
                phase=state_stage.phase,
                branch_name=state_stage.branch_name,
                pr_url=state_stage.pr_url,
                iteration_count=state_stage.iteration_count,
            )
            updated_stages.append(updated_stage)
        else:
            logger.warning(
                "Stage %s not found in parsed file, keeping original",
                state_stage.number,
            )
            updated_stages.append(state_stage)

    return updated_stages


class ParsedTasksFile(BaseModel):
    """Result of parsing a tasks.md file."""

    stages: list[Stage] = Field(
        default_factory=list, description="All stages parsed from the file"
    )
    file_path: str = Field(description="Path to the parsed file")
    parse_errors: list[str] = Field(
        default_factory=list, description="Any errors encountered during parsing"
    )

    @property
    def total_tasks(self) -> int:
        """Total number of tasks across all stages."""
        return sum(stage.task_count for stage in self.stages)

    @property
    def completed_tasks(self) -> int:
        """Total number of completed tasks across all stages."""
        return sum(stage.completed_count for stage in self.stages)

    @property
    def is_valid(self) -> bool:
        """Check if the file was parsed successfully with at least one stage."""
        return len(self.stages) > 0 and len(self.parse_errors) == 0


class TasksParser:
    """Parser for .shotgun/tasks.md files.

    Parses stage headers and task checkboxes from markdown files.
    """

    # Regex patterns for parsing
    STAGE_PATTERN = re.compile(
        r"^###\s+Stage\s+([A-Za-z0-9]+)\s*:\s*(.+)$", re.IGNORECASE | re.MULTILINE
    )
    TASK_PATTERN = re.compile(r"^-\s*\[([ xX])\]\s*(.+)$", re.MULTILINE)
    DEPENDS_ON_PATTERN = re.compile(
        r"^(?:#+\s*)?Depends\s+on\s*:\s*(.+)$", re.IGNORECASE
    )

    def __init__(self, working_directory: Path | None = None):
        """Initialize the parser.

        Args:
            working_directory: Base directory for resolving relative paths.
                Defaults to current working directory.
        """
        self.working_directory = working_directory or Path.cwd()

    def parse(self, file_path: str | Path = ".shotgun/tasks.md") -> ParsedTasksFile:
        """Parse a tasks.md file.

        Args:
            file_path: Path to the tasks.md file (relative or absolute).

        Returns:
            ParsedTasksFile with stages and any parse errors.
        """
        # Resolve the file path
        if isinstance(file_path, str):
            file_path = Path(file_path)

        if not file_path.is_absolute():
            file_path = self.working_directory / file_path

        result = ParsedTasksFile(file_path=str(file_path))

        # Check if file exists
        if not file_path.exists():
            result.parse_errors.append(f"File not found: {file_path}")
            return result

        # Read the file content
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            result.parse_errors.append(f"Error reading file: {e}")
            return result

        # Parse stages and tasks
        result.stages = self._parse_content(content, result.parse_errors)
        return result

    def parse_content(self, content: str) -> ParsedTasksFile:
        """Parse tasks.md content directly (for testing).

        Args:
            content: The markdown content to parse.

        Returns:
            ParsedTasksFile with stages and any parse errors.
        """
        result = ParsedTasksFile(file_path="<string>")
        result.stages = self._parse_content(content, result.parse_errors)
        return result

    @staticmethod
    def _parse_depends_on(value: str) -> list[str]:
        """Parse a 'Depends on:' value into a list of stage identifiers.

        Handles formats like:
            "Stage 1, Stage 2"
            "Stage 1, Stage 3"
            "1, 2"
            "None"

        Args:
            value: The raw text after "Depends on:".

        Returns:
            List of stage identifier strings (e.g. ["1", "2"]).
        """
        value = value.strip()
        if not value or value.lower() == "none":
            return []

        parts = [p.strip() for p in value.split(",")]
        identifiers: list[str] = []
        for part in parts:
            # Strip "Stage " prefix if present
            cleaned = re.sub(r"(?i)^stage\s+", "", part).strip()
            if cleaned:
                identifiers.append(cleaned)
        return identifiers

    def _parse_content(self, content: str, errors: list[str]) -> list[Stage]:
        """Parse the content and extract stages with tasks.

        Args:
            content: The file content to parse.
            errors: List to append any parse errors to.

        Returns:
            List of parsed Stage objects.
        """
        stages: list[Stage] = []
        lines = content.split("\n")

        current_stage: Stage | None = None

        for line_num, line in enumerate(lines, start=1):
            # Check for stage header
            stage_match = self.STAGE_PATTERN.match(line.strip())
            if stage_match:
                # Save the previous stage if exists
                if current_stage is not None:
                    stages.append(current_stage)

                # Start a new stage
                stage_number = stage_match.group(
                    1
                )  # Keep as string for alphanumeric support
                stage_name = stage_match.group(2).strip()

                current_stage = Stage(number=stage_number, name=stage_name)
                continue

            # Check for depends_on line (only valid right after a stage header, before tasks)
            if current_stage is not None and not current_stage.tasks:
                depends_match = self.DEPENDS_ON_PATTERN.match(line.strip())
                if depends_match:
                    current_stage.depends_on = self._parse_depends_on(
                        depends_match.group(1)
                    )
                    continue

            # Check for task checkbox
            task_match = self.TASK_PATTERN.match(line.strip())
            if task_match:
                if current_stage is None:
                    errors.append(f"Line {line_num}: Task found outside of a stage")
                    continue

                checkbox = task_match.group(1)
                task_text = task_match.group(2).strip()
                completed = checkbox.lower() == "x"

                task = Task(
                    text=task_text,
                    completed=completed,
                    line_number=line_num,
                )
                current_stage.tasks.append(task)

        # Don't forget the last stage
        if current_stage is not None:
            stages.append(current_stage)

        # Validate we have stages
        if not stages:
            errors.append("No stages found. Expected format: ### Stage N: Stage Name")

        # Warn about empty stages
        for stage in stages:
            if not stage.tasks:
                errors.append(f"Stage {stage.number} ({stage.name}) has no tasks")

        return stages

    def refresh_stages(
        self, state_stages: list[Stage], file_path: str | Path = ".shotgun/tasks.md"
    ) -> list[Stage]:
        """Re-parse the file and update task completion status in existing stages.

        This is used after Claude Code runs to verify which tasks were completed.
        Preserves stage status and other metadata from state_stages.

        Args:
            state_stages: Existing stages from AutopilotState.
            file_path: Path to the tasks.md file.

        Returns:
            Updated list of stages with refreshed task completion status.
        """
        parsed = self.parse(file_path)

        logger.info(
            "Refreshing stages from %s - parsed valid=%s, stages=%d",
            file_path,
            parsed.is_valid,
            len(parsed.stages),
        )

        if not parsed.is_valid:
            logger.warning(
                "Refresh parsing failed, keeping original stages: %s",
                parsed.parse_errors,
            )
            return state_stages

        return merge_stages_with_parsed_tasks(state_stages, parsed.stages)
