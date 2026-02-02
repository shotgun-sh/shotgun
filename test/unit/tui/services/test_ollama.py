"""Unit tests for the Ollama service."""

from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from shotgun.tui.services.ollama import (
    DEFAULT_OLLAMA_URL,
    OllamaModel,
    OllamaStatus,
    format_size,
    get_ollama_status,
)


def test_format_size_bytes():
    """Test formatting small byte sizes."""
    assert format_size(0) == "0 B"
    assert format_size(500) == "500 B"
    assert format_size(1023) == "1023 B"


def test_format_size_kilobytes():
    """Test formatting kilobyte sizes."""
    assert format_size(1024) == "1.0 KB"
    assert format_size(2048) == "2.0 KB"
    assert format_size(1536) == "1.5 KB"


def test_format_size_megabytes():
    """Test formatting megabyte sizes."""
    assert format_size(1024 * 1024) == "1.0 MB"
    assert format_size(1024 * 1024 * 2) == "2.0 MB"
    assert format_size(int(1024 * 1024 * 1.5)) == "1.5 MB"


def test_format_size_gigabytes():
    """Test formatting gigabyte sizes."""
    assert format_size(1024 * 1024 * 1024) == "1.0 GB"
    assert format_size(1024 * 1024 * 1024 * 4) == "4.0 GB"
    assert format_size(int(1024 * 1024 * 1024 * 19.2)) == "19.2 GB"


def test_ollama_model_creation():
    """Test OllamaModel Pydantic model."""
    model = OllamaModel(
        name="qwen3:32b",
        size=19234567890,
        modified_at=datetime(2024, 1, 1, 0, 0, 0),
    )
    assert model.name == "qwen3:32b"
    assert model.size == 19234567890
    assert model.modified_at == datetime(2024, 1, 1, 0, 0, 0)


def test_ollama_status_creation():
    """Test OllamaStatus Pydantic model."""
    status = OllamaStatus(running=True, models=[])
    assert status.running is True
    assert status.models == []
    assert status.error is None

    status_with_error = OllamaStatus(
        running=False, models=[], error="Connection refused"
    )
    assert status_with_error.running is False
    assert status_with_error.error == "Connection refused"


@pytest.mark.asyncio
async def test_get_ollama_status_running_with_models():
    """Test getting status when Ollama is running with models."""
    # Use Mock (not AsyncMock) for response objects since json() is synchronous
    mock_health_response = Mock()
    mock_health_response.status_code = 200

    mock_tags_response = Mock()
    mock_tags_response.json.return_value = {
        "models": [
            {
                "name": "qwen3:32b",
                "size": 19234567890,
                "modified_at": "2024-01-01T00:00:00Z",
            },
            {
                "name": "llama3:8b",
                "size": 4700000000,
                "modified_at": "2024-01-02T00:00:00Z",
            },
        ]
    }
    mock_tags_response.raise_for_status = Mock()

    with patch("shotgun.tui.services.ollama.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(
            side_effect=[mock_health_response, mock_tags_response]
        )
        mock_client.return_value.__aenter__.return_value = mock_instance

        status = await get_ollama_status()

        assert status.running is True
        assert len(status.models) == 2
        assert status.models[0].name == "qwen3:32b"
        assert status.models[0].size == 19234567890
        assert status.models[1].name == "llama3:8b"
        assert status.error is None


@pytest.mark.asyncio
async def test_get_ollama_status_running_no_models():
    """Test getting status when Ollama is running but has no models."""
    mock_health_response = Mock()
    mock_health_response.status_code = 200

    mock_tags_response = Mock()
    mock_tags_response.json.return_value = {"models": []}
    mock_tags_response.raise_for_status = Mock()

    with patch("shotgun.tui.services.ollama.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(
            side_effect=[mock_health_response, mock_tags_response]
        )
        mock_client.return_value.__aenter__.return_value = mock_instance

        status = await get_ollama_status()

        assert status.running is True
        assert len(status.models) == 0
        assert status.error is None


