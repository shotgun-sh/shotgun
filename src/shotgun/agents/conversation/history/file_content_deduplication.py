"""Pre-compaction file content deduplication for conversation history.

This module provides a deterministic pre-pass that removes file content from
tool returns before LLM-based compaction. Files are still accessible via
`retrieve_code` (codebase) or `read_file` (.shotgun/ folder).
"""

from enum import StrEnum
from typing import Any

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ToolReturnPart,
)

from shotgun.logging_config import get_logger

logger = get_logger(__name__)


class FileReadTool(StrEnum):
    """Tool names that read file content."""

    CODEBASE = "file_read"  # Reads from indexed codebase (Kuzu graph)
    SHOTGUN_FOLDER = "read_file"  # Reads from .shotgun/ folder


# Minimum content length to bother deduplicating (skip tiny files)
MIN_CONTENT_LENGTH = 500

# Placeholder templates for each type
CODEBASE_PLACEHOLDER = (
    "**File**: `{file_path}`\n"
    "**Size**: {size_bytes} bytes | **Language**: {language}\n"
    "**Content**: [Removed for compaction - use `retrieve_code` or `file_read` to access]"
)

SHOTGUN_PLACEHOLDER = (
    "**File**: `.shotgun/{filename}`\n"
    "**Content**: [Removed for compaction - file persisted in .shotgun/ folder]"
)

# Simple prefix for detecting file_read output format
# Instead of using regex, we just check for the expected prefix and extract the file path
CODEBASE_FILE_PREFIX = "**File**: `"


def _extract_file_path(content: str) -> str | None:
    """Extract file path from file_read tool return content.

    Uses simple string operations instead of regex for maximum performance.
    The file_read tool output format is: **File**: `path`\\n...

    Args:
        content: The tool return content string

    Returns:
        The file path or None if format doesn't match
    """
    # Fast check: content must start with expected prefix
    if not content.startswith(CODEBASE_FILE_PREFIX):
        return None

    # Find the closing backtick after the prefix
    prefix_len = len(CODEBASE_FILE_PREFIX)
    backtick_pos = content.find("`", prefix_len)

    if backtick_pos == -1:
        return None

    return content[prefix_len:backtick_pos]


def _get_language_from_path(file_path: str) -> str:
    """Infer programming language from file extension."""
    from pathlib import Path

    from shotgun.codebase.core.language_config import get_language_config

    ext = Path(file_path).suffix
    config = get_language_config(ext)
    return config.name if config else "unknown"


def _create_codebase_placeholder(file_path: str, size_bytes: int, language: str) -> str:
    """Create placeholder for codebase file content."""
    return CODEBASE_PLACEHOLDER.format(
        file_path=file_path,
        size_bytes=size_bytes,
        language=language or "unknown",
    )


def _create_shotgun_placeholder(filename: str) -> str:
    """Create placeholder for .shotgun/ file content."""
    return SHOTGUN_PLACEHOLDER.format(filename=filename)


def _estimate_tokens_saved(original: str, replacement: str) -> int:
    """Rough estimate of tokens saved (~4 chars per token)."""
    original_chars = len(original)
    replacement_chars = len(replacement)
    # Rough token estimate: ~4 characters per token for code
    return max(0, (original_chars - replacement_chars) // 4)


def deduplicate_file_content(
    messages: list[ModelMessage],
    retention_window: int = 3,
) -> tuple[list[ModelMessage], int]:
    """Replace file read content with placeholders for indexed/persisted files.

    This is a deterministic pre-compaction pass that reduces tokens without
    requiring an LLM. Files remain accessible via their respective tools.

    This function uses copy-on-write semantics: only messages that need
    modification are copied, while unmodified messages are reused by reference.
    This significantly reduces memory allocation and processing time for large
    conversations where only a subset of messages contain file content.

    Args:
        messages: Conversation history
        retention_window: Keep full content in last N messages (for recent context)

    Returns:
        Tuple of (modified_messages, estimated_tokens_saved)
    """
    if not messages:
        return messages, 0

    total_tokens_saved = 0
    files_deduplicated = 0

    # Calculate retention boundary (keep last N messages intact)
    retention_start = max(0, len(messages) - retention_window)

    # Track which message indices need replacement
    # We use a dict to store index -> new_message mappings
    replacements: dict[int, ModelMessage] = {}

    for msg_idx, message in enumerate(messages):
        # Skip messages in retention window
        if msg_idx >= retention_start:
            continue

        # Only process ModelRequest (which contains ToolReturnPart)
        if not isinstance(message, ModelRequest):
            continue

        # Build new parts list, replacing file content where appropriate
        new_parts: list[Any] = []
        message_modified = False

        for part in message.parts:
            if not isinstance(part, ToolReturnPart):
                new_parts.append(part)
                continue

            tool_name = part.tool_name
            content = part.content

            # Skip if content is too short to bother
            if not isinstance(content, str) or len(content) < MIN_CONTENT_LENGTH:
                new_parts.append(part)
                continue

            replacement = None
            original_content = content

            # Handle codebase file reads (file_read)
            if tool_name == FileReadTool.CODEBASE:
                file_path = _extract_file_path(content)
                if file_path:
                    # Use content length as size estimate (includes formatting overhead
                    # but close enough for deduplication purposes)
                    size_bytes = len(content)
                    language = _get_language_from_path(file_path)
                    replacement = _create_codebase_placeholder(
                        file_path, size_bytes, language
                    )
                    logger.debug(
                        f"Deduplicating codebase file: {file_path} ({size_bytes} bytes)"
                    )

            # Handle .shotgun/ file reads (read_file)
            elif tool_name == FileReadTool.SHOTGUN_FOLDER:
                # For read_file, content is raw - we need to figure out filename
                # from the tool call args (but we only have the return here)
                # Use a generic placeholder since we don't have the filename
                if len(content) >= MIN_CONTENT_LENGTH:
                    # Try to extract filename from content if it looks like markdown
                    # Otherwise use generic placeholder
                    replacement = _create_shotgun_placeholder("artifact")
                    logger.debug(
                        f"Deduplicating .shotgun/ file read ({len(content)} chars)"
                    )

            # Apply replacement if we have one
            if replacement:
                # Create new ToolReturnPart with replaced content
                new_part = ToolReturnPart(
                    tool_name=part.tool_name,
                    tool_call_id=part.tool_call_id,
                    content=replacement,
                    timestamp=part.timestamp,
                )
                new_parts.append(new_part)
                message_modified = True

                tokens_saved = _estimate_tokens_saved(original_content, replacement)
                total_tokens_saved += tokens_saved
                files_deduplicated += 1
            else:
                new_parts.append(part)

        # Only create a new message if parts were actually modified
        if message_modified:
            replacements[msg_idx] = ModelRequest(parts=new_parts)

    # If no modifications were made, return original list (no allocation needed)
    if not replacements:
        return messages, 0

    # Build result list with copy-on-write: reuse unmodified messages
    modified_messages: list[ModelMessage] = []
    for idx, msg in enumerate(messages):
        if idx in replacements:
            modified_messages.append(replacements[idx])
        else:
            modified_messages.append(msg)

    if files_deduplicated > 0:
        logger.info(
            f"File content deduplication: {files_deduplicated} files, "
            f"~{total_tokens_saved:,} tokens saved"
        )

    return modified_messages, total_tokens_saved
