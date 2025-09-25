"""Models and utilities for persisting TUI conversation history."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai.messages import (
    ModelMessage,
    ModelMessagesTypeAdapter,
)
from pydantic_core import to_jsonable_python


class ConversationState(BaseModel):
    """Represents the complete state of a conversation in memory."""

    agent_messages: list[ModelMessage]
    agent_type: str  # Will store AgentType.value

    model_config = ConfigDict(arbitrary_types_allowed=True)


class ConversationHistory(BaseModel):
    """Persistent conversation history for TUI sessions."""

    version: int = 1
    agent_history: list[dict[str, Any]] = Field(
        default_factory=list
    )  # Will store serialized ModelMessage objects
    last_agent_model: str = "research"
    updated_at: datetime = Field(default_factory=datetime.now)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def set_agent_messages(self, messages: list[ModelMessage]) -> None:
        """Set agent_history from a list of ModelMessage objects.

        Args:
            messages: List of ModelMessage objects to serialize and store
        """
        # Serialize ModelMessage list to JSON-serializable format
        self.agent_history = to_jsonable_python(
            messages, fallback=lambda x: str(x), exclude_none=True
        )

    def get_agent_messages(self) -> list[ModelMessage]:
        """Get agent_history as a list of ModelMessage objects.

        Returns:
            List of deserialized ModelMessage objects
        """
        if not self.agent_history:
            return []

        # Deserialize from JSON format back to ModelMessage objects
        return ModelMessagesTypeAdapter.validate_python(self.agent_history)
