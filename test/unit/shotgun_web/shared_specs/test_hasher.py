"""Tests for shared_specs.hasher module."""

import hashlib
from pathlib import Path

import pytest

from shotgun.shotgun_web.shared_specs.hasher import (
    LARGE_FILE_CHUNK_SIZE,
    LARGE_FILE_THRESHOLD,
    SMALL_FILE_CHUNK_SIZE,
    _get_chunk_size,
    calculate_sha256,
    calculate_sha256_with_size,
)


def test_get_chunk_size_small_file():
    """Test chunk size for small files."""
    # Files under 10MB should use 64KB chunks
    assert _get_chunk_size(1024) == SMALL_FILE_CHUNK_SIZE
    assert _get_chunk_size(1024 * 1024) == SMALL_FILE_CHUNK_SIZE
    assert _get_chunk_size(LARGE_FILE_THRESHOLD - 1) == SMALL_FILE_CHUNK_SIZE


def test_get_chunk_size_large_file():
    """Test chunk size for large files."""
    # Files >= 10MB should use 1MB chunks
    assert _get_chunk_size(LARGE_FILE_THRESHOLD) == LARGE_FILE_CHUNK_SIZE
    assert _get_chunk_size(LARGE_FILE_THRESHOLD + 1) == LARGE_FILE_CHUNK_SIZE
    assert _get_chunk_size(100 * 1024 * 1024) == LARGE_FILE_CHUNK_SIZE


@pytest.mark.asyncio
async def test_calculate_sha256_known_content(temp_file_for_hash: Path):
    """Test SHA-256 calculation matches expected hash for known content."""
    # "Hello, World!" has a known SHA-256 hash
    expected_hash = hashlib.sha256(b"Hello, World!").hexdigest()

    result = await calculate_sha256(temp_file_for_hash)

    assert result == expected_hash
    assert len(result) == 64  # SHA-256 produces 64 hex characters


@pytest.mark.asyncio
async def test_calculate_sha256_empty_file(tmp_path: Path):
    """Test SHA-256 calculation for empty file."""
    empty_file = tmp_path / "empty.txt"
    empty_file.write_bytes(b"")

    expected_hash = hashlib.sha256(b"").hexdigest()
    result = await calculate_sha256(empty_file)

    assert result == expected_hash


@pytest.mark.asyncio
async def test_calculate_sha256_binary_content(tmp_path: Path):
    """Test SHA-256 calculation for binary content."""
    binary_file = tmp_path / "binary.bin"
    binary_content = bytes(range(256))
    binary_file.write_bytes(binary_content)

    expected_hash = hashlib.sha256(binary_content).hexdigest()
    result = await calculate_sha256(binary_file)

    assert result == expected_hash


@pytest.mark.asyncio
async def test_calculate_sha256_large_file(large_temp_file: Path):
    """Test SHA-256 calculation for large files uses streaming correctly."""
    # Calculate expected hash
    expected_hash = hashlib.sha256(b"x" * (15 * 1024 * 1024)).hexdigest()

    result = await calculate_sha256(large_temp_file)

    assert result == expected_hash


@pytest.mark.asyncio
async def test_calculate_sha256_file_not_found(tmp_path: Path):
    """Test SHA-256 raises FileNotFoundError for missing file."""
    non_existent = tmp_path / "does_not_exist.txt"

    with pytest.raises(FileNotFoundError):
        await calculate_sha256(non_existent)


@pytest.mark.asyncio
async def test_calculate_sha256_with_size(temp_file_for_hash: Path):
    """Test calculate_sha256_with_size returns both hash and size."""
    expected_hash = hashlib.sha256(b"Hello, World!").hexdigest()
    expected_size = len("Hello, World!")

    content_hash, file_size = await calculate_sha256_with_size(temp_file_for_hash)

    assert content_hash == expected_hash
    assert file_size == expected_size


@pytest.mark.asyncio
async def test_calculate_sha256_with_size_large_file(large_temp_file: Path):
    """Test calculate_sha256_with_size for large files."""
    expected_size = 15 * 1024 * 1024

    content_hash, file_size = await calculate_sha256_with_size(large_temp_file)

    assert len(content_hash) == 64
    assert file_size == expected_size


@pytest.mark.asyncio
async def test_calculate_sha256_deterministic(temp_file_for_hash: Path):
    """Test SHA-256 calculation is deterministic."""
    hash1 = await calculate_sha256(temp_file_for_hash)
    hash2 = await calculate_sha256(temp_file_for_hash)

    assert hash1 == hash2
