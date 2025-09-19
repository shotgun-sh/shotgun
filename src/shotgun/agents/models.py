"""Pydantic models for agent dependencies and configuration."""

from asyncio import Future, Queue
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai import RunContext

from .config.models import ModelConfig

if TYPE_CHECKING:
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


# Rebuild model to resolve forward references after imports are available
try:
    from shotgun.codebase.service import CodebaseService

    AgentDeps.model_rebuild()
except ImportError:
    # CodebaseService may not be available in all contexts
    pass
