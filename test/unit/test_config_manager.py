"""Unit tests for ConfigManager."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import SecretStr

from shotgun.agents.config.constants import (
    API_KEY_FIELD,
    CONFIG_VERSION_FIELD,
    SHOTGUN_INSTANCE_ID_FIELD,
    ConfigSection,
)
from shotgun.agents.config.manager import (
    CURRENT_CONFIG_VERSION,
    ConfigManager,
    get_config_manager,
)
from shotgun.agents.config.models import (
    AnthropicConfig,
    GoogleConfig,
    ModelConfig,
    ModelName,
    OpenAIConfig,
    ProviderType,
    ShotgunConfig,
)
from shotgun.agents.config.provider import get_provider_model


@pytest.mark.smoke
def test_init_default_path(monkeypatch):
    """Test ConfigManager initialization with default path."""
    # Clear any SHOTGUN_HOME env var for this test
    monkeypatch.delenv("SHOTGUN_HOME", raising=False)

    manager = ConfigManager()
    # Verify the path ends with the expected components
    assert manager.config_path.name == "config.json"
    assert manager.config_path.parent.name == ".shotgun-sh"
    assert manager._config is None


def test_init_custom_path():
    """Test ConfigManager initialization with custom path."""
    custom_path = Path("/custom/config.json")
    manager = ConfigManager(config_path=custom_path)
    assert manager.config_path == custom_path
    assert manager._config is None


@patch("shotgun.agents.config.manager.logger")
@pytest.mark.asyncio
async def test_load_config_not_exists(mock_logger):
    """Test loading config when file doesn't exist."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "nonexistent.json"
        manager = ConfigManager(config_path=config_path)

        config = await manager.load()

        assert isinstance(config, ShotgunConfig)
        assert config.selected_model is None
        assert manager._config is config
        # Now creates new config with user_id, so we get two log messages
        assert mock_logger.info.call_count == 2
        assert hasattr(config, "shotgun_instance_id")
        assert config.shotgun_instance_id is not None
        assert hasattr(config, "config_version")
        assert config.config_version == CURRENT_CONFIG_VERSION


@patch("shotgun.agents.config.manager.logger")
@pytest.mark.asyncio
async def test_load_config_cached(mock_logger):
    """Test loading config returns cached version when force_reload=False."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "nonexistent.json"
        manager = ConfigManager(config_path=config_path)

        # Use force_reload=False to test caching behavior
        config1 = await manager.load(force_reload=False)
        config2 = await manager.load(force_reload=False)

        assert config1 is config2
        # First load creates config with user_id (2 log messages)
        # Second load returns cached config (no additional log messages)
        assert mock_logger.info.call_count == 2


@patch("shotgun.agents.config.manager.logger")
@pytest.mark.asyncio
async def test_load_config_valid_file(mock_logger):
    """Test loading config from valid file."""
    import uuid

    config_data = {
        ConfigSection.OPENAI.value: {API_KEY_FIELD: "test-openai-key"},
        ConfigSection.ANTHROPIC.value: {API_KEY_FIELD: "test-anthropic-key"},
        ConfigSection.GOOGLE.value: {API_KEY_FIELD: "test-google-key"},
        ConfigSection.SHOTGUN.value: {},
        "selected_model": "claude-sonnet-4-5",
        SHOTGUN_INSTANCE_ID_FIELD: str(uuid.uuid4()),
        CONFIG_VERSION_FIELD: 3,
    }

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as temp_file:
        json.dump(config_data, temp_file)
        temp_file.flush()

        try:
            manager = ConfigManager(config_path=Path(temp_file.name))
            config = await manager.load()

            assert isinstance(config, ShotgunConfig)
            assert config.selected_model == ModelName.CLAUDE_SONNET_4_5
            assert isinstance(config.openai.api_key, SecretStr)
            assert config.openai.api_key.get_secret_value() == "test-openai-key"
            assert isinstance(config.anthropic.api_key, SecretStr)
            assert config.anthropic.api_key.get_secret_value() == "test-anthropic-key"
            assert isinstance(config.google.api_key, SecretStr)
            assert config.google.api_key.get_secret_value() == "test-google-key"

            mock_logger.debug.assert_called_once_with(
                "Configuration loaded successfully from %s", Path(temp_file.name)
            )
        finally:
            os.unlink(temp_file.name)


@pytest.mark.asyncio
async def test_load_config_invalid_json():
    """Test loading config from invalid JSON file auto-recovers with fresh config."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as temp_file:
        temp_file.write("invalid json")
        temp_file.flush()

        try:
            manager = ConfigManager(config_path=Path(temp_file.name))

            # Should auto-recover by creating fresh config
            config = await manager.load()

            # Verify fresh config was created with migration failure flag
            assert isinstance(config, ShotgunConfig)
            assert config.migration_failed is True
            assert config.migration_backup_path is not None
            assert hasattr(config, "shotgun_instance_id")
            assert config.shotgun_instance_id is not None
        finally:
            os.unlink(temp_file.name)


