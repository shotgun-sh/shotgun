"""Pydantic models for agent error handling."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from shotgun.agents.models import AgentType


class AgentErrorContext(BaseModel):
    """Context information needed to classify and handle agent errors.

    Attributes:
        exception: The exception that was raised
        is_shotgun_account: Whether the user is using a Shotgun Account
        model_name: Name of the model being used
        agent_mode: Current agent type (research, tasks, etc.)
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    exception: Any = Field(...)
    is_shotgun_account: bool
    model_name: str
    agent_mode: AgentType
