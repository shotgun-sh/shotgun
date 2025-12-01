"""Supabase Storage download utilities."""

import httpx

from shotgun.logging_config import get_logger

logger = get_logger(__name__)


async def download_file_from_url(download_url: str) -> bytes:
    """Download a file from a presigned Supabase Storage URL.

    The API returns presigned URLs with embedded tokens that don't require
    any authentication headers.

    Args:
        download_url: Presigned Supabase Storage URL
                     (e.g., "https://...supabase.co/storage/v1/object/sign/...?token=...")

    Returns:
        File contents as bytes

    Raises:
        httpx.HTTPStatusError: If download fails
    """
    logger.debug("Downloading file from: %s", download_url)

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(download_url)
        response.raise_for_status()
        return response.content
