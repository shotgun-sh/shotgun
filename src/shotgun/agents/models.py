"""Pydantic models for agent dependencies and configuration."""

import os
from asyncio import Future, Queue
from collections.abc import Callable
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai import RunContext

from shotgun.agents.usage_manager import SessionUsageManager, get_session_usage_manager

from .config.models import ModelConfig

if TYPE_CHECKING:
    from shotgun.codebase.service import CodebaseService


class AgentResponse(BaseModel):
    """Structured response from an agent with optional clarifying questions.

    This model provides a consistent response format for all agents:
    - response: The main response text (can be empty if only asking questions)
    - clarifying_questions: Optional list of questions to ask the user

    When clarifying_questions is provided, the agent expects to receive
    answers before continuing its work. This replaces the ask_questions tool.
    """

    response: str = Field(
        description="The agent's response text. Always respond with some text summarizing what happened, whats next, etc.",
    )
    clarifying_questions: list[str] | None = Field(
        default=None,
        description="""
Optional list of clarifying questions to ask the user.
- Single question: Shown as a non-blocking suggestion (user can answer or continue with other prompts)
- Multiple questions (2+): Asked sequentially in Q&A mode (blocks input until all answered or cancelled)
""",
    )


class AgentType(StrEnum):
    """Enumeration for available agent types."""

    RESEARCH = "research"
    SPECIFY = "specify"
    PLAN = "plan"
    TASKS = "tasks"
    EXPORT = "export"


class PipelineConfigEntry(BaseModel):
    """Configuration for each agent in the pipeline.

    This model defines what files an agent can write to and what
    files from prior agents it should read for context.
    """

    own_file: str | None = Field(
        default=None,
        description="The file this agent writes to (None for export agent)",
    )
    prior_files: list[str] = Field(
        default_factory=list,
        description="Files from prior agents in pipeline to read for context",
    )


class UserAnswer(BaseModel):
    """A answer from the user."""

    answer: str = Field(
        description="The answer from the user",
    )
    tool_call_id: str = Field(
        description="Tool call id",
    )


class UserQuestion(BaseModel):
    """A question asked by the user."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    question: str = Field(
        description="The question asked by the user",
    )
    tool_call_id: str = Field(
        description="Tool call id",
    )
    result: Future[UserAnswer] = Field(
        description="Future that will contain the user's answer"
    )


class MultipleUserQuestions(BaseModel):
    """Multiple questions to ask the user sequentially."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    questions: list[str] = Field(
        description="List of questions to ask the user",
    )
    current_index: int = Field(
        default=0,
        description="Current question index being asked",
    )
    answers: list[str] = Field(
        default_factory=list,
        description="Accumulated answers from the user",
    )
    tool_call_id: str = Field(
        description="Tool call id",
    )
    result: Future[UserAnswer] = Field(
        description="Future that will contain all answers formatted as Q&A pairs"
    )


