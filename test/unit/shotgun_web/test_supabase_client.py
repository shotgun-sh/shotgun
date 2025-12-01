"""Tests for shotgun_web.supabase_client module."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from shotgun.shotgun_web.supabase_client import download_file_from_url


@pytest.mark.asyncio
async def test_download_file_from_url_success():
    """Test download_file_from_url returns file content."""
    mock_response = MagicMock()
    mock_response.content = b"Test file content"
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch(
        "httpx.AsyncClient",
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_client)),
    ):
        result = await download_file_from_url(
            "https://storage.example.com/file.md?token=abc123"
        )

        assert result == b"Test file content"
        mock_client.get.assert_called_once_with(
            "https://storage.example.com/file.md?token=abc123"
        )


@pytest.mark.asyncio
async def test_download_file_from_url_http_error():
    """Test download_file_from_url propagates HTTP errors."""
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Not Found",
        request=MagicMock(),
        response=MagicMock(status_code=404),
    )

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch(
        "httpx.AsyncClient",
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_client)),
    ):
        with pytest.raises(httpx.HTTPStatusError):
            await download_file_from_url(
                "https://storage.example.com/nonexistent.md?token=abc123"
            )