@patch("shotgun.agents.config.manager.logger")
@pytest.mark.asyncio
async def test_save_config_with_argument(mock_logger):
    """Test saving config with explicit config argument."""
    import uuid

    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "test_config.json"
        manager = ConfigManager(config_path=config_path)

        config = ShotgunConfig(
            selected_model=ModelName.CLAUDE_SONNET_4_5,
            openai=OpenAIConfig(api_key=SecretStr("test-key")),
            shotgun_instance_id=str(uuid.uuid4()),
        )

        await manager.save(config)

        assert config_path.exists()
        with open(config_path, encoding="utf-8") as f:
            saved_data = json.load(f)

        assert saved_data["selected_model"] == "claude-sonnet-4-5"
        assert saved_data["openai"]["api_key"] == "test-key"
        assert manager._config is config
        mock_logger.debug.assert_called_once_with(
            "Configuration saved to %s", config_path
        )


@patch("shotgun.agents.config.manager.logger")
@pytest.mark.asyncio
async def test_save_config_without_argument(mock_logger):
    """Test saving config without explicit config argument."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "test_config.json"
        manager = ConfigManager(config_path=config_path)

        # Load default config first
        await manager.load()

        await manager.save()

        assert config_path.exists()
        # Multiple log calls due to initialize() and save()
        assert mock_logger.debug.call_count >= 1


@patch("shotgun.agents.config.manager.logger")
@pytest.mark.asyncio
async def test_save_config_creates_directory(mock_logger):
    """Test saving config creates parent directory if it doesn't exist."""
    import uuid

    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "nested" / "dir" / "config.json"
        manager = ConfigManager(config_path=config_path)

        config = ShotgunConfig(
            shotgun_instance_id=str(uuid.uuid4()),
        )
        await manager.save(config)

        assert config_path.exists()
        assert config_path.parent.exists()


@patch("shotgun.agents.config.manager.logger")
@pytest.mark.asyncio
async def test_save_config_failure(mock_logger):
    """Test save config handles file write errors."""
    import uuid

    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "readonly" / "config.json"
        # Create readonly parent directory
        config_path.parent.mkdir()
        config_path.parent.chmod(0o444)

        manager = ConfigManager(config_path=config_path)
        config = ShotgunConfig(
            shotgun_instance_id=str(uuid.uuid4()),
        )

        try:
            with pytest.raises((OSError, PermissionError)):
                await manager.save(config)

            mock_logger.error.assert_called_once()
        finally:
            # Cleanup - restore write permissions
            config_path.parent.chmod(0o755)


@patch.dict(os.environ, {}, clear=True)
@patch("shotgun.agents.config.provider.get_config_manager")
@pytest.mark.asyncio
async def test_get_provider_model_openai_with_config_key(mock_get_config_manager):
    """Test get_provider_model for OpenAI with API key in config."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        # Set cached config directly
        import uuid

        config = ShotgunConfig(
            openai=OpenAIConfig(api_key=SecretStr("test-openai-key")),
            shotgun_instance_id=str(uuid.uuid4()),
        )
        manager._config = config
        mock_get_config_manager.return_value = manager

        model = await get_provider_model(ProviderType.OPENAI)

        assert isinstance(model, ModelConfig)
        assert model.name == "gpt-5.2"
        assert model.api_key == "test-openai-key"


@patch.dict(os.environ, {}, clear=True)
@patch("shotgun.agents.config.provider.get_config_manager")
@pytest.mark.asyncio
async def test_get_provider_model_openai_no_key(mock_get_config_manager):
    """Test get_provider_model for OpenAI with no API key."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)
        mock_get_config_manager.return_value = manager

        with pytest.raises(ValueError, match="OpenAI API key not configured"):
            await get_provider_model(ProviderType.OPENAI)


@patch.dict(os.environ, {}, clear=True)
@patch("shotgun.agents.config.provider.get_config_manager")
@pytest.mark.asyncio
async def test_get_provider_model_anthropic_with_config_key(mock_get_config_manager):
    """Test get_provider_model for Anthropic with API key in config."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        # Set cached config directly
        import uuid

        config = ShotgunConfig(
            anthropic=AnthropicConfig(api_key=SecretStr("test-anthropic-key")),
            shotgun_instance_id=str(uuid.uuid4()),
        )
        manager._config = config
        mock_get_config_manager.return_value = manager

        model = await get_provider_model(ProviderType.ANTHROPIC)

        assert isinstance(model, ModelConfig)
        assert model.name == "claude-opus-4-5"
        assert model.api_key == "test-anthropic-key"


@patch.dict(os.environ, {}, clear=True)
@patch("shotgun.agents.config.provider.get_config_manager")
@pytest.mark.asyncio
async def test_get_provider_model_anthropic_no_key(mock_get_config_manager):
    """Test get_provider_model for Anthropic with no API key."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)
        mock_get_config_manager.return_value = manager

        with pytest.raises(ValueError, match="Anthropic API key not configured"):
            await get_provider_model(ProviderType.ANTHROPIC)


