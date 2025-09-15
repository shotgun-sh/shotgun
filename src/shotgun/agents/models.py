"""Pydantic models for agent dependencies and configuration."""

from pathlib import Path

from pydantic import BaseModel, Field

from .config.models import ModelConfig


class UIOptions(BaseModel):
    """User interface options for agents."""

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


class AgentDeps(UIOptions):
    """Dependencies passed to all agents for configuration and runtime behavior."""

    llm_model: ModelConfig = Field(
        description="Model configuration with token limits and provider info",
    )