class AgentRuntimeOptions(BaseModel):
    """User interface options for agents."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    interactive_mode: bool = Field(
        default=True,
        description="Whether agents can interact with users (ask questions, etc.)",
    )

    working_directory: Path = Field(
        default_factory=lambda: Path.cwd(),
        description="Working directory for agent operations",
    )

    is_tui_context: bool = Field(
        default=False,
        description="Whether the agent is running in TUI context",
    )

    max_iterations: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of iterations for agent loops",
    )

    queue: Queue[UserQuestion | MultipleUserQuestions] = Field(
        default_factory=Queue,
        description="Queue for storing user questions (single or multiple)",
    )

    tasks: list[Future[UserAnswer]] = Field(
        default_factory=list,
        description="Tasks for storing deferred tool results",
    )

    usage_manager: SessionUsageManager = Field(
        default_factory=get_session_usage_manager,
        description="Usage manager for tracking usage",
    )


class FileOperationType(StrEnum):
    """Types of file operations that can be tracked."""

    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"


class FileOperation(BaseModel):
    """Single file operation record."""

    file_path: str = Field(
        description="Full absolute path to the file",
    )
    operation: FileOperationType = Field(
        description="Type of operation performed",
    )
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="When the operation occurred",
    )


class FileOperationTracker(BaseModel):
    """Tracks file operations during a single agent run."""

    operations: list[FileOperation] = Field(
        default_factory=list,
        description="List of file operations performed",
    )

    def add_operation(
        self, file_path: Path | str, operation: FileOperationType
    ) -> None:
        """Record a file operation.

        Args:
            file_path: Path to the file (will be converted to absolute)
            operation: Type of operation performed
        """
        # Convert to absolute path string
        if isinstance(file_path, Path):
            absolute_path = str(file_path.resolve())
        else:
            absolute_path = str(Path(file_path).resolve())

        self.operations.append(
            FileOperation(file_path=absolute_path, operation=operation)
        )

    def clear(self) -> None:
        """Clear all tracked operations for a new run."""
        self.operations = []

    def get_summary(self) -> dict[FileOperationType, list[str]]:
        """Get operations grouped by type.

        Returns:
            Dictionary mapping operation types to lists of file paths
        """
        summary: dict[FileOperationType, list[str]] = {
            FileOperationType.CREATED: [],
            FileOperationType.UPDATED: [],
            FileOperationType.DELETED: [],
        }

        for op in self.operations:
            summary[op.operation].append(op.file_path)

        # Remove duplicates while preserving order
        for op_type in summary:
            seen = set()
            unique_paths = []
            for path in summary[op_type]:
                if path not in seen:
                    seen.add(path)
                    unique_paths.append(path)
            summary[op_type] = unique_paths

        return summary

    def format_summary(self) -> str:
        """Generate human-readable summary for the user.

        Returns:
            Formatted string showing files modified during the run
        """
        if not self.operations:
            return "No files were modified during this run."

        summary = self.get_summary()
        lines = ["Files modified during this run:"]

        if summary[FileOperationType.CREATED]:
            lines.append("\nCreated:")
            for path in summary[FileOperationType.CREATED]:
                lines.append(f"  - {path}")

        if summary[FileOperationType.UPDATED]:
            lines.append("\nUpdated:")
            for path in summary[FileOperationType.UPDATED]:
                lines.append(f"  - {path}")

        if summary[FileOperationType.DELETED]:
            lines.append("\nDeleted:")
            for path in summary[FileOperationType.DELETED]:
                lines.append(f"  - {path}")

        return "\n".join(lines)

    def get_display_path(self) -> str | None:
        """Get a single file path or common parent directory for display.

        Returns:
            Path string to display, or None if no files were modified
        """
        if not self.operations:
            return None

        unique_paths = list({op.file_path for op in self.operations})

        if len(unique_paths) == 1:
            # Single file - return its path
            return unique_paths[0]

        # Multiple files - find common parent directory
        common_path = os.path.commonpath(unique_paths)
        return common_path


class AgentDeps(AgentRuntimeOptions):
    """Dependencies passed to all agents for configuration and runtime behavior."""

    llm_model: ModelConfig = Field(
        description="Model configuration with token limits and provider info",
    )

    codebase_service: "CodebaseService" = Field(
        description="Codebase service for code analysis tools",
    )

    system_prompt_fn: Callable[[RunContext["AgentDeps"]], str] = Field(
        description="Function that generates the system prompt for this agent",
    )

    file_tracker: FileOperationTracker = Field(
        default_factory=FileOperationTracker,
        description="Tracker for file operations during agent run",
    )

    agent_mode: AgentType | None = Field(
        default=None,
        description="Current agent mode for file scoping",
    )


# Rebuild model to resolve forward references after imports are available
try:
    from shotgun.codebase.service import CodebaseService

    AgentDeps.model_rebuild()
except ImportError:
    # Services may not be available in all contexts
    pass