@patch.dict(os.environ, {}, clear=True)
@patch("shotgun.agents.config.provider.get_config_manager")
@pytest.mark.asyncio
async def test_get_provider_model_google_with_config_key(mock_get_config_manager):
    """Test get_provider_model for Google with API key in config."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        # Set cached config directly
        import uuid

        config = ShotgunConfig(
            google=GoogleConfig(api_key=SecretStr("test-google-key")),
            shotgun_instance_id=str(uuid.uuid4()),
        )
        manager._config = config
        mock_get_config_manager.return_value = manager

        model = await get_provider_model(ProviderType.GOOGLE)

        assert isinstance(model, ModelConfig)
        assert model.name == "gemini-3-pro-preview"
        assert model.api_key == "test-google-key"


@patch.dict(os.environ, {}, clear=True)
@patch("shotgun.agents.config.provider.get_config_manager")
@pytest.mark.asyncio
async def test_get_provider_model_google_no_key(mock_get_config_manager):
    """Test get_provider_model for Google with no API key."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)
        mock_get_config_manager.return_value = manager

        with pytest.raises(ValueError, match="Gemini API key not configured"):
            await get_provider_model(ProviderType.GOOGLE)


@patch("shotgun.agents.config.provider.get_config_manager")
@pytest.mark.asyncio
async def test_get_provider_model_string_provider(mock_get_config_manager):
    """Test get_provider_model with string provider argument."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        # Set cached config directly
        import uuid

        config = ShotgunConfig(
            openai=OpenAIConfig(api_key=SecretStr("test-key")),
            shotgun_instance_id=str(uuid.uuid4()),
        )
        manager._config = config
        mock_get_config_manager.return_value = manager

        model = await get_provider_model("openai")

        assert isinstance(model, ModelConfig)
        assert model.name == "gpt-5.2"


@patch("shotgun.agents.config.provider.get_config_manager")
@pytest.mark.asyncio
async def test_get_provider_model_none_finds_first_available(mock_get_config_manager):
    """Test get_provider_model with None provider finds first available."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        # Set cached config directly - only Anthropic has a key
        import uuid

        config = ShotgunConfig(
            anthropic=AnthropicConfig(api_key=SecretStr("test-key")),
            shotgun_instance_id=str(uuid.uuid4()),
        )
        manager._config = config
        mock_get_config_manager.return_value = manager

        model = await get_provider_model(None)

        assert isinstance(model, ModelConfig)
        assert model.name == "claude-opus-4-5"


@patch("shotgun.agents.config.provider.get_config_manager")
@pytest.mark.asyncio
async def test_get_provider_model_respects_selected_model(mock_get_config_manager):
    """Test get_provider_model respects selected_model when provider has key."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        import uuid

        # User has selected Opus but also has OpenAI key (which would be first provider)
        config = ShotgunConfig(
            openai=OpenAIConfig(api_key=SecretStr("openai-key")),
            anthropic=AnthropicConfig(api_key=SecretStr("anthropic-key")),
            selected_model=ModelName.CLAUDE_OPUS_4_5,
            shotgun_instance_id=str(uuid.uuid4()),
        )
        manager._config = config
        mock_get_config_manager.return_value = manager

        model = await get_provider_model(None)

        # Should respect selected_model (Opus) not fall back to first provider (OpenAI)
        assert isinstance(model, ModelConfig)
        assert model.name == ModelName.CLAUDE_OPUS_4_5


@patch("shotgun.agents.config.provider.get_config_manager")
@pytest.mark.asyncio
async def test_get_provider_model_falls_back_when_selected_model_provider_has_no_key(
    mock_get_config_manager,
):
    """Test get_provider_model falls back when selected model's provider has no key."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        import uuid

        # User has selected Opus but only has OpenAI key (Anthropic has no key)
        config = ShotgunConfig(
            openai=OpenAIConfig(api_key=SecretStr("openai-key")),
            selected_model=ModelName.CLAUDE_OPUS_4_5,
            shotgun_instance_id=str(uuid.uuid4()),
        )
        manager._config = config
        mock_get_config_manager.return_value = manager

        model = await get_provider_model(None)

        # Should fall back to OpenAI since Anthropic has no key
        assert isinstance(model, ModelConfig)
        assert model.name == ModelName.GPT_5_2


@patch("shotgun.agents.config.provider.get_config_manager")
@pytest.mark.asyncio
async def test_get_provider_model_unsupported_provider(mock_get_config_manager):
    """Test get_provider_model with unsupported provider."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)
        mock_get_config_manager.return_value = manager

        with pytest.raises(ValueError, match="is not a valid ProviderType"):
            await get_provider_model("unsupported")


@pytest.mark.asyncio
async def test_update_provider_openai():
    """Test updating OpenAI provider configuration."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        await manager.update_provider(
            ProviderType.OPENAI, **{API_KEY_FIELD: "new-openai-key"}
        )

        # Verify config was updated and saved
        assert config_path.exists()
        with open(config_path, encoding="utf-8") as f:
            saved_data = json.load(f)

        assert saved_data["openai"]["api_key"] == "new-openai-key"


