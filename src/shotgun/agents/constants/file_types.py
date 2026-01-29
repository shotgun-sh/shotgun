"""Centralized file type constants for the agents module.

This module defines file extensions, MIME types, and size limits used
for multimodal file handling (file_requests and multimodal_file_read).
"""

from typing import TypeAlias

from pydantic_ai import BinaryContent

# Type alias for file content - either binary (PDF, image) or text
FileContent: TypeAlias = str | BinaryContent

# Binary file extensions that require BinaryContent loading
BINARY_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".pdf",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
    }
)

# Text file extensions that can be read as strings
TEXT_EXTENSIONS: frozenset[str] = frozenset(
    {
        # Documentation
        ".md",
        ".txt",
        ".rst",
        # Data formats
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".xml",
        ".csv",
        # Web
        ".html",
        ".css",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        # Programming languages
        ".py",
        ".java",
        ".go",
        ".rs",
        ".rb",
        ".php",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".cs",
        ".swift",
        ".kt",
        ".scala",
        # Scripts
        ".sh",
        ".bash",
        ".sql",
        ".ps1",
        # Config
        ".ini",
        ".cfg",
        ".conf",
        ".env",
        ".properties",
        # Other
        ".log",
        ".diff",
        ".patch",
        ".gitignore",
        ".dockerignore",
    }
)

# MIME type mapping for binary file types
MIME_TYPES: dict[str, str] = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}

# Maximum file sizes
MAX_BINARY_FILE_SIZE_BYTES: int = 32 * 1024 * 1024  # 32MB (Anthropic's limit)
MAX_TEXT_FILE_SIZE_BYTES: int = 1 * 1024 * 1024  # 1MB


def is_binary_extension(suffix: str) -> bool:
    """Check if a file extension is a binary type.

    Args:
        suffix: File extension (e.g., ".pdf", ".png")

    Returns:
        True if the extension is a binary type
    """
    return suffix.lower() in BINARY_EXTENSIONS


def is_text_extension(suffix: str) -> bool:
    """Check if a file extension is a text type.

    Args:
        suffix: File extension (e.g., ".md", ".txt")

    Returns:
        True if the extension is a text type
    """
    return suffix.lower() in TEXT_EXTENSIONS


def is_supported_extension(suffix: str) -> bool:
    """Check if a file extension is supported for file_requests.

    Args:
        suffix: File extension (e.g., ".pdf", ".md")

    Returns:
        True if the extension is supported (binary or text)
    """
    return is_binary_extension(suffix) or is_text_extension(suffix)


def get_mime_type(suffix: str) -> str | None:
    """Get MIME type for a file extension.

    Args:
        suffix: File extension (e.g., ".pdf", ".png")

    Returns:
        MIME type string or None if not a binary type
    """
    return MIME_TYPES.get(suffix.lower())
