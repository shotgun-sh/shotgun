"""Async SHA-256 file hashing utilities."""

import hashlib
from pathlib import Path

import aiofiles

from shotgun.logging_config import get_logger

logger = get_logger(__name__)

# Chunk sizes for reading files
SMALL_FILE_CHUNK_SIZE = 65536  # 64KB for files < 10MB
LARGE_FILE_CHUNK_SIZE = 1048576  # 1MB for files >= 10MB
LARGE_FILE_THRESHOLD = 10 * 1024 * 1024  # 10MB


def _get_chunk_size(file_size: int) -> int:
    """Determine optimal chunk size based on file size.

    Args:
        file_size: Size of file in bytes

    Returns:
        Chunk size in bytes (64KB for small files, 1MB for large files)
    """
    if file_size >= LARGE_FILE_THRESHOLD:
        return LARGE_FILE_CHUNK_SIZE
    return SMALL_FILE_CHUNK_SIZE


async def calculate_sha256(file_path: Path) -> str:
    """Calculate SHA-256 hash of a file using streaming.

    Reads file in chunks to avoid loading entire file into memory.
    Uses adaptive chunk sizing: 64KB for files <10MB, 1MB for larger files.

    Args:
        file_path: Path to file to hash

    Returns:
        Hex-encoded SHA-256 hash string (64 characters)

    Raises:
        FileNotFoundError: If file does not exist
        PermissionError: If file is not readable
    """
    file_size = file_path.stat().st_size
    chunk_size = _get_chunk_size(file_size)

    logger.debug(
        "Calculating SHA-256 for %s (size=%d, chunk_size=%d)",
        file_path,
        file_size,
        chunk_size,
    )

    sha256_hash = hashlib.sha256()

    async with aiofiles.open(file_path, "rb") as f:
        while chunk := await f.read(chunk_size):
            sha256_hash.update(chunk)

    hex_digest = sha256_hash.hexdigest()
    logger.debug("SHA-256 for %s: %s", file_path, hex_digest)

    return hex_digest


async def calculate_sha256_with_size(file_path: Path) -> tuple[str, int]:
    """Calculate SHA-256 hash and get file size.

    Convenience function that returns both hash and size in one call.

    Args:
        file_path: Path to file to hash

    Returns:
        Tuple of (hex-encoded SHA-256 hash, file size in bytes)
    """
    file_size = file_path.stat().st_size
    content_hash = await calculate_sha256(file_path)
    return content_hash, file_size
