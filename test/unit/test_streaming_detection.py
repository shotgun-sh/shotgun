"""Unit tests for streaming capability detection."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from pydantic import SecretStr

from shotgun.agents.config.manager import ConfigManager
from shotgun.agents.config.models import (
    KeyProvider,
    ModelName,
    OpenAIConfig,
    ProviderType,
    ShotgunConfig,
)
from shotgun.agents.config.provider import get_provider_model
from shotgun.agents.config.streaming_test import (
    check_streaming_capability,
    check_streaming_capability_sync,
)


@pytest.mark.asyncio
async def test_check_streaming_capability_success():
    """Test successful streaming capability detection."""

    async def mock_aiter_bytes():
        yield b"data: test"

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.aiter_bytes = mock_aiter_bytes

    with patch("httpx.AsyncClient") as mock_client:
        mock_stream_context = AsyncMock()
        mock_stream_context.__aenter__.return_value = mock_response
        mock_stream_context.__aexit__.return_value = None

        mock_client_instance = MagicMock()
        mock_client_instance.stream.return_value = mock_stream_context
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        mock_client.return_value.__aexit__.return_value = None

        result = await check_streaming_capability("test-key", "gpt-5")
        assert result is True


@pytest.mark.asyncio
async def test_check_streaming_capability_failure_http_error():
    """Test streaming capability detection with HTTP error."""
    mock_response = MagicMock()
    mock_response.status_code = 403

    with patch("httpx.AsyncClient") as mock_client:
        mock_stream_context = AsyncMock()
        mock_stream_context.__aenter__.return_value = mock_response
        mock_stream_context.__aexit__.return_value = None

        mock_client_instance = MagicMock()
        mock_client_instance.stream.return_value = mock_stream_context
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        mock_client.return_value.__aexit__.return_value = None

        result = await check_streaming_capability("test-key", "gpt-5")
        assert result is False


@pytest.mark.asyncio
async def test_check_streaming_capability_timeout():
    """Test streaming capability detection with timeout."""
    with patch("httpx.AsyncClient") as mock_client:
        mock_client_instance = MagicMock()
        mock_client_instance.stream.side_effect = httpx.TimeoutException("Timeout")
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        mock_client.return_value.__aexit__.return_value = None

        result = await check_streaming_capability("test-key", "gpt-5")
        assert result is False


def test_check_streaming_capability_sync():
    """Test synchronous wrapper for streaming capability detection."""
    with patch(
        "shotgun.agents.config.streaming_test.check_streaming_capability"
    ) as mock_async:
        mock_async.return_value = True

        result = check_streaming_capability_sync("test-key", "gpt-5")
        # The sync wrapper should call the async function
        mock_async.assert_called_once_with("test-key", "gpt-5")


@pytest.mark.asyncio
async def test_get_provider_model_gpt5_byok_not_tested():
    """Test get_provider_model with GPT-5 BYOK when streaming not tested yet."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"

        # Create config with OpenAI API key but no streaming capability tested
        config = ShotgunConfig(
            openai=OpenAIConfig(api_key=SecretStr("test-key")),
            shotgun_instance_id="test-instance",
        )

        # Mock the singleton config manager
        with patch("shotgun.agents.config.provider.get_config_manager") as mock_get_mgr:
            manager = ConfigManager(config_path=config_path)
            await manager.save(config)
            mock_get_mgr.return_value = manager

            # Mock the streaming test to return True
            with patch(
                "shotgun.agents.config.provider.check_streaming_capability_sync"
            ) as mock_test:
                mock_test.return_value = True

                # Get the model config
                model_config = await get_provider_model(ModelName.GPT_5)

                # Verify streaming test was called
                mock_test.assert_called_once_with("test-key", "gpt-5")

                # Verify ModelConfig has correct settings
                assert model_config.name == ModelName.GPT_5
                assert model_config.provider == ProviderType.OPENAI
                assert model_config.key_provider == KeyProvider.BYOK
                assert model_config.supports_streaming is True

                # Verify config was updated
                updated_config = await manager.load(force_reload=True)
                assert updated_config.openai.gpt5_supports_streaming is True