@pytest.mark.asyncio
async def test_update_provider_anthropic_string():
    """Test updating Anthropic provider with string provider type."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        await manager.update_provider(
            "anthropic", **{API_KEY_FIELD: "new-anthropic-key"}
        )

        # Verify config was updated and saved
        assert config_path.exists()
        with open(config_path, encoding="utf-8") as f:
            saved_data = json.load(f)

        assert saved_data["anthropic"]["api_key"] == "new-anthropic-key"


@pytest.mark.asyncio
async def test_update_provider_google():
    """Test updating Google provider configuration."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        await manager.update_provider(
            ProviderType.GOOGLE, **{API_KEY_FIELD: "new-google-key"}
        )

        # Verify config was updated and saved
        assert config_path.exists()
        with open(config_path, encoding="utf-8") as f:
            saved_data = json.load(f)

        assert saved_data["google"]["api_key"] == "new-google-key"


@pytest.mark.asyncio
async def test_update_provider_none_api_key():
    """Test updating provider with None API key is ignored."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        # This should not raise an error and should save default config
        await manager.update_provider(ProviderType.OPENAI, **{API_KEY_FIELD: None})

        assert config_path.exists()


@pytest.mark.asyncio
async def test_update_provider_unsupported_fields():
    """Test updating provider with unsupported fields raises error."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        with pytest.raises(ValueError, match="Unsupported configuration fields"):
            await manager.update_provider(
                ProviderType.OPENAI, api_key="key", model="gpt-4"
            )


@pytest.mark.asyncio
async def test_update_provider_unsupported_provider():
    """Test updating unsupported provider raises error."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        with pytest.raises(ValueError, match="is not a valid ProviderType"):
            await manager.update_provider("unsupported", api_key="key")


@pytest.mark.asyncio
async def test_clear_provider_key_openai():
    """Test clearing OpenAI provider API key."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        # First set a key
        await manager.update_provider(ProviderType.OPENAI, api_key="test-key")
        assert await manager.has_provider_key(ProviderType.OPENAI)

        # Now clear it
        await manager.clear_provider_key(ProviderType.OPENAI)

        # Verify key is cleared
        assert not await manager.has_provider_key(ProviderType.OPENAI)

        # Verify config file was updated
        with open(config_path, encoding="utf-8") as f:
            saved_data = json.load(f)
        assert saved_data["openai"]["api_key"] is None


@pytest.mark.asyncio
async def test_clear_provider_key_anthropic():
    """Test clearing Anthropic provider API key."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        # First set a key
        await manager.update_provider(ProviderType.ANTHROPIC, api_key="test-key")
        assert await manager.has_provider_key(ProviderType.ANTHROPIC)

        # Now clear it
        await manager.clear_provider_key(ProviderType.ANTHROPIC)

        # Verify key is cleared
        assert not await manager.has_provider_key(ProviderType.ANTHROPIC)

        # Verify config file was updated
        with open(config_path, encoding="utf-8") as f:
            saved_data = json.load(f)
        assert saved_data["anthropic"]["api_key"] is None


@pytest.mark.asyncio
async def test_clear_provider_key_google():
    """Test clearing Google provider API key."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        # First set a key
        await manager.update_provider(ProviderType.GOOGLE, api_key="test-key")
        assert await manager.has_provider_key(ProviderType.GOOGLE)

        # Now clear it
        await manager.clear_provider_key(ProviderType.GOOGLE)

        # Verify key is cleared
        assert not await manager.has_provider_key(ProviderType.GOOGLE)

        # Verify config file was updated
        with open(config_path, encoding="utf-8") as f:
            saved_data = json.load(f)
        assert saved_data["google"]["api_key"] is None


@pytest.mark.asyncio
async def test_clear_provider_key_shotgun():
    """Test clearing Shotgun Account API key and JWT."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        # First set both api_key and supabase_jwt using update_shotgun_account
        await manager.update_shotgun_account(
            api_key="test-api-key", supabase_jwt="test-jwt-token"
        )

        # Verify both are set by checking config directly
        config = await manager.load(force_reload=True)
        assert manager.provider_has_api_key(config.shotgun)
        assert config.shotgun.supabase_jwt is not None
        assert config.shotgun.supabase_jwt.get_secret_value() == "test-jwt-token"

        # Now clear it
        await manager.clear_provider_key("shotgun")

        # Verify both api_key and supabase_jwt are cleared
        config = await manager.load(force_reload=True)
        assert not manager.provider_has_api_key(config.shotgun)
        assert config.shotgun.supabase_jwt is None

        # Verify config file was updated
        with open(config_path, encoding="utf-8") as f:
            saved_data = json.load(f)
        assert saved_data["shotgun"]["api_key"] is None
        assert saved_data["shotgun"]["supabase_jwt"] is None


@pytest.mark.asyncio
async def test_clear_provider_key_string_provider():
    """Test clearing provider key with string provider type."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        # First set a key using string
        await manager.update_provider("anthropic", api_key="test-key")
        assert await manager.has_provider_key("anthropic")

        # Now clear it using string
        await manager.clear_provider_key("anthropic")

        # Verify key is cleared
        assert not await manager.has_provider_key("anthropic")


