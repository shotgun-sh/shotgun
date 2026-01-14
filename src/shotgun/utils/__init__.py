"""Utility functions for the Shotgun package.

Attachment utilities are available via direct imports to avoid circular dependencies:
    from shotgun.utils.attachment_models import FileAttachment, AttachmentType, ...
    from shotgun.utils.attachment_parser import parse_attachment_reference, ...
    from shotgun.utils.attachment_processor import process_attachment, ...
"""

from .file_system_utils import ensure_shotgun_directory_exists, get_shotgun_home

__all__ = [
    # File system utilities
    "ensure_shotgun_directory_exists",
    "get_shotgun_home",
]
