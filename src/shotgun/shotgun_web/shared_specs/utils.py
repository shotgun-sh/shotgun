"""Utility functions for shared specs module."""

from enum import StrEnum


class UploadPhase(StrEnum):
    """Upload pipeline phases."""

    CREATING = "creating"  # Creating spec/version via API
    SCANNING = "scanning"
    HASHING = "hashing"
    UPLOADING = "uploading"
    CLOSING = "closing"
    COMPLETE = "complete"
    ERROR = "error"


def format_bytes(size: int) -> str:
    """Format bytes as human-readable string.

    Args:
        size: Size in bytes

    Returns:
        Human-readable string like "1.5 KB" or "2.3 MB"
    """
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    else:
        return f"{size / (1024 * 1024 * 1024):.1f} GB"