@patch("shotgun.agents.config.manager.logger")
@pytest.mark.asyncio
async def test_initialize(mock_logger):
    """Test initialize method creates default config and saves it."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        config = await manager.initialize()

        assert isinstance(config, ShotgunConfig)
        assert config.selected_model is None
        assert config_path.exists()
        assert hasattr(config, "shotgun_instance_id")
        assert config.shotgun_instance_id is not None
        assert hasattr(config, "config_version")
        assert config.config_version == CURRENT_CONFIG_VERSION
        # The log message now includes user_id
        assert mock_logger.info.call_count == 1
        call_args = mock_logger.info.call_args[0]
        assert "Configuration initialized at" in call_args[0]
        assert config_path == call_args[1]
        assert config.shotgun_instance_id == call_args[2]


def test_convert_secrets_to_secretstr():
    """Test _convert_secrets_to_secretstr converts plain text to SecretStr."""
    manager = ConfigManager()
    data = {
        "openai": {"api_key": "openai-key"},
        "anthropic": {"api_key": "anthropic-key"},
        "google": {"api_key": "google-key"},
        "other": {"api_key": "other-key"},  # Should not be converted
    }

    manager._convert_secrets_to_secretstr(data)

    assert isinstance(data["openai"]["api_key"], SecretStr)
    assert data["openai"]["api_key"].get_secret_value() == "openai-key"
    assert isinstance(data["anthropic"]["api_key"], SecretStr)
    assert data["anthropic"]["api_key"].get_secret_value() == "anthropic-key"
    assert isinstance(data["google"]["api_key"], SecretStr)
    assert data["google"]["api_key"].get_secret_value() == "google-key"
    assert data["other"]["api_key"] == "other-key"  # Should remain unchanged


def test_convert_secrets_to_secretstr_none_keys():
    """Test _convert_secrets_to_secretstr handles None keys."""
    manager = ConfigManager()
    data = {
        "openai": {"api_key": None},
        "anthropic": {"api_key": None},
        "google": {"api_key": None},
    }

    manager._convert_secrets_to_secretstr(data)

    assert data["openai"]["api_key"] is None
    assert data["anthropic"]["api_key"] is None
    assert data["google"]["api_key"] is None


def test_convert_secretstr_to_plain():
    """Test _convert_secretstr_to_plain converts SecretStr to plain text."""
    manager = ConfigManager()
    data = {
        "openai": {"api_key": SecretStr("openai-key")},
        "anthropic": {"api_key": SecretStr("anthropic-key")},
        "google": {"api_key": SecretStr("google-key")},
        "other": {"api_key": SecretStr("other-key")},  # Should not be converted
    }

    manager._convert_secretstr_to_plain(data)

    assert data["openai"]["api_key"] == "openai-key"
    assert data["anthropic"]["api_key"] == "anthropic-key"
    assert data["google"]["api_key"] == "google-key"
    assert isinstance(data["other"]["api_key"], SecretStr)  # Should remain unchanged


def test_convert_secretstr_to_plain_none_keys():
    """Test _convert_secretstr_to_plain handles None keys."""
    manager = ConfigManager()
    data = {
        "openai": {"api_key": None},
        "anthropic": {"api_key": None},
        "google": {"api_key": None},
    }

    manager._convert_secretstr_to_plain(data)

    assert data["openai"]["api_key"] is None
    assert data["anthropic"]["api_key"] is None
    assert data["google"]["api_key"] is None


def test_get_config_manager():
    """Test get_config_manager factory function."""
    manager = get_config_manager()

    assert isinstance(manager, ConfigManager)
    # Verify the path ends with the expected components
    assert manager.config_path.name == "config.json"
    assert manager.config_path.parent.name == ".shotgun-sh"


def test_get_config_manager_singleton():
    """Test get_config_manager returns the same singleton instance."""
    # Reset the singleton for this test
    import shotgun.agents.config.manager as manager_module

    original_instance = manager_module._config_manager_instance
    manager_module._config_manager_instance = None

    try:
        manager1 = get_config_manager()
        manager2 = get_config_manager()
        manager3 = get_config_manager()

        # All calls should return the same instance
        assert manager1 is manager2
        assert manager2 is manager3
        assert manager1 is manager3
    finally:
        # Restore original singleton
        manager_module._config_manager_instance = original_instance


@pytest.mark.asyncio
async def test_config_manager_force_reload():
    """Test ConfigManager force_reload parameter and caching behavior."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        # Load config with force_reload=False to enable caching
        config1 = await manager.load(force_reload=False)
        assert config1.google.api_key is None

        # Manually modify the config file
        import uuid

        config_data = {
            ConfigSection.OPENAI.value: {},
            ConfigSection.ANTHROPIC.value: {},
            ConfigSection.GOOGLE.value: {API_KEY_FIELD: "new-google-key"},
            ConfigSection.SHOTGUN.value: {},
            "selected_model": None,
            SHOTGUN_INSTANCE_ID_FIELD: str(uuid.uuid4()),
            CONFIG_VERSION_FIELD: 3,
        }
        with open(config_path, "w") as f:
            json.dump(config_data, f)

        # Load with force_reload=False should return cached config
        config2 = await manager.load(force_reload=False)
        assert config2.google.api_key is None  # Still cached

        # Load with force_reload=True (default) should read from disk
        config3 = await manager.load(force_reload=True)
        assert config3.google.api_key is not None
        assert config3.google.api_key.get_secret_value() == "new-google-key"


