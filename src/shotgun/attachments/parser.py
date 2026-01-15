"""Attachment path parser for @path syntax in user input.

Parses file references from user input text. Supported formats:
- Absolute paths: @/absolute/path.pdf
- Home directory: @~/Documents/file.png
- Explicit relative: @./relative.jpg, @../parent/file.gif
- Bare relative: @tmp/file.pdf, @path/to/file.png
- Filename only: @document.pdf, @image.png

Without the @ prefix, file paths are passed through to the LLM which
can use its own file tools to handle them.
"""

import logging
import re
from pathlib import Path

from shotgun.attachments.errors import (
    cannot_read_file,
    could_not_resolve_path,
    file_not_found,
    not_a_file,
    unsupported_file_type,
)
from shotgun.attachments.models import (
    AttachmentParseResult,
    AttachmentType,
    FileAttachment,
)

logger = logging.getLogger(__name__)

# Regex pattern for @path syntax
# Matches:
# - Explicit prefixes: @/absolute, @~/, @./, @../
# - Bare relative paths: @tmp/file, @path/to/file
# - Filenames with supported extensions: @file.pdf, @image.png
# Excludes trailing punctuation that commonly follows paths in sentences
ATTACHMENT_PATH_PATTERN = re.compile(
    r"@("
    r"(?:/|~|\.\.?/)[^\s?!,;:\"')\]]+"  # /path, ~/path, ./path, ../path
    r"|"
    r"\w[^\s?!,;:\"')\]@]*/[^\s?!,;:\"')\]]+"  # path/to/file (bare relative)
    r"|"
    r"\w[\w.-]*\.(?:pdf|png|jpe?g|gif|webp)"  # file.pdf (filename with extension)
    r")",
    re.IGNORECASE,
)

# Supported file extensions mapped to AttachmentType
SUPPORTED_EXTENSIONS: dict[str, AttachmentType] = {
    ".pdf": AttachmentType.PDF,
    ".png": AttachmentType.PNG,
    ".jpg": AttachmentType.JPG,
    ".jpeg": AttachmentType.JPEG,
    ".gif": AttachmentType.GIF,
    ".webp": AttachmentType.WEBP,
}

# MIME types for each attachment type
MIME_TYPES: dict[AttachmentType, str] = {
    AttachmentType.PDF: "application/pdf",
    AttachmentType.PNG: "image/png",
    AttachmentType.JPG: "image/jpeg",
    AttachmentType.JPEG: "image/jpeg",
    AttachmentType.GIF: "image/gif",
    AttachmentType.WEBP: "image/webp",
}


def _extract_path_reference(text: str) -> str | None:
    """Extract the first @path reference from text.

    Args:
        text: Input text to search.

    Returns:
        The path string (without @) if found, None otherwise.
    """
    match = ATTACHMENT_PATH_PATTERN.search(text)
    if match:
        return match.group(1)
    return None


def _resolve_path(path_str: str) -> Path:
    """Resolve a path string to an absolute Path.

    Handles:
    - Absolute paths: /path/to/file
    - Home directory: ~/path/to/file
    - Relative paths: ./file or ../file

    Args:
        path_str: Path string from user input.

    Returns:
        Resolved absolute Path object.
    """
    path = Path(path_str)

    # Expand ~ to user home directory
    if path_str.startswith("~"):
        path = path.expanduser()

    # Resolve to absolute path (handles ./ and ../)
    return path.resolve()


def _validate_file_extension(path: Path) -> AttachmentType | None:
    """Validate file has a supported extension.

    Args:
        path: Path to validate.

    Returns:
        AttachmentType if extension is supported, None otherwise.
    """
    extension = path.suffix.lower()
    return SUPPORTED_EXTENSIONS.get(extension)


def _get_mime_type(attachment_type: AttachmentType) -> str:
    """Get MIME type for an attachment type.

    Args:
        attachment_type: The attachment type enum.

    Returns:
        MIME type string (e.g., "application/pdf").
    """
    return MIME_TYPES[attachment_type]


def is_image_type(attachment_type: AttachmentType) -> bool:
    """Check if attachment type is an image format.

    Args:
        attachment_type: The attachment type to check.

    Returns:
        True if PNG, JPG, JPEG, GIF, or WEBP; False for PDF.
    """
    return attachment_type != AttachmentType.PDF


def parse_attachment_reference(text: str) -> AttachmentParseResult:
    """Parse @path reference from user input text.

    Extracts the first @path reference from the input text, validates the file
    exists and has a supported extension, and returns parsing result.

    The original text is preserved with the @path reference intact so the LLM
    knows which file is being referenced.

    Args:
        text: User input text that may contain an @path reference.

    Returns:
        AttachmentParseResult with:
        - original_text: The input text unchanged (with @path preserved)
        - attachment: FileAttachment if valid file found, None otherwise
        - error_message: Error description if parsing failed, None if successful

    Examples:
        >>> result = parse_attachment_reference("Analyze @/path/to/doc.pdf")
        >>> result.original_text
        'Analyze @/path/to/doc.pdf'
        >>> result.attachment.file_name
        'doc.pdf'
    """
    # Extract path reference from text
    path_str = _extract_path_reference(text)

    # No @path reference found - not an error, just no attachment
    if path_str is None:
        return AttachmentParseResult(
            original_text=text,
            attachment=None,
            error_message=None,
        )

    # Resolve to absolute path
    try:
        resolved_path = _resolve_path(path_str)
    except Exception as e:
        logger.warning(f"Failed to resolve path '{path_str}': {e}")
        return AttachmentParseResult(
            original_text=text,
            attachment=None,
            error_message=could_not_resolve_path(path_str),
        )

    # Check if file exists
    if not resolved_path.exists():
        return AttachmentParseResult(
            original_text=text,
            attachment=None,
            error_message=file_not_found(resolved_path),
        )

    # Check if it's a file (not a directory)
    if not resolved_path.is_file():
        return AttachmentParseResult(
            original_text=text,
            attachment=None,
            error_message=not_a_file(resolved_path),
        )

    # Validate file extension
    attachment_type = _validate_file_extension(resolved_path)
    if attachment_type is None:
        extension = resolved_path.suffix or "(no extension)"
        supported = ", ".join(ext.lstrip(".") for ext in SUPPORTED_EXTENSIONS.keys())
        return AttachmentParseResult(
            original_text=text,
            attachment=None,
            error_message=unsupported_file_type(extension, supported),
        )

    # Check file is readable
    try:
        file_size = resolved_path.stat().st_size
    except PermissionError:
        return AttachmentParseResult(
            original_text=text,
            attachment=None,
            error_message=cannot_read_file(resolved_path, "permission denied"),
        )
    except OSError as e:
        logger.warning(f"Failed to stat file '{resolved_path}': {e}")
        return AttachmentParseResult(
            original_text=text,
            attachment=None,
            error_message=cannot_read_file(resolved_path),
        )

    # Create successful attachment (content_base64 will be populated by processor)
    attachment = FileAttachment(
        file_path=resolved_path,
        file_name=resolved_path.name,
        file_type=attachment_type,
        file_size_bytes=file_size,
        content_base64=None,
        mime_type=_get_mime_type(attachment_type),
    )

    logger.debug(
        f"Parsed attachment: {attachment.file_name} "
        f"({attachment.file_type.value}, {file_size} bytes)"
    )

    return AttachmentParseResult(
        original_text=text,
        attachment=attachment,
        error_message=None,
    )
