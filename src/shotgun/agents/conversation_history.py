"""Models and utilities for persisting TUI conversation history."""

import json
import logging
from datetime import datetime
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai.messages import (
    ModelMessage,
    ModelMessagesTypeAdapter,
    ModelResponse,
    ToolCallPart,
)
from pydantic_core import to_jsonable_python

from shotgun.tui.screens.chat_screen.hint_message import HintMessage

__all__ = ["HintMessage", "ConversationHistory"]

logger = logging.getLogger(__name__)

SerializedMessage = dict[str, Any]


def is_tool_call_complete(tool_call: ToolCallPart) -> bool:
    """Check if a tool call has valid, complete JSON arguments.

    Args:
        tool_call: The tool call part to validate

    Returns:
        True if the tool call args are valid JSON, False otherwise
    """
    if tool_call.args is None:
        return True  # No args is valid

    if isinstance(tool_call.args, dict):
        return True  # Already parsed dict is valid

    if not isinstance(tool_call.args, str):
        return False

    # Try to parse the JSON string
    try:
        json.loads(tool_call.args)
        return True
    except (json.JSONDecodeError, ValueError) as e:
        # Log incomplete tool call detection
        args_preview = (
            tool_call.args[:100] + "..."
            if len(tool_call.args) > 100
            else tool_call.args
        )
        logger.info(
            "Detected incomplete tool call in validation",
            extra={
                "tool_name": tool_call.tool_name,
                "tool_call_id": tool_call.tool_call_id,
                "args_preview": args_preview,
                "error": str(e),
            },
        )
        return False


def filter_incomplete_messages(messages: list[ModelMessage]) -> list[ModelMessage]:
    """Filter out messages with incomplete tool calls.

    Args:
        messages: List of messages to filter

    Returns:
        List of messages with only complete tool calls
    """
    filtered: list[ModelMessage] = []
    filtered_count = 0
    filtered_tool_names: list[str] = []

    for message in messages:
        # Only check ModelResponse messages for tool calls
        if not isinstance(message, ModelResponse):
            filtered.append(message)
            continue

        # Check if any tool calls are incomplete
        has_incomplete_tool_call = False
        for part in message.parts:
            if isinstance(part, ToolCallPart) and not is_tool_call_complete(part):
                has_incomplete_tool_call = True
                filtered_tool_names.append(part.tool_name)
                break

        # Only include messages without incomplete tool calls
        if not has_incomplete_tool_call:
            filtered.append(message)
        else:
            filtered_count += 1

    # Log if any messages were filtered
    if filtered_count > 0:
        logger.info(
            "Filtered incomplete messages before saving",
            extra={
                "filtered_count": filtered_count,
                "total_messages": len(messages),
                "filtered_tool_names": filtered_tool_names,
            },
        )

    return filtered


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
        # Filter out messages with incomplete tool calls to prevent corruption
        filtered_messages = filter_incomplete_messages(messages)

        # Serialize ModelMessage list to JSON-serializable format
        self.agent_history = to_jsonable_python(
            filtered_messages, fallback=lambda x: str(x), exclude_none=True
        )

    def set_ui_messages(self, messages: list[ModelMessage | HintMessage]) -> None:
        """Set ui_history from a list of UI messages."""

        # Filter out ModelMessages with incomplete tool calls (keep all HintMessages)
        # We need to maintain message order, so we'll check each message individually
        filtered_messages: list[ModelMessage | HintMessage] = []

        for msg in messages:
            if isinstance(msg, HintMessage):
                # Always keep hint messages
                filtered_messages.append(msg)
            elif isinstance(msg, ModelResponse):
                # Check if this ModelResponse has incomplete tool calls
                has_incomplete = False
                for part in msg.parts:
                    if isinstance(part, ToolCallPart) and not is_tool_call_complete(
                        part
                    ):
                        has_incomplete = True
                        break

                if not has_incomplete:
                    filtered_messages.append(msg)
            else:
                # Keep all other ModelMessage types (ModelRequest, etc.)
                filtered_messages.append(msg)

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

        self.ui_history = [_serialize_message(msg) for msg in filtered_messages]

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