@pytest.mark.asyncio
async def test_update_provider_sets_selected_model_when_first_key():
    """Test that adding the first API key sets selected_model to that provider's default."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        # Initially, selected_model is None
        config = await manager.load()
        assert config.selected_model is None

        # Add API key to Anthropic when no other keys exist
        await manager.update_provider(
            ProviderType.ANTHROPIC, **{API_KEY_FIELD: "test-anthropic-key"}
        )

        # Verify selected_model is now set to Anthropic's default
        config = await manager.load()
        assert config.selected_model == ModelName.CLAUDE_OPUS_4_5
        assert config.anthropic.api_key.get_secret_value() == "test-anthropic-key"


@pytest.mark.asyncio
async def test_update_provider_keeps_selected_model_when_other_keys_exist():
    """Test that adding a key when others exist doesn't change selected_model."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        # First, add OpenAI key (should set selected_model to OpenAI default)
        await manager.update_provider(
            ProviderType.OPENAI, **{API_KEY_FIELD: "test-openai-key"}
        )
        config = await manager.load()
        assert config.selected_model == ModelName.GPT_5_2

        # Now add Anthropic key (should NOT change selected_model)
        await manager.update_provider(
            ProviderType.ANTHROPIC, **{API_KEY_FIELD: "test-anthropic-key"}
        )
        config = await manager.load()
        assert config.selected_model == ModelName.GPT_5_2  # Still GPT-5.1
        assert config.anthropic.api_key.get_secret_value() == "test-anthropic-key"


@pytest.mark.asyncio
async def test_update_provider_sets_selected_model_for_google():
    """Test that Google selected_model is set when it's the first key."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        # Add API key to Google when no other keys exist
        await manager.update_provider(
            ProviderType.GOOGLE, **{API_KEY_FIELD: "test-google-key"}
        )

        # Verify selected_model is now set to Google's default
        config = await manager.load()
        assert config.selected_model == ModelName.GEMINI_3_PRO_PREVIEW
        assert config.google.api_key.get_secret_value() == "test-google-key"


@pytest.mark.asyncio
async def test_update_provider_with_none_key_doesnt_set_selected_model():
    """Test that setting a None API key doesn't change selected_model."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        # Initially selected_model is None
        config = await manager.load()
        assert config.selected_model is None

        # Try to update Anthropic with None key
        await manager.update_provider(ProviderType.ANTHROPIC, **{API_KEY_FIELD: None})

        # selected_model should still be None
        config = await manager.load()
        assert config.selected_model is None
        assert config.anthropic.api_key is None


@patch("shotgun.agents.config.manager.logger")
@pytest.mark.asyncio
async def test_load_updates_selected_model_when_provider_has_no_key(mock_logger):
    """Test that load() updates selected_model when its provider has no API key."""
    import uuid

    config_data = {
        ConfigSection.OPENAI.value: {},  # No API key
        ConfigSection.ANTHROPIC.value: {API_KEY_FIELD: "test-anthropic-key"},
        ConfigSection.GOOGLE.value: {},
        ConfigSection.SHOTGUN.value: {},
        "selected_model": "gpt-5.1",  # Selected model is OpenAI but has no key
        SHOTGUN_INSTANCE_ID_FIELD: str(uuid.uuid4()),
        CONFIG_VERSION_FIELD: 3,
    }

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as temp_file:
        json.dump(config_data, temp_file)
        temp_file.flush()

        try:
            manager = ConfigManager(config_path=Path(temp_file.name))
            config = await manager.load()

            # selected_model should now be Anthropic's default since OpenAI has no key
            assert config.selected_model == ModelName.CLAUDE_OPUS_4_5
            assert isinstance(config.anthropic.api_key, SecretStr)
            assert config.anthropic.api_key.get_secret_value() == "test-anthropic-key"

            # Check that the info log was called
            assert any(
                "Selected model" in str(call) and "finding available model" in str(call)
                for call in mock_logger.info.call_args_list
            )
        finally:
            os.unlink(temp_file.name)


