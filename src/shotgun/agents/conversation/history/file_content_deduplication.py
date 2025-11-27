"""Pre-compaction file content deduplication for conversation history.

This module provides a deterministic pre-pass that removes file content from
tool returns before LLM-based compaction. Files are still accessible via
`retrieve_code` (codebase) or `read_file` (.shotgun/ folder).
"""

import copy
import re
from typing import TYPE_CHECKING, Any

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ToolReturnPart,
)

from shotgun.logging_config import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

# Tools that read file content
CODEBASE_FILE_TOOL = "file_read"  # Reads from indexed codebase (Kuzu graph)
SHOTGUN_FILE_TOOLS = {"read_file"}  # Reads from .shotgun/ folder

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

# Pattern for parsing file_read output (codebase files)
# Format: **File**: `path`\n**Size**: N bytes\n[optional encoding]\n\n**Content**:\n```lang\ncontent```
CODEBASE_FILE_PATTERN = re.compile(
    r"\*\*File\*\*:\s*`([^`]+)`\s*\n"  # File path
    r"\*\*Size\*\*:\s*(\d+)\s*bytes\s*\n"  # Size in bytes
    r"(?:\*\*Encoding\*\*:.*?\n)?"  # Optional encoding line
    r"\n\*\*Content\*\*:\s*\n"  # Blank line + Content header
    r"```(\w*)\n"  # Language tag
    r"(.*?)```",  # Actual content
    re.DOTALL,
)


def _parse_codebase_file_content(
    content: str,
) -> tuple[str, int, str, str] | None:
    """Parse file_read tool return content.

    Args:
        content: The tool return content string

    Returns:
        Tuple of (file_path, size_bytes, language, actual_content) or None if not parseable
    """
    match = CODEBASE_FILE_PATTERN.search(content)
    if not match:
        return None

    file_path = match.group(1)
    size_bytes = int(match.group(2))
    language = match.group(3) or ""
    actual_content = match.group(4)

    return file_path, size_bytes, language, actual_content


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

    Args:
        messages: Conversation history
        retention_window: Keep full content in last N messages (for recent context)

    Returns:
        Tuple of (modified_messages, estimated_tokens_saved)
    """
    if not messages:
        return messages, 0

    # Deep copy to avoid modifying original
    modified_messages = copy.deepcopy(messages)
    total_tokens_saved = 0
    files_deduplicated = 0

    # Calculate retention boundary (keep last N messages intact)
    retention_start = max(0, len(modified_messages) - retention_window)

    for msg_idx, message in enumerate(modified_messages):
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
            if tool_name == CODEBASE_FILE_TOOL:
                parsed = _parse_codebase_file_content(content)
                if parsed:
                    file_path, size_bytes, language, actual_content = parsed
                    # Only replace if actual content is substantial
                    if len(actual_content) >= MIN_CONTENT_LENGTH:
                        replacement = _create_codebase_placeholder(
                            file_path, size_bytes, language
                        )
                        logger.debug(
                            f"Deduplicating codebase file: {file_path} "
                            f"({size_bytes} bytes)"
                        )

            # Handle .shotgun/ file reads (read_file)
            elif tool_name in SHOTGUN_FILE_TOOLS:
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

        # Replace message with new parts if modified
        if message_modified:
            modified_messages[msg_idx] = ModelRequest(parts=new_parts)

    if files_deduplicated > 0:
        logger.info(
            f"File content deduplication: {files_deduplicated} files, "
            f"~{total_tokens_saved:,} tokens saved"
        )

    return modified_messages, total_tokens_saved
