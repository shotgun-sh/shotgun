"""Attachment error message formatting utilities.

Centralizes error message formatting for consistent user feedback.
All attachment-related error messages should use these functions.
"""

from pathlib import Path

# Warning emoji prefix for all error messages
WARNING_PREFIX = "\u26a0\ufe0f"  # ⚠️


def file_not_found(path: Path | str) -> str:
    """Format file not found error message."""
    return f"{WARNING_PREFIX} File not found: {path}"


def not_a_file(path: Path | str) -> str:
    """Format not a file (e.g., directory) error message."""
    return f"{WARNING_PREFIX} Not a file: {path}"


def unsupported_file_type(extension: str, supported: str) -> str:
    """Format unsupported file type error message.

    Args:
        extension: The file extension (e.g., ".doc" or "(no extension)")
        supported: Comma-separated list of supported extensions
    """
    return (
        f"{WARNING_PREFIX} Unsupported file type: {extension} (supported: {supported})"
    )


def cannot_read_file(path: Path | str, reason: str | None = None) -> str:
    """Format cannot read file error message.

    Args:
        path: Path to the file
        reason: Optional reason (e.g., "permission denied")
    """
    if reason:
        return f"{WARNING_PREFIX} Cannot read file: {path} ({reason})"
    return f"{WARNING_PREFIX} Cannot read file: {path}"


def could_not_resolve_path(path: str) -> str:
    """Format path resolution error message."""
    return f"{WARNING_PREFIX} Could not resolve path: {path}"


def file_too_large(size: str, limit: str, provider: str) -> str:
    """Format file too large error message.

    Args:
        size: Human-readable file size (e.g., "45.0 MB")
        limit: Human-readable size limit (e.g., "32.0 MB")
        provider: Provider name (e.g., "Anthropic")
    """
    return f"{WARNING_PREFIX} File too large: {size} (max: {limit} for {provider})"
