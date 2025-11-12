"""Pydantic models for agent error handling."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AgentErrorContext(BaseModel):
    """Context information needed to classify and handle agent errors.

    Attributes:
        exception: The exception that was raised
        is_shotgun_account: Whether the user is using a Shotgun Account
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    exception: Any = Field(...)
    is_shotgun_account: bool
