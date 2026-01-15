"""Attachment processor for file validation and encoding.

Provides functions to validate file sizes against provider limits
and encode file contents to base64 for API submission.
"""

import base64
import logging
from pathlib import Path

import aiofiles

from shotgun.agents.config.models import ProviderType
from shotgun.attachments.errors import (
    cannot_read_file,
    file_not_found,
    file_too_large,
)
from shotgun.attachments.models import AttachmentType, FileAttachment

logger = logging.getLogger(__name__)

# Provider file size limits in bytes
PROVIDER_SIZE_LIMITS: dict[ProviderType, int] = {
    ProviderType.OPENAI: 20 * 1024 * 1024,  # 20MB
    ProviderType.ANTHROPIC: 32 * 1024 * 1024,  # 32MB
    ProviderType.GOOGLE: 4 * 1024 * 1024,  # 4MB
}

# Default limit for unknown providers (most restrictive)
DEFAULT_SIZE_LIMIT: int = 4 * 1024 * 1024  # 4MB


def get_provider_size_limit(provider: ProviderType) -> int:
    """Get the maximum file size limit for a provider.

    Args:
        provider: The LLM provider type.

    Returns:
        Maximum file size in bytes.
    """
    return PROVIDER_SIZE_LIMITS.get(provider, DEFAULT_SIZE_LIMIT)


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format.

    Args:
        size_bytes: File size in bytes.

    Returns:
        Human-readable string (e.g., "2.5 MB", "512 KB", "128 B").
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def validate_file_size(
    attachment: FileAttachment,
    provider: ProviderType,
) -> tuple[bool, str | None]:
    """Validate file size against provider limit.

    Args:
        attachment: The file attachment to validate.
        provider: The target LLM provider.

    Returns:
        Tuple of (is_valid, error_message).
        If valid: (True, None)
        If invalid: (False, "File size {size} exceeds {provider} limit of {limit}")
    """
    limit = get_provider_size_limit(provider)

    if attachment.file_size_bytes > limit:
        size_str = format_file_size(attachment.file_size_bytes)
        limit_str = format_file_size(limit)
        provider_name = provider.value.capitalize()
        return (
            False,
            file_too_large(size_str, limit_str, provider_name),
        )

    return (True, None)


async def encode_file_to_base64(file_path: Path) -> str:
    """Asynchronously read and encode file contents to base64.

    Args:
        file_path: Path to the file to encode.

    Returns:
        Base64-encoded string of file contents.

    Raises:
        FileNotFoundError: If file does not exist.
        PermissionError: If file cannot be read.
        OSError: If file read fails.
    """
    async with aiofiles.open(file_path, "rb") as f:
        content = await f.read()

    if not content:
        return ""

    return base64.b64encode(content).decode("utf-8")


async def process_attachment(
    attachment: FileAttachment,
    provider: ProviderType,
) -> tuple[FileAttachment, str | None]:
    """Validate and process an attachment for submission.

    Validates file size against provider limits and encodes content to base64.
    All supported attachment types (PDF, PNG, JPG, JPEG, GIF, WEBP) work with
    all providers (OpenAI, Anthropic, Google) via BinaryContent.

    Args:
        attachment: The file attachment to process.
        provider: The target LLM provider.

    Returns:
        Tuple of (processed_attachment, error_message).
        If successful: (attachment_with_base64_content, None)
        If failed: (original_attachment, error_message)
    """
    # Validate file size
    is_valid, error = validate_file_size(attachment, provider)
    if not is_valid:
        return (attachment, error)

    # Encode file to base64
    try:
        content_base64 = await encode_file_to_base64(attachment.file_path)
    except FileNotFoundError:
        return (attachment, file_not_found(attachment.file_path))
    except PermissionError:
        return (attachment, cannot_read_file(attachment.file_path, "permission denied"))
    except OSError as e:
        logger.warning(f"Failed to read file '{attachment.file_path}': {e}")
        return (attachment, cannot_read_file(attachment.file_path))

    # Create new attachment with base64 content
    processed = FileAttachment(
        file_path=attachment.file_path,
        file_name=attachment.file_name,
        file_type=attachment.file_type,
        file_size_bytes=attachment.file_size_bytes,
        content_base64=content_base64,
        mime_type=attachment.mime_type,
    )

    logger.debug(
        f"Processed attachment: {processed.file_name} "
        f"({len(content_base64)} base64 chars)"
    )

    return (processed, None)


def create_attachment_hint_display(attachment: FileAttachment) -> str:
    """Create display string for attachment in chat history.

    Args:
        attachment: The file attachment.

    Returns:
        Formatted display string (e.g., "document.pdf (2.5 MB)").
    """
    size_str = format_file_size(attachment.file_size_bytes)
    return f"{attachment.file_name} ({size_str})"


def get_attachment_icon(attachment_type: AttachmentType) -> str:
    """Get the appropriate icon for an attachment type.

    Args:
        attachment_type: The type of attachment.

    Returns:
        Icon string for display.
    """
    if attachment_type == AttachmentType.PDF:
        return "\U0001f4c4"  # document emoji
    else:
        return "\U0001f5bc\ufe0f"  # framed picture emoji