@patch("shotgun.agents.config.manager.logger")
@pytest.mark.asyncio
async def test_load_keeps_selected_model_when_provider_has_key(mock_logger):
    """Test that load() keeps selected_model when its provider has an API key."""
    import uuid

    config_data = {
        ConfigSection.OPENAI.value: {API_KEY_FIELD: "test-openai-key"},
        ConfigSection.ANTHROPIC.value: {API_KEY_FIELD: "test-anthropic-key"},
        ConfigSection.GOOGLE.value: {},
        ConfigSection.SHOTGUN.value: {},
        "selected_model": "gpt-5.2",
        SHOTGUN_INSTANCE_ID_FIELD: str(uuid.uuid4()),
        CONFIG_VERSION_FIELD: 3,
    }

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as temp_file:
        json.dump(config_data, temp_file)
        temp_file.flush()

        try:
            manager = ConfigManager(config_path=Path(temp_file.name))
            config = await manager.load()

            # selected_model should still be GPT-5.2 since it has a key
            assert config.selected_model == ModelName.GPT_5_2
            assert isinstance(config.openai.api_key, SecretStr)
            assert config.openai.api_key.get_secret_value() == "test-openai-key"

            # Should not log any info about changing selected_model
            info_calls = [
                call
                for call in mock_logger.info.call_args_list
                if "finding available model" in str(call)
            ]
            assert len(info_calls) == 0
        finally:
            os.unlink(temp_file.name)


@pytest.mark.asyncio
async def test_clear_provider_key_updates_selected_model():
    """Test that clearing provider key updates selected_model to available provider."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        # Set up multiple providers
        await manager.update_provider(ProviderType.OPENAI, api_key="test-openai-key")
        await manager.update_provider(
            ProviderType.ANTHROPIC, api_key="test-anthropic-key"
        )

        # Manually set selected_model to Anthropic model
        await manager.update_selected_model(ModelName.CLAUDE_SONNET_4_5)
        config = await manager.load(force_reload=True)
        assert config.selected_model == ModelName.CLAUDE_SONNET_4_5

        # Clear Anthropic provider key
        await manager.clear_provider_key(ProviderType.ANTHROPIC)

        # Reload config and verify selected_model is updated to available provider
        config = await manager.load(force_reload=True)

        # selected_model should be updated to an OpenAI model or set to None then to OpenAI on load
        # The load() method should detect that the selected model's provider has no key
        # and switch to an available provider
        assert config.selected_model != ModelName.CLAUDE_SONNET_4_5
        assert config.selected_model == ModelName.GPT_5_2  # Should switch to OpenAI


@pytest.mark.asyncio
async def test_clear_all_provider_keys_sets_selected_model_to_none():
    """Test that clearing all provider keys sets selected_model appropriately."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        # Set up a provider
        await manager.update_provider(ProviderType.OPENAI, api_key="test-openai-key")
        config = await manager.load(force_reload=True)
        assert config.selected_model == ModelName.GPT_5_2

        # Clear the only provider key
        await manager.clear_provider_key(ProviderType.OPENAI)

        # Reload config
        config = await manager.load(force_reload=True)

        # selected_model should be None since no providers have keys
        # The load() method will try to find an available provider but won't find any
        assert config.selected_model is None


@pytest.mark.asyncio
@patch("shotgun.agents.config.manager.logger")
async def test_load_migration_sets_shown_welcome_screen_for_existing_byok_users(
    mock_logger,
):
    """Test that load() sets shown_welcome_screen=False for existing BYOK users."""
    import uuid

    # Create config file without shown_welcome_screen but with a BYOK provider key
    config_data = {
        ConfigSection.OPENAI.value: {API_KEY_FIELD: "test-openai-key"},
        ConfigSection.ANTHROPIC.value: {},
        ConfigSection.GOOGLE.value: {},
        ConfigSection.SHOTGUN.value: {},
        "selected_model": "gpt-5",
        SHOTGUN_INSTANCE_ID_FIELD: str(uuid.uuid4()),
        CONFIG_VERSION_FIELD: 3,
        # Note: shown_welcome_screen is intentionally missing
    }

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as temp_file:
        json.dump(config_data, temp_file)
        temp_file.flush()

        try:
            manager = ConfigManager(config_path=Path(temp_file.name))
            config = await manager.load()

            # shown_welcome_screen should be set to False for existing BYOK user
            assert config.shown_welcome_screen is False

            # Verify the migration log message was called
            assert any(
                "Existing BYOK user detected" in str(call)
                for call in mock_logger.info.call_args_list
            )
        finally:
            os.unlink(temp_file.name)


