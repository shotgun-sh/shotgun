"""File attachment support for @path syntax.

This module provides functionality for parsing and processing file attachments
in user input using the @path syntax (e.g., @/path/to/file.pdf).
"""

from shotgun.attachments.models import (
    AttachmentBarState,
    AttachmentHint,
    AttachmentParseResult,
    AttachmentType,
    FileAttachment,
)
from shotgun.attachments.parser import is_image_type, parse_attachment_reference
from shotgun.attachments.processor import (
    create_attachment_hint_display,
    format_file_size,
    get_attachment_icon,
    get_provider_size_limit,
    process_attachment,
    validate_file_size,
)

__all__ = [
    # Models
    "AttachmentBarState",
    "AttachmentHint",
    "AttachmentParseResult",
    "AttachmentType",
    "FileAttachment",
    # Parser
    "is_image_type",
    "parse_attachment_reference",
    # Processor
    "create_attachment_hint_display",
    "format_file_size",
    "get_attachment_icon",
    "get_provider_size_limit",
    "process_attachment",
    "validate_file_size",
]
