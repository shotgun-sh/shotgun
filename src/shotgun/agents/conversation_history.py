"""Models and utilities for persisting TUI conversation history."""

from datetime import datetime
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai.messages import (
    ModelMessage,
    ModelMessagesTypeAdapter,
)
from pydantic_core import to_jsonable_python

from shotgun.tui.screens.chat_screen.hint_message import HintMessage

SerializedMessage = dict[str, Any]


class ConversationState(BaseModel):
    """Represents the complete state of a conversation in memory."""

    agent_messages: list[ModelMessage]
    ui_messages: list[ModelMessage | HintMessage] = Field(default_factory=list)
    agent_type: str  # Will store AgentType.value

    model_config = ConfigDict(arbitrary_types_allowed=True)


class ConversationHistory(BaseModel):
    """Persistent conversation history for TUI sessions."""

    version: int = 1
    agent_history: list[SerializedMessage] = Field(
        default_factory=list
    )  # Stores serialized ModelMessage objects
    ui_history: list[SerializedMessage] = Field(
        default_factory=list
    )  # Stores serialized ModelMessage and HintMessage objects
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

    def set_ui_messages(self, messages: list[ModelMessage | HintMessage]) -> None:
        """Set ui_history from a list of UI messages."""

        def _serialize_message(
            message: ModelMessage | HintMessage,
        ) -> Any:
            if isinstance(message, HintMessage):
                data = message.model_dump()
                data["message_type"] = "hint"
                return data
            payload = to_jsonable_python(
                message, fallback=lambda x: str(x), exclude_none=True
            )
            if isinstance(payload, dict):
                payload.setdefault("message_type", "model")
            return payload

        self.ui_history = [_serialize_message(msg) for msg in messages]

    def get_agent_messages(self) -> list[ModelMessage]:
        """Get agent_history as a list of ModelMessage objects.

        Returns:
            List of deserialized ModelMessage objects
        """
        if not self.agent_history:
            return []

        # Deserialize from JSON format back to ModelMessage objects
        return ModelMessagesTypeAdapter.validate_python(self.agent_history)

    def get_ui_messages(self) -> list[ModelMessage | HintMessage]:
        """Get ui_history as a list of Model or hint messages."""

        if not self.ui_history:
            # Fallback for older conversation files without UI history
            return cast(list[ModelMessage | HintMessage], self.get_agent_messages())

        messages: list[ModelMessage | HintMessage] = []
        for item in self.ui_history:
            message_type = item.get("message_type") if isinstance(item, dict) else None
            if message_type == "hint":
                messages.append(HintMessage.model_validate(item))
                continue

            # Backwards compatibility: data may not include the type marker
            payload = item
            if isinstance(payload, dict):
                payload = {k: v for k, v in payload.items() if k != "message_type"}
            deserialized = ModelMessagesTypeAdapter.validate_python([payload])
            messages.append(deserialized[0])

        return messages
