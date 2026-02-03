"""Unit tests for the LM Studio service."""

from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from shotgun.tui.services.lm_studio import (
    DEFAULT_LM_STUDIO_URL,
    LMStudioModel,
    LMStudioStatus,
    get_lm_studio_status,
    sanitize_lm_studio_model_name_for_id,
)


def test_lm_studio_model_creation():
    """Test LMStudioModel Pydantic model."""
    model = LMStudioModel(
        id="lmstudio-community/Meta-Llama-3-8B-Instruct-GGUF",
        object="model",
        owned_by="lmstudio",
    )
    assert model.id == "lmstudio-community/Meta-Llama-3-8B-Instruct-GGUF"
    assert model.name == "lmstudio-community/Meta-Llama-3-8B-Instruct-GGUF"
    assert model.object == "model"
    assert model.owned_by == "lmstudio"


def test_lm_studio_model_supports_tools():
    """Test LMStudioModel always reports tool support."""
    model = LMStudioModel(id="any-model")
    assert model.supports_tools is True


def test_lm_studio_model_supports_vision():
    """Test LMStudioModel conservatively reports no vision support."""
    model = LMStudioModel(id="any-model")
    assert model.supports_vision is False


def test_lm_studio_status_creation():
    """Test LMStudioStatus Pydantic model."""
    status = LMStudioStatus(running=True, models=[])
    assert status.running is True
    assert status.models == []
    assert status.error is None

    status_with_error = LMStudioStatus(
        running=False, models=[], error="Connection refused"
    )
    assert status_with_error.running is False
    assert status_with_error.error == "Connection refused"


@pytest.mark.asyncio
async def test_get_lm_studio_status_running_with_models():
    """Test getting status when LM Studio is running with models."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "object": "list",
        "data": [
            {
                "id": "lmstudio-community/Meta-Llama-3-8B-Instruct-GGUF",
                "object": "model",
                "owned_by": "lmstudio",
            },
            {
                "id": "TheBloke/Mistral-7B-Instruct-v0.2-GGUF",
                "object": "model",
                "owned_by": "lmstudio",
            },
        ],
    }

    with patch("shotgun.tui.services.lm_studio.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__.return_value = mock_instance

        status = await get_lm_studio_status()

        assert status.running is True
        assert len(status.models) == 2
        assert status.models[0].id == "lmstudio-community/Meta-Llama-3-8B-Instruct-GGUF"
        assert status.models[1].id == "TheBloke/Mistral-7B-Instruct-v0.2-GGUF"
        assert status.error is None


@pytest.mark.asyncio
async def test_get_lm_studio_status_running_no_models():
    """Test getting status when LM Studio is running but has no models."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"object": "list", "data": []}

    with patch("shotgun.tui.services.lm_studio.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__.return_value = mock_instance

        status = await get_lm_studio_status()

        assert status.running is True
        assert len(status.models) == 0
        assert status.error is None


@pytest.mark.asyncio
async def test_get_lm_studio_status_not_running():
    """Test getting status when LM Studio is not running."""
    with patch("shotgun.tui.services.lm_studio.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        mock_client.return_value.__aenter__.return_value = mock_instance

        status = await get_lm_studio_status()

        assert status.running is False
        assert len(status.models) == 0
        assert status.error == "LM Studio is not running"


@pytest.mark.asyncio
async def test_get_lm_studio_status_timeout():
    """Test getting status when connection times out."""
    with patch("shotgun.tui.services.lm_studio.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
        mock_client.return_value.__aenter__.return_value = mock_instance

        status = await get_lm_studio_status()

        assert status.running is False
        assert len(status.models) == 0
        assert status.error == "Connection timed out"


@pytest.mark.asyncio
async def test_get_lm_studio_status_unexpected_status_code():
    """Test getting status when LM Studio returns unexpected status code."""
    mock_response = Mock()
    mock_response.status_code = 500

    with patch("shotgun.tui.services.lm_studio.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__.return_value = mock_instance

        status = await get_lm_studio_status()

        assert status.running is False
        assert len(status.models) == 0
        assert "500" in status.error


@pytest.mark.asyncio
async def test_get_lm_studio_status_custom_url():
    """Test getting status with custom base URL."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"object": "list", "data": []}

    with patch("shotgun.tui.services.lm_studio.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__.return_value = mock_instance

        custom_url = "http://192.168.1.100:1234"
        await get_lm_studio_status(base_url=custom_url)

        # Verify custom URL was used
        calls = mock_instance.get.call_args_list
        assert calls[0][0][0] == f"{custom_url}/v1/models"


@pytest.mark.asyncio
async def test_get_lm_studio_status_malformed_model_data():
    """Test getting status when model data is malformed."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "object": "list",
        "data": [
            {
                "id": "valid-model",
                "object": "model",
            },
            {"bad_field": "missing id"},  # Malformed entry
            {
                "id": "another-valid",
                "object": "model",
            },
        ],
    }

    with patch("shotgun.tui.services.lm_studio.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__.return_value = mock_instance

        status = await get_lm_studio_status()

        # Should still succeed with valid models
        assert status.running is True
        assert len(status.models) >= 1  # At least the valid ones
        assert status.error is None


@pytest.mark.asyncio
async def test_get_lm_studio_status_request_error():
    """Test getting status with generic request error."""
    with patch("shotgun.tui.services.lm_studio.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(side_effect=httpx.RequestError("Generic error"))
        mock_client.return_value.__aenter__.return_value = mock_instance

        status = await get_lm_studio_status()

        assert status.running is False
        assert len(status.models) == 0
        assert status.error is not None


def test_default_lm_studio_url():
    """Test that default URL is correct."""
    assert DEFAULT_LM_STUDIO_URL == "http://localhost:1234"


def test_sanitize_lm_studio_model_name_for_id_replaces_colon():
    """Test that colons are replaced with hyphens."""
    assert sanitize_lm_studio_model_name_for_id("model:version") == "model-version"


def test_sanitize_lm_studio_model_name_for_id_replaces_slash():
    """Test that slashes are replaced with hyphens."""
    assert (
        sanitize_lm_studio_model_name_for_id("lmstudio-community/Meta-Llama-3")
        == "lmstudio-community-Meta-Llama-3"
    )


def test_sanitize_lm_studio_model_name_for_id_replaces_dot():
    """Test that dots are replaced with hyphens."""
    assert sanitize_lm_studio_model_name_for_id("model.v1") == "model-v1"


def test_sanitize_lm_studio_model_name_for_id_replaces_multiple_chars():
    """Test that multiple special characters are all replaced."""
    assert sanitize_lm_studio_model_name_for_id("lib/model:v1.0") == "lib-model-v1-0"


def test_sanitize_lm_studio_model_name_for_id_preserves_hyphens():
    """Test that existing hyphens are preserved."""
    assert sanitize_lm_studio_model_name_for_id("my-model") == "my-model"
