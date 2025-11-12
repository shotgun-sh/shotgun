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


class ErrorMessage(BaseModel):
    """Container for error message components.

    Attributes:
        message: The main error message (markdown or plain text)
        requires_email_component: Whether this error needs an email contact component
        email: Optional email address for contact (if requires_email_component is True)
        email_context: Additional context to show after email component
    """

    message: str
    requires_email_component: bool = False
    email: str | None = None
    email_context: str | None = None
