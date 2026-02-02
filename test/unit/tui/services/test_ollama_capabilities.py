"""Unit tests for Ollama model capabilities."""

from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest

from shotgun.tui.services.ollama import (
    OllamaModel,
    get_model_capabilities,
)


def test_ollama_model_supports_vision_true():
    """Test supports_vision property returns True when vision capability is present."""
    model = OllamaModel(
        name="llava:7b",
        size=4700000000,
        modified_at=datetime(2024, 1, 1, 0, 0, 0),
        capabilities=["completion", "vision"],
    )
    assert model.supports_vision is True


def test_ollama_model_supports_vision_false():
    """Test supports_vision property returns False when vision capability is absent."""
    model = OllamaModel(
        name="llama3:8b",
        size=4700000000,
        modified_at=datetime(2024, 1, 1, 0, 0, 0),
        capabilities=["completion"],
    )
    assert model.supports_vision is False


def test_ollama_model_supports_vision_empty_capabilities():
    """Test supports_vision property returns False when capabilities is empty."""
    model = OllamaModel(
        name="some-model",
        size=1000000,
        modified_at=datetime(2024, 1, 1, 0, 0, 0),
        capabilities=[],
    )
    assert model.supports_vision is False


def test_ollama_model_default_capabilities():
    """Test that OllamaModel defaults to empty capabilities list."""
    model = OllamaModel(
        name="test-model",
        size=1000000,
        modified_at=datetime(2024, 1, 1, 0, 0, 0),
    )
    assert model.capabilities == []
    assert model.supports_vision is False


@pytest.mark.asyncio
async def test_get_model_capabilities_from_capabilities_field():
    """Test getting capabilities when model returns capabilities directly."""
    mock_client = AsyncMock()
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "capabilities": ["completion", "vision"],
    }
    mock_client.post = AsyncMock(return_value=mock_response)

    capabilities = await get_model_capabilities(
        "http://localhost:11434", "llava:7b", mock_client
    )

    assert capabilities == ["completion", "vision"]
    mock_client.post.assert_called_once_with(
        "http://localhost:11434/api/show",
        json={"name": "llava:7b"},
    )


@pytest.mark.asyncio
async def test_get_model_capabilities_from_model_info_with_vision():
    """Test getting capabilities when vision is detected from model_info."""
    mock_client = AsyncMock()
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "model_info": {
            "general.architecture": "clip",
            "some_other_field": "value",
        },
    }
    mock_client.post = AsyncMock(return_value=mock_response)

    capabilities = await get_model_capabilities(
        "http://localhost:11434", "llava:7b", mock_client
    )

    assert "vision" in capabilities
    assert "completion" in capabilities


@pytest.mark.asyncio
async def test_get_model_capabilities_from_model_info_without_vision():
    """Test getting capabilities when no vision markers in model_info."""
    mock_client = AsyncMock()
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "model_info": {
            "general.architecture": "llama",
            "some_field": "value",
        },
    }
    mock_client.post = AsyncMock(return_value=mock_response)

    capabilities = await get_model_capabilities(
        "http://localhost:11434", "llama3:8b", mock_client
    )

    assert capabilities == ["completion"]
    assert "vision" not in capabilities


@pytest.mark.asyncio
async def test_get_model_capabilities_api_error():
    """Test getting capabilities returns empty list on API error."""
    mock_client = AsyncMock()
    mock_response = Mock()
    mock_response.status_code = 404
    mock_client.post = AsyncMock(return_value=mock_response)

    capabilities = await get_model_capabilities(
        "http://localhost:11434", "nonexistent:model", mock_client
    )

    assert capabilities == []


@pytest.mark.asyncio
async def test_get_model_capabilities_exception():
    """Test getting capabilities returns empty list on exception."""
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=Exception("Connection error"))

    capabilities = await get_model_capabilities(
        "http://localhost:11434", "some-model", mock_client
    )

    assert capabilities == []
