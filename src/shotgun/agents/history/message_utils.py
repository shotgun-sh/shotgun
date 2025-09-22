"""Utility functions for working with PydanticAI messages."""

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    SystemPromptPart,
    UserPromptPart,
)


def get_first_user_request(messages: list[ModelMessage]) -> str | None:
    """Extract first user request content from messages."""
    for msg in messages:
        if isinstance(msg, ModelRequest):
            for part in msg.parts:
                if isinstance(part, UserPromptPart) and isinstance(part.content, str):
                    return part.content
    return None


def get_last_user_request(messages: list[ModelMessage]) -> ModelRequest | None:
    """Extract the last user request from messages."""
    for msg in reversed(messages):
        if isinstance(msg, ModelRequest):
            for part in msg.parts:
                if isinstance(part, UserPromptPart):
                    return msg
    return None


def get_user_content_from_request(request: ModelRequest) -> str | None:
    """Extract user prompt content from a ModelRequest."""
    for part in request.parts:
        if isinstance(part, UserPromptPart) and isinstance(part.content, str):
            return part.content
    return None


def get_system_prompt(messages: list[ModelMessage]) -> str | None:
    """Extract system prompt from messages."""
    for msg in messages:
        if isinstance(msg, ModelRequest):
            for part in msg.parts:
                if isinstance(part, SystemPromptPart):
                    return part.content
    return None