@pytest.mark.asyncio
async def test_get_ollama_status_not_running():
    """Test getting status when Ollama is not running."""
    with patch("shotgun.tui.services.ollama.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        mock_client.return_value.__aenter__.return_value = mock_instance

        status = await get_ollama_status()

        assert status.running is False
        assert len(status.models) == 0
        assert status.error == "Ollama is not running"


@pytest.mark.asyncio
async def test_get_ollama_status_timeout():
    """Test getting status when connection times out."""
    with patch("shotgun.tui.services.ollama.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
        mock_client.return_value.__aenter__.return_value = mock_instance

        status = await get_ollama_status()

        assert status.running is False
        assert len(status.models) == 0
        assert status.error == "Connection timed out"


@pytest.mark.asyncio
async def test_get_ollama_status_unexpected_status_code():
    """Test getting status when Ollama returns unexpected status code."""
    mock_response = Mock()
    mock_response.status_code = 500

    with patch("shotgun.tui.services.ollama.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__.return_value = mock_instance

        status = await get_ollama_status()

        assert status.running is False
        assert len(status.models) == 0
        assert "500" in status.error


@pytest.mark.asyncio
async def test_get_ollama_status_custom_url():
    """Test getting status with custom base URL."""
    mock_health_response = Mock()
    mock_health_response.status_code = 200

    mock_tags_response = Mock()
    mock_tags_response.json.return_value = {"models": []}
    mock_tags_response.raise_for_status = Mock()

    with patch("shotgun.tui.services.ollama.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(
            side_effect=[mock_health_response, mock_tags_response]
        )
        mock_client.return_value.__aenter__.return_value = mock_instance

        custom_url = "http://192.168.1.100:11434"
        await get_ollama_status(base_url=custom_url)

        # Verify custom URL was used
        calls = mock_instance.get.call_args_list
        assert calls[0][0][0] == f"{custom_url}/"
        assert calls[1][0][0] == f"{custom_url}/api/tags"


@pytest.mark.asyncio
async def test_get_ollama_status_models_api_error():
    """Test getting status when models API fails but health check passes."""
    mock_health_response = Mock()
    mock_health_response.status_code = 200

    mock_tags_response = Mock()
    mock_tags_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Server Error", request=Mock(), response=Mock(status_code=500)
    )

    with patch("shotgun.tui.services.ollama.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(
            side_effect=[mock_health_response, mock_tags_response]
        )
        mock_client.return_value.__aenter__.return_value = mock_instance

        status = await get_ollama_status()

        # Ollama is running but models couldn't be fetched
        assert status.running is True
        assert len(status.models) == 0
        assert "Failed to fetch models" in status.error


@pytest.mark.asyncio
async def test_get_ollama_status_malformed_model_data():
    """Test getting status when model data is malformed."""
    mock_health_response = Mock()
    mock_health_response.status_code = 200

    mock_tags_response = Mock()
    mock_tags_response.json.return_value = {
        "models": [
            {
                "name": "valid-model",
                "size": 1000,
                "modified_at": "2024-01-01T00:00:00Z",
            },
            {"bad_field": "missing required fields"},  # Malformed entry
            {
                "name": "another-valid",
                "size": 2000,
                "modified_at": "2024-01-02T00:00:00Z",
            },
        ]
    }
    mock_tags_response.raise_for_status = Mock()

    with patch("shotgun.tui.services.ollama.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(
            side_effect=[mock_health_response, mock_tags_response]
        )
        mock_client.return_value.__aenter__.return_value = mock_instance

        status = await get_ollama_status()

        # Should still succeed with valid models
        assert status.running is True
        assert len(status.models) >= 1  # At least the valid ones
        assert status.error is None


@pytest.mark.asyncio
async def test_get_ollama_status_request_error():
    """Test getting status with generic request error."""
    with patch("shotgun.tui.services.ollama.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(side_effect=httpx.RequestError("Generic error"))
        mock_client.return_value.__aenter__.return_value = mock_instance

        status = await get_ollama_status()

        assert status.running is False
        assert len(status.models) == 0
        assert status.error is not None


def test_default_ollama_url():
    """Test that default URL is correct."""
    assert DEFAULT_OLLAMA_URL == "http://localhost:11434"