@pytest.mark.asyncio
async def test_get_provider_model_gpt5_mini_byok_not_tested():
    """Test get_provider_model with GPT-5-Mini BYOK when streaming not tested yet."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"

        # Create config with OpenAI API key but no streaming capability tested
        config = ShotgunConfig(
            openai=OpenAIConfig(api_key=SecretStr("test-key")),
            shotgun_instance_id="test-instance",
        )

        # Mock the singleton config manager
        with patch("shotgun.agents.config.provider.get_config_manager") as mock_get_mgr:
            manager = ConfigManager(config_path=config_path)
            await manager.save(config)
            mock_get_mgr.return_value = manager

            # Mock the streaming test to return False
            with patch(
                "shotgun.agents.config.provider.check_streaming_capability_sync"
            ) as mock_test:
                mock_test.return_value = False

                # Get the model config
                model_config = await get_provider_model(ModelName.GPT_5_MINI)

                # Verify streaming test was called
                mock_test.assert_called_once_with("test-key", "gpt-5-mini")

                # Verify ModelConfig has correct settings
                assert model_config.name == ModelName.GPT_5_MINI
                assert model_config.provider == ProviderType.OPENAI
                assert model_config.key_provider == KeyProvider.BYOK
                assert model_config.supports_streaming is False

                # Verify config was updated
                updated_config = await manager.load(force_reload=True)
                assert updated_config.openai.gpt5_mini_supports_streaming is False


@pytest.mark.asyncio
async def test_get_provider_model_gpt5_byok_already_tested():
    """Test get_provider_model with GPT-5 BYOK when streaming already tested."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"

        # Create config with streaming capability already tested
        config = ShotgunConfig(
            openai=OpenAIConfig(
                api_key=SecretStr("test-key"), gpt5_supports_streaming=False
            ),
            shotgun_instance_id="test-instance",
        )

        # Mock the singleton config manager
        with patch("shotgun.agents.config.provider.get_config_manager") as mock_get_mgr:
            manager = ConfigManager(config_path=config_path)
            await manager.save(config)
            mock_get_mgr.return_value = manager

            # Mock the streaming test - should NOT be called
            with patch(
                "shotgun.agents.config.provider.check_streaming_capability_sync"
            ) as mock_test:
                # Get the model config
                model_config = await get_provider_model(ModelName.GPT_5)

                # Verify streaming test was NOT called (already tested)
                mock_test.assert_not_called()

                # Verify ModelConfig uses cached result
                assert model_config.supports_streaming is False


@pytest.mark.asyncio
async def test_get_provider_model_shotgun_always_streaming():
    """Test get_provider_model with Shotgun account always has streaming enabled."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"

        # Create config with Shotgun account
        from shotgun.agents.config.models import ShotgunAccountConfig

        config = ShotgunConfig(
            shotgun=ShotgunAccountConfig(api_key=SecretStr("shotgun-key")),
            shotgun_instance_id="test-instance",
        )

        # Mock the singleton config manager
        with patch("shotgun.agents.config.provider.get_config_manager") as mock_get_mgr:
            manager = ConfigManager(config_path=config_path)
            await manager.save(config)
            mock_get_mgr.return_value = manager

            # Get the model config for GPT-5
            model_config = await get_provider_model(ModelName.GPT_5)

            # Verify ModelConfig has streaming enabled
            assert model_config.key_provider == KeyProvider.SHOTGUN
            assert model_config.supports_streaming is True


@pytest.mark.asyncio
async def test_update_provider_resets_streaming_capabilities():
    """Test that updating OpenAI API key resets streaming capabilities."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        # Create config with streaming capabilities already set
        config = ShotgunConfig(
            openai=OpenAIConfig(
                api_key=SecretStr("old-key"),
                gpt5_supports_streaming=True,
                gpt5_mini_supports_streaming=False,
            ),
            shotgun_instance_id="test-instance",
        )
        await manager.save(config)

        # Update the API key
        await manager.update_provider(ProviderType.OPENAI, api_key="new-key")

        # Verify streaming capabilities were reset
        updated_config = await manager.load(force_reload=True)
        assert updated_config.openai.gpt5_supports_streaming is None
        assert updated_config.openai.gpt5_mini_supports_streaming is None


@pytest.mark.asyncio
async def test_clear_provider_key_resets_streaming_capabilities():
    """Test that clearing OpenAI API key resets streaming capabilities."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        # Create config with streaming capabilities already set
        config = ShotgunConfig(
            openai=OpenAIConfig(
                api_key=SecretStr("test-key"),
                gpt5_supports_streaming=True,
                gpt5_mini_supports_streaming=False,
            ),
            shotgun_instance_id="test-instance",
        )
        await manager.save(config)

        # Clear the API key
        await manager.clear_provider_key(ProviderType.OPENAI)

        # Verify streaming capabilities were reset
        updated_config = await manager.load(force_reload=True)
        assert updated_config.openai.api_key is None
        assert updated_config.openai.gpt5_supports_streaming is None
        assert updated_config.openai.gpt5_mini_supports_streaming is None
