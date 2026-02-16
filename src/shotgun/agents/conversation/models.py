"""Models for persisting TUI conversation history."""

from datetime import datetime
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai.messages import (
    ModelMessage,
    ModelMessagesTypeAdapter,
    ModelResponse,
    ToolCallPart,
)
from pydantic_core import to_jsonable_python

from shotgun.tui.screens.chat_screen.hint_message import HintMessage
from shotgun.tui.screens.chat_screen.welcome_message import WelcomeMessage

from .filters import (
    filter_binary_content,
    filter_incomplete_messages,
    filter_orphaned_tool_responses,
    is_tool_call_complete,
)

SerializedMessage = dict[str, Any]

# Mapping of custom part_kind values to their pydantic-ai base part_kind.
# Custom subclasses (e.g. SystemStatusPrompt, InternalPromptPart) override
# part_kind with values that ModelMessagesTypeAdapter doesn't recognise,
# causing deserialization to fail. Remapping before validation fixes this.
_CUSTOM_PART_KIND_MAP: dict[str, str] = {
    "system-status": "user-prompt",  # SystemStatusPrompt -> UserPromptPart
    "internal-prompt": "user-prompt",  # InternalPromptPart -> UserPromptPart
}


def _sanitize_parts(messages: list[SerializedMessage]) -> list[SerializedMessage]:
    """Remap custom part_kind values so ModelMessagesTypeAdapter can deserialize them."""
    sanitized: list[SerializedMessage] = []
    for msg in messages:
        parts = msg.get("parts")
        if not parts:
            sanitized.append(msg)
            continue
        new_parts = []
        changed = False
        for part in parts:
            pk = part.get("part_kind")
            if pk in _CUSTOM_PART_KIND_MAP:
                part = {**part, "part_kind": _CUSTOM_PART_KIND_MAP[pk]}
                changed = True
            new_parts.append(part)
        if changed:
            sanitized.append({**msg, "parts": new_parts})
        else:
            sanitized.append(msg)
    return sanitized


class FileReference(BaseModel):
    """Placeholder for binary content that was loaded from a file.

    When binary content (like PDFs, images) is loaded via file_requests,
    we store this reference instead of the actual binary data to:
    - Keep conversation.json lightweight
    - Avoid UTF-8 encoding issues with binary data
    - Allow the AI to request the file again if needed
    """

    kind: Literal["file_reference"] = "file_reference"
    file_path: str
    media_type: str
    size_bytes: int


class ConversationState(BaseModel):
    """Represents the complete state of a conversation in memory."""

    agent_messages: list[ModelMessage]
    ui_messages: list[ModelMessage | HintMessage | WelcomeMessage] = Field(
        default_factory=list
    )
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
    # Write-only debugging field: records the --spec-dir override if set (never read back)
    spec_dir_override: str | None = None
    # Write-only debugging field: records the Anthropic API tier if using an Anthropic model (never read back)
    anthropic_tier: int | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def set_agent_messages(self, messages: list[ModelMessage]) -> None:
        """Set agent_history from a list of ModelMessage objects.

        Args:
            messages: List of ModelMessage objects to serialize and store
        """
        # Replace BinaryContent with FileReference to avoid serialization issues
        filtered_messages = filter_binary_content(messages)
        # Filter out messages with incomplete tool calls to prevent corruption
        filtered_messages = filter_incomplete_messages(filtered_messages)
        # Filter out orphaned tool responses (tool responses without tool calls)
        filtered_messages = filter_orphaned_tool_responses(filtered_messages)

        # Serialize ModelMessage list to JSON-serializable format
        self.agent_history = to_jsonable_python(
            filtered_messages, fallback=lambda x: str(x), exclude_none=True
        )

    def set_ui_messages(
        self, messages: list[ModelMessage | HintMessage | WelcomeMessage]
    ) -> None:
        """Set ui_history from a list of UI messages."""
        # First pass: apply binary content filter to ModelMessages only
        # This preserves message count and order (just modifies content)
        binary_filtered: list[ModelMessage | HintMessage | WelcomeMessage] = []
        model_messages_for_filter: list[ModelMessage] = []
        model_indices: list[int] = []

        for i, msg in enumerate(messages):
            if isinstance(msg, (HintMessage, WelcomeMessage)):
                binary_filtered.append(msg)
            else:
                model_messages_for_filter.append(msg)
                model_indices.append(i)
                binary_filtered.append(msg)  # Placeholder, will be replaced

        # Apply binary content filter
        if model_messages_for_filter:
            filtered_models = filter_binary_content(model_messages_for_filter)
            # Replace the placeholders with filtered versions
            for idx, filtered_msg in zip(model_indices, filtered_models, strict=True):
                binary_filtered[idx] = filtered_msg

        # Second pass: filter out ModelMessages with incomplete tool calls
        filtered_messages: list[ModelMessage | HintMessage | WelcomeMessage] = []
        for msg in binary_filtered:
            if isinstance(msg, (HintMessage, WelcomeMessage)):
                filtered_messages.append(msg)
            elif isinstance(msg, ModelResponse):
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
                filtered_messages.append(msg)

        def _serialize_message(
            message: ModelMessage | HintMessage | WelcomeMessage,
        ) -> Any:
            if isinstance(message, WelcomeMessage):
                data = message.model_dump()
                data["message_type"] = "welcome"
                return data
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

        # Sanitize custom part_kind values before deserialization
        sanitized = _sanitize_parts(self.agent_history)
        return ModelMessagesTypeAdapter.validate_python(sanitized)

    def get_ui_messages(self) -> list[ModelMessage | HintMessage | WelcomeMessage]:
        """Get ui_history as a list of Model, hint, or welcome messages."""

        if not self.ui_history:
            # Fallback for older conversation files without UI history
            return cast(
                list[ModelMessage | HintMessage | WelcomeMessage],
                self.get_agent_messages(),
            )

        messages: list[ModelMessage | HintMessage | WelcomeMessage] = []
        for item in self.ui_history:
            message_type = item.get("message_type") if isinstance(item, dict) else None
            if message_type == "welcome":
                messages.append(WelcomeMessage.model_validate(item))
                continue
            if message_type == "hint":
                messages.append(HintMessage.model_validate(item))
                continue

            # Backwards compatibility: data may not include the type marker
            payload = item
            if isinstance(payload, dict):
                payload = {k: v for k, v in payload.items() if k != "message_type"}
            deserialized = ModelMessagesTypeAdapter.validate_python(
                _sanitize_parts([payload])
            )
            messages.append(deserialized[0])

        return messages
