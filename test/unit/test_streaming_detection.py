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
from shotgun.agents.config.streaming_test import check_streaming_capability


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

        result = await check_streaming_capability("test-key", "gpt-5", max_attempts=1)
        assert result is True


@pytest.mark.asyncio
async def test_check_streaming_capability_failure_http_error():
    """Test streaming capability detection with HTTP error (403 = definitive failure)."""
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

        # 403 is a definitive error - should fail immediately without retries
        result = await check_streaming_capability("test-key", "gpt-5", max_attempts=3)
        assert result is False


@pytest.mark.asyncio
async def test_check_streaming_capability_timeout():
    """Test streaming capability detection with timeout (retries then fails)."""
    with patch("httpx.AsyncClient") as mock_client:
        mock_client_instance = MagicMock()
        mock_client_instance.stream.side_effect = httpx.TimeoutException("Timeout")
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        mock_client.return_value.__aexit__.return_value = None

        # Should retry 3 times and then fail
        result = await check_streaming_capability("test-key", "gpt-5", max_attempts=3)
        assert result is False


@pytest.mark.asyncio
async def test_check_streaming_capability_retry_success():
    """Test streaming capability succeeds after initial failures."""

    async def mock_aiter_bytes():
        yield b"data: test"

    # First attempt fails with 500, second attempt succeeds
    mock_response_fail = MagicMock()
    mock_response_fail.status_code = 500

    mock_response_success = MagicMock()
    mock_response_success.status_code = 200
    mock_response_success.aiter_bytes = mock_aiter_bytes

    with patch("httpx.AsyncClient") as mock_client:
        mock_stream_context_fail = AsyncMock()
        mock_stream_context_fail.__aenter__.return_value = mock_response_fail
        mock_stream_context_fail.__aexit__.return_value = None

        mock_stream_context_success = AsyncMock()
        mock_stream_context_success.__aenter__.return_value = mock_response_success
        mock_stream_context_success.__aexit__.return_value = None

        mock_client_instance = MagicMock()
        # First call returns 500, second call returns 200
        mock_client_instance.stream.side_effect = [
            mock_stream_context_fail,
            mock_stream_context_success,
        ]
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        mock_client.return_value.__aexit__.return_value = None

        # Should succeed on second attempt
        result = await check_streaming_capability("test-key", "gpt-5", max_attempts=3)
        assert result is True


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
                "shotgun.agents.config.provider.check_streaming_capability"
            ) as mock_test:
                mock_test.return_value = True

                # Get the model config
                model_config = await get_provider_model(ModelName.GPT_5_1)

                # Verify streaming test was called
                mock_test.assert_called_once_with("test-key", "gpt-5.1")

                # Verify ModelConfig has correct settings
                assert model_config.name == ModelName.GPT_5_1
                assert model_config.provider == ProviderType.OPENAI
                assert model_config.key_provider == KeyProvider.BYOK
                assert model_config.supports_streaming is True

                # Verify config was updated
                updated_config = await manager.load(force_reload=True)
                assert updated_config.openai.supports_streaming is True


@pytest.mark.asyncio
async def test_get_provider_model_gpt5_2_byok_not_tested():
    """Test get_provider_model with GPT-5.2 BYOK when streaming not tested yet."""
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
                "shotgun.agents.config.provider.check_streaming_capability"
            ) as mock_test:
                mock_test.return_value = False

                # Get the model config
                model_config = await get_provider_model(ModelName.GPT_5_2)

                # Verify streaming test was called
                mock_test.assert_called_once_with("test-key", "gpt-5.2")

                # Verify ModelConfig has correct settings
                assert model_config.name == ModelName.GPT_5_2
                assert model_config.provider == ProviderType.OPENAI
                assert model_config.key_provider == KeyProvider.BYOK
                assert model_config.supports_streaming is False

                # Verify config was updated
                updated_config = await manager.load(force_reload=True)
                assert updated_config.openai.supports_streaming is False


@pytest.mark.asyncio
async def test_get_provider_model_gpt5_1_byok_already_tested():
    """Test get_provider_model with GPT-5.1 BYOK when streaming already tested."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"

        # Create config with streaming capability already tested
        config = ShotgunConfig(
            openai=OpenAIConfig(
                api_key=SecretStr("test-key"), supports_streaming=False
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
                "shotgun.agents.config.provider.check_streaming_capability"
            ) as mock_test:
                # Get the model config
                model_config = await get_provider_model(ModelName.GPT_5_1)

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

            # Get the model config for GPT-5.1
            model_config = await get_provider_model(ModelName.GPT_5_1)

            # Verify ModelConfig has streaming enabled
            assert model_config.key_provider == KeyProvider.SHOTGUN
            assert model_config.supports_streaming is True


@pytest.mark.asyncio
async def test_update_provider_resets_streaming_capabilities():
    """Test that updating OpenAI API key resets streaming capabilities."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        # Create config with streaming capability already set
        config = ShotgunConfig(
            openai=OpenAIConfig(
                api_key=SecretStr("old-key"),
                supports_streaming=True,
            ),
            shotgun_instance_id="test-instance",
        )
        await manager.save(config)

        # Update the API key
        await manager.update_provider(ProviderType.OPENAI, api_key="new-key")

        # Verify streaming capability was reset
        updated_config = await manager.load(force_reload=True)
        assert updated_config.openai.supports_streaming is None


@pytest.mark.asyncio
async def test_clear_provider_key_resets_streaming_capabilities():
    """Test that clearing OpenAI API key resets streaming capabilities."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        # Create config with streaming capability already set
        config = ShotgunConfig(
            openai=OpenAIConfig(
                api_key=SecretStr("test-key"),
                supports_streaming=True,
            ),
            shotgun_instance_id="test-instance",
        )
        await manager.save(config)

        # Clear the API key
        await manager.clear_provider_key(ProviderType.OPENAI)

        # Verify streaming capability was reset
        updated_config = await manager.load(force_reload=True)
        assert updated_config.openai.api_key is None
        assert updated_config.openai.supports_streaming is None