@pytest.mark.asyncio
@patch("shotgun.agents.config.manager.logger")
async def test_load_migration_does_not_set_shown_welcome_screen_for_new_users(
    mock_logger,
):
    """Test that load() does not set shown_welcome_screen for new users without BYOK keys."""
    import uuid

    # Create config file without shown_welcome_screen and without any BYOK provider keys
    config_data = {
        ConfigSection.OPENAI.value: {},
        ConfigSection.ANTHROPIC.value: {},
        ConfigSection.GOOGLE.value: {},
        ConfigSection.SHOTGUN.value: {},
        "selected_model": None,
        SHOTGUN_INSTANCE_ID_FIELD: str(uuid.uuid4()),
        CONFIG_VERSION_FIELD: 3,
        # Note: shown_welcome_screen is intentionally missing
    }

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as temp_file:
        json.dump(config_data, temp_file)
        temp_file.flush()

        try:
            manager = ConfigManager(config_path=Path(temp_file.name))
            config = await manager.load()

            # shown_welcome_screen should use default (False) from the model
            assert config.shown_welcome_screen is False

            # Verify the migration log message was NOT called
            assert not any(
                "Existing BYOK user detected" in str(call)
                for call in mock_logger.info.call_args_list
            )
        finally:
            os.unlink(temp_file.name)


@pytest.mark.asyncio
@patch("shotgun.agents.config.manager.logger")
async def test_load_migration_respects_existing_shown_welcome_screen(mock_logger):
    """Test that load() does not override existing shown_welcome_screen value."""
    import uuid

    # Create config file with shown_welcome_screen already set to True
    config_data = {
        ConfigSection.OPENAI.value: {API_KEY_FIELD: "test-openai-key"},
        ConfigSection.ANTHROPIC.value: {},
        ConfigSection.GOOGLE.value: {},
        ConfigSection.SHOTGUN.value: {},
        "selected_model": "gpt-5",
        SHOTGUN_INSTANCE_ID_FIELD: str(uuid.uuid4()),
        CONFIG_VERSION_FIELD: 3,
        "shown_welcome_screen": True,
    }

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as temp_file:
        json.dump(config_data, temp_file)
        temp_file.flush()

        try:
            manager = ConfigManager(config_path=Path(temp_file.name))
            config = await manager.load()

            # shown_welcome_screen should remain True
            assert config.shown_welcome_screen is True

            # Verify the migration log message was NOT called
            assert not any(
                "Existing BYOK user detected" in str(call)
                for call in mock_logger.info.call_args_list
            )
        finally:
            os.unlink(temp_file.name)


@pytest.mark.asyncio
async def test_update_provider_sets_shown_welcome_screen_for_byok():
    """Test that update_provider sets shown_welcome_screen=True when BYOK provider is configured."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        # Initially, shown_welcome_screen should be False (default)
        config = await manager.load()
        assert config.shown_welcome_screen is False

        # Add API key to OpenAI (BYOK provider)
        await manager.update_provider(
            ProviderType.OPENAI, **{API_KEY_FIELD: "test-openai-key"}
        )

        # Verify shown_welcome_screen is now True
        config = await manager.load()
        assert config.shown_welcome_screen is True
        assert config.openai.api_key.get_secret_value() == "test-openai-key"

        # Verify it's persisted to the config file
        with open(config_path, encoding="utf-8") as f:
            saved_data = json.load(f)
        assert saved_data["shown_welcome_screen"] is True


@pytest.mark.asyncio
async def test_update_provider_sets_shown_welcome_screen_for_all_byok_providers():
    """Test that update_provider sets shown_welcome_screen=True for all BYOK providers."""
    providers = [
        (ProviderType.OPENAI, "test-openai-key"),
        (ProviderType.ANTHROPIC, "test-anthropic-key"),
        (ProviderType.GOOGLE, "test-google-key"),
    ]

    for provider, api_key in providers:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            manager = ConfigManager(config_path=config_path)

            # Initially, shown_welcome_screen should be False
            config = await manager.load()
            assert config.shown_welcome_screen is False

            # Add API key to the provider
            await manager.update_provider(provider, **{API_KEY_FIELD: api_key})

            # Verify shown_welcome_screen is now True
            config = await manager.load()
            assert config.shown_welcome_screen is True


@pytest.mark.asyncio
async def test_update_provider_does_not_set_shown_welcome_screen_for_none_key():
    """Test that update_provider does not set shown_welcome_screen when setting None API key."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        # Initially, shown_welcome_screen should be False
        config = await manager.load()
        assert config.shown_welcome_screen is False

        # Try to update OpenAI with None key
        await manager.update_provider(ProviderType.OPENAI, **{API_KEY_FIELD: None})

        # shown_welcome_screen should still be False
        config = await manager.load()
        assert config.shown_welcome_screen is False


@pytest.mark.asyncio
async def test_update_shotgun_account_does_not_set_shown_welcome_screen():
    """Test that update_shotgun_account does not set shown_welcome_screen."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        # Initially, shown_welcome_screen should be False
        config = await manager.load()
        assert config.shown_welcome_screen is False

        # Update Shotgun Account credentials
        await manager.update_shotgun_account(
            api_key="test-api-key", supabase_jwt="test-jwt-token"
        )

        # shown_welcome_screen should still be False
        # (Shotgun Account setup is handled differently in the welcome screen flow)
        config = await manager.load()
        assert config.shown_welcome_screen is False
