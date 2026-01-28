"""Filter functions for conversation message validation."""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any

from pydantic_ai import BinaryContent
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelRequestPart,
    ModelResponse,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pydantic_ai.messages import UserContent

logger = logging.getLogger(__name__)


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


def filter_orphaned_tool_responses(messages: list[ModelMessage]) -> list[ModelMessage]:
    """Filter out tool responses without corresponding tool calls.

    This ensures message history is valid for OpenAI API which requires
    tool responses to follow their corresponding tool calls.

    Args:
        messages: List of messages to filter

    Returns:
        List of messages with orphaned tool responses removed
    """
    # Collect all tool_call_ids from ToolCallPart in ModelResponse
    valid_tool_call_ids: set[str] = set()
    for msg in messages:
        if isinstance(msg, ModelResponse):
            for part in msg.parts:
                if isinstance(part, ToolCallPart) and part.tool_call_id:
                    valid_tool_call_ids.add(part.tool_call_id)

    # Filter out orphaned ToolReturnPart from ModelRequest
    filtered: list[ModelMessage] = []
    orphaned_count = 0
    orphaned_tool_names: list[str] = []

    for msg in messages:
        if isinstance(msg, ModelRequest):
            # Filter parts, removing orphaned ToolReturnPart
            filtered_parts: list[ModelRequestPart] = []
            request_part: ModelRequestPart
            for request_part in msg.parts:
                if isinstance(request_part, ToolReturnPart):
                    if request_part.tool_call_id in valid_tool_call_ids:
                        filtered_parts.append(request_part)
                    else:
                        # Skip orphaned tool response
                        orphaned_count += 1
                        orphaned_tool_names.append(request_part.tool_name or "unknown")
                else:
                    filtered_parts.append(request_part)

            # Only add if there are remaining parts
            if filtered_parts:
                filtered.append(ModelRequest(parts=filtered_parts))
        else:
            filtered.append(msg)

    # Log if any tool responses were filtered
    if orphaned_count > 0:
        logger.info(
            "Filtered orphaned tool responses",
            extra={
                "orphaned_count": orphaned_count,
                "total_messages": len(messages),
                "orphaned_tool_names": orphaned_tool_names,
            },
        )

    return filtered


# Pattern to extract file path from the marker string preceding BinaryContent
# Format: "\n\n--- File: {path} ---"
_FILE_MARKER_PATTERN = re.compile(r"^[\n\s]*---\s*File:\s*(.+?)\s*---$")


def _extract_file_path(text: str) -> str | None:
    """Extract file path from a file marker string.

    Args:
        text: String potentially containing a file marker

    Returns:
        The file path if found, None otherwise
    """
    match = _FILE_MARKER_PATTERN.match(text.strip())
    return match.group(1) if match else None


def _create_file_reference(
    binary: BinaryContent, file_path: str | None
) -> dict[str, Any]:
    """Create a FileReference dict from BinaryContent.

    Args:
        binary: The BinaryContent to create a reference for
        file_path: The file path if known, None for unknown

    Returns:
        A dict representation of FileReference
    """
    return {
        "kind": "file_reference",
        "file_path": file_path or "<unknown>",
        "media_type": binary.media_type,
        "size_bytes": len(binary.data),
    }


def _filter_content_parts(content: Sequence[UserContent]) -> list[UserContent]:
    """Replace BinaryContent with FileReference in content parts.

    Args:
        content: Sequence of content parts (strings, BinaryContent, etc.)

    Returns:
        New list with BinaryContent replaced by FileReference dicts
    """
    result: list[UserContent] = []
    last_file_path: str | None = None

    for item in content:
        if isinstance(item, str):
            # Check if this is a file marker and extract the path
            extracted_path = _extract_file_path(item)
            if extracted_path:
                last_file_path = extracted_path
            result.append(item)
        elif isinstance(item, BinaryContent):
            # Replace BinaryContent with FileReference
            file_ref = _create_file_reference(item, last_file_path)
            result.append(file_ref)  # type: ignore[arg-type]
            last_file_path = None  # Reset after use
        else:
            # Keep other content types as-is
            result.append(item)

    return result


def filter_binary_content(messages: list[ModelMessage]) -> list[ModelMessage]:
    """Replace BinaryContent with FileReference placeholders in messages.

    This ensures conversation history can be serialized to JSON without
    UTF-8 encoding issues from binary data. The FileReference preserves
    metadata about the file that was loaded.

    Args:
        messages: List of messages to filter

    Returns:
        List of messages with BinaryContent replaced by FileReference
    """
    filtered: list[ModelMessage] = []
    replaced_count = 0

    for message in messages:
        if not isinstance(message, ModelRequest):
            filtered.append(message)
            continue

        # Check if any parts contain BinaryContent
        has_binary = False
        for part in message.parts:
            if isinstance(part, UserPromptPart):
                # Content can be a string or sequence
                if isinstance(part.content, (list, tuple)):
                    for item in part.content:
                        if isinstance(item, BinaryContent):
                            has_binary = True
                            break
            if has_binary:
                break

        if not has_binary:
            filtered.append(message)
            continue

        # Filter parts, replacing BinaryContent with FileReference
        filtered_parts: list[ModelRequestPart] = []
        for part in message.parts:
            if isinstance(part, UserPromptPart) and isinstance(
                part.content, (list, tuple)
            ):
                # Filter the content parts
                new_content = _filter_content_parts(part.content)
                # Count how many were replaced
                for item in new_content:
                    if isinstance(item, dict) and item.get("kind") == "file_reference":
                        replaced_count += 1
                # Create new UserPromptPart with filtered content
                filtered_parts.append(
                    UserPromptPart(content=new_content, timestamp=part.timestamp)
                )
            else:
                filtered_parts.append(part)

        filtered.append(ModelRequest(parts=filtered_parts))

    if replaced_count > 0:
        logger.info(
            "Replaced binary content with file references",
            extra={
                "replaced_count": replaced_count,
                "total_messages": len(messages),
            },
        )

    return filtered
