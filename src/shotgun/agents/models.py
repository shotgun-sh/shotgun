"""Pydantic models for agent dependencies and configuration."""

import os
from asyncio import Future, Queue
from collections.abc import Callable
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai import RunContext

from .config.models import ModelConfig

if TYPE_CHECKING:
    from shotgun.artifacts.service import ArtifactService
    from shotgun.codebase.service import CodebaseService


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

    max_iterations: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of iterations for agent loops",
    )

    queue: Queue[UserQuestion] = Field(
        default_factory=Queue,
        description="Queue for storing user responses",
    )

    tasks: list[Future[UserAnswer]] = Field(
        default_factory=list,
        description="Tasks for storing deferred tool results",
    )


class FileOperationType(str, Enum):
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

    artifact_service: "ArtifactService" = Field(
        description="Artifact service for managing structured artifacts",
    )

    system_prompt_fn: Callable[[RunContext["AgentDeps"]], str] = Field(
        description="Function that generates the system prompt for this agent",
    )

    file_tracker: FileOperationTracker = Field(
        default_factory=FileOperationTracker,
        description="Tracker for file operations during agent run",
    )


# Rebuild model to resolve forward references after imports are available
try:
    from shotgun.artifacts.service import ArtifactService
    from shotgun.codebase.service import CodebaseService

    AgentDeps.model_rebuild()
except ImportError:
    # Services may not be available in all contexts
    pass
