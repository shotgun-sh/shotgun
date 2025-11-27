"""Async tokenizer download and caching utilities."""

import hashlib
from pathlib import Path

import aiofiles
import httpx

from shotgun.logging_config import get_logger
from shotgun.utils.file_system_utils import get_shotgun_home

logger = get_logger(__name__)

# Gemini tokenizer constants
GEMINI_TOKENIZER_URL = "https://raw.githubusercontent.com/google/gemma_pytorch/main/tokenizer/tokenizer.model"
GEMINI_TOKENIZER_SHA256 = (
    "61a7b147390c64585d6c3543dd6fc636906c9af3865a5548f27f31aee1d4c8e2"
)


def get_tokenizer_cache_dir() -> Path:
    """Get the directory for cached tokenizer models.

    Returns:
        Path to tokenizers cache directory
    """
    cache_dir = get_shotgun_home() / "tokenizers"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get_gemini_tokenizer_path() -> Path:
    """Get the path where the Gemini tokenizer should be cached.

    Returns:
        Path to cached Gemini tokenizer
    """
    return get_tokenizer_cache_dir() / "gemini_tokenizer.model"


async def download_gemini_tokenizer() -> Path:
    """Download and cache the official Gemini tokenizer model.

    This downloads Google's official Gemini/Gemma tokenizer from the
    gemma_pytorch repository and caches it locally for future use.

    The download is async and non-blocking, with SHA256 verification
    for security.

    Returns:
        Path to the cached tokenizer file

    Raises:
        RuntimeError: If download fails or checksum verification fails
    """
    cache_path = get_gemini_tokenizer_path()

    # Check if already cached
    if cache_path.exists():
        logger.debug(f"Gemini tokenizer already cached at {cache_path}")
        return cache_path

    logger.info("Downloading Gemini tokenizer (4MB, first time only)...")

    try:
        # Download with async httpx
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(GEMINI_TOKENIZER_URL, follow_redirects=True)
            response.raise_for_status()
            content = response.content

        # Verify SHA256 checksum
        actual_hash = hashlib.sha256(content).hexdigest()
        if actual_hash != GEMINI_TOKENIZER_SHA256:
            raise RuntimeError(
                f"Gemini tokenizer checksum mismatch. "
                f"Expected: {GEMINI_TOKENIZER_SHA256}, got: {actual_hash}"
            )

        # Atomic write: write to temp file first, then rename
        temp_path = cache_path.with_suffix(".tmp")
        async with aiofiles.open(temp_path, "wb") as f:
            await f.write(content)
        temp_path.rename(cache_path)

        logger.info(f"Gemini tokenizer downloaded and cached at {cache_path}")
        return cache_path

    except httpx.HTTPError as e:
        raise RuntimeError(f"Failed to download Gemini tokenizer: {e}") from e
    except OSError as e:
        raise RuntimeError(f"Failed to save Gemini tokenizer: {e}") from e
