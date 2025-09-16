"""Unit tests for ConfigManager."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import SecretStr

from shotgun.agents.config.manager import ConfigManager, get_config_manager
from shotgun.agents.config.models import (
    AnthropicConfig,
    GoogleConfig,
    ModelConfig,
    OpenAIConfig,
    ProviderType,
    ShotgunConfig,
)
from shotgun.agents.config.provider import get_provider_model


def test_init_default_path(monkeypatch):
    """Test ConfigManager initialization with default path."""
    # Clear any SHOTGUN_HOME env var for this test
    monkeypatch.delenv("SHOTGUN_HOME", raising=False)

    manager = ConfigManager()
    expected_path = Path.home() / ".shotgun-sh" / "config.json"
    assert manager.config_path == expected_path
    assert manager._config is None


def test_init_custom_path():
    """Test ConfigManager initialization with custom path."""
    custom_path = Path("/custom/config.json")
    manager = ConfigManager(config_path=custom_path)
    assert manager.config_path == custom_path
    assert manager._config is None


@patch("shotgun.agents.config.manager.logger")
def test_load_config_not_exists(mock_logger):
    """Test loading config when file doesn't exist."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "nonexistent.json"
        manager = ConfigManager(config_path=config_path)

        config = manager.load()

        assert isinstance(config, ShotgunConfig)
        assert config.default_provider == ProviderType.OPENAI
        assert manager._config is config
        mock_logger.info.assert_called_once_with(
            "Configuration file not found, using defaults: %s", config_path
        )


@patch("shotgun.agents.config.manager.logger")
def test_load_config_cached(mock_logger):
    """Test loading config returns cached version on second call."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "nonexistent.json"
        manager = ConfigManager(config_path=config_path)

        config1 = manager.load()
        config2 = manager.load()

        assert config1 is config2
        mock_logger.info.assert_called_once()


@patch("shotgun.agents.config.manager.logger")
def test_load_config_valid_file(mock_logger):
    """Test loading config from valid file."""
    config_data = {
        "openai": {"api_key": "test-openai-key"},
        "anthropic": {"api_key": "test-anthropic-key"},
        "google": {"api_key": "test-google-key"},
        "default_provider": "anthropic",
    }

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as temp_file:
        json.dump(config_data, temp_file)
        temp_file.flush()

        try:
            manager = ConfigManager(config_path=Path(temp_file.name))
            config = manager.load()

            assert isinstance(config, ShotgunConfig)
            assert config.default_provider == ProviderType.ANTHROPIC
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


@patch("shotgun.agents.config.manager.logger")
def test_load_config_invalid_json(mock_logger):
    """Test loading config from invalid JSON file."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as temp_file:
        temp_file.write("invalid json")
        temp_file.flush()

        try:
            manager = ConfigManager(config_path=Path(temp_file.name))
            config = manager.load()

            assert isinstance(config, ShotgunConfig)
            assert config.default_provider == ProviderType.OPENAI
            mock_logger.error.assert_called_once()
            mock_logger.info.assert_called_once_with("Using default configuration")
        finally:
            os.unlink(temp_file.name)


@patch("shotgun.agents.config.manager.logger")
def test_save_config_with_argument(mock_logger):
    """Test saving config with explicit config argument."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "test_config.json"
        manager = ConfigManager(config_path=config_path)

        config = ShotgunConfig(
            default_provider=ProviderType.ANTHROPIC,
            openai=OpenAIConfig(api_key=SecretStr("test-key")),
        )

        manager.save(config)

        assert config_path.exists()
        with open(config_path, encoding="utf-8") as f:
            saved_data = json.load(f)

        assert saved_data["default_provider"] == "anthropic"
        assert saved_data["openai"]["api_key"] == "test-key"
        assert manager._config is config
        mock_logger.debug.assert_called_once_with(
            "Configuration saved to %s", config_path
        )


@patch("shotgun.agents.config.manager.logger")
def test_save_config_without_argument(mock_logger):
    """Test saving config without explicit config argument."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "test_config.json"
        manager = ConfigManager(config_path=config_path)

        # Load default config first
        manager.load()

        manager.save()

        assert config_path.exists()
        mock_logger.debug.assert_called_once_with(
            "Configuration saved to %s", config_path
        )


@patch("shotgun.agents.config.manager.logger")
def test_save_config_creates_directory(mock_logger):
    """Test saving config creates parent directory if it doesn't exist."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "nested" / "dir" / "config.json"
        manager = ConfigManager(config_path=config_path)

        config = ShotgunConfig()
        manager.save(config)

        assert config_path.exists()
        assert config_path.parent.exists()


@patch("shotgun.agents.config.manager.logger")
def test_save_config_failure(mock_logger):
    """Test save config handles file write errors."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "readonly" / "config.json"
        # Create readonly parent directory
        config_path.parent.mkdir()
        config_path.parent.chmod(0o444)

        manager = ConfigManager(config_path=config_path)
        config = ShotgunConfig()

        try:
            with pytest.raises((OSError, PermissionError)):
                manager.save(config)

            mock_logger.error.assert_called_once()
        finally:
            # Cleanup - restore write permissions
            config_path.parent.chmod(0o755)


@patch.dict(os.environ, {}, clear=True)
@patch("shotgun.agents.config.provider.get_config_manager")
def test_get_provider_model_openai_with_config_key(mock_get_config_manager):
    """Test get_provider_model for OpenAI with API key in config."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        # Set cached config directly
        config = ShotgunConfig(
            openai=OpenAIConfig(api_key=SecretStr("test-openai-key"))
        )
        manager._config = config
        mock_get_config_manager.return_value = manager

        model = get_provider_model(ProviderType.OPENAI)

        assert isinstance(model, ModelConfig)
        assert model.pydantic_model_name == "openai:gpt-5"
        assert os.environ.get("OPENAI_API_KEY") == "test-openai-key"


@patch.dict(os.environ, {"OPENAI_API_KEY": "env-openai-key"})
@patch("shotgun.agents.config.provider.get_config_manager")
def test_get_provider_model_openai_with_env_key(mock_get_config_manager):
    """Test get_provider_model for OpenAI with API key in environment."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)
        mock_get_config_manager.return_value = manager

        model = get_provider_model(ProviderType.OPENAI)

        assert isinstance(model, ModelConfig)
        assert model.pydantic_model_name == "openai:gpt-5"


@patch.dict(os.environ, {}, clear=True)
@patch("shotgun.agents.config.provider.get_config_manager")
def test_get_provider_model_openai_no_key(mock_get_config_manager):
    """Test get_provider_model for OpenAI with no API key."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)
        mock_get_config_manager.return_value = manager

        with pytest.raises(ValueError, match="OpenAI API key not configured"):
            get_provider_model(ProviderType.OPENAI)


@patch.dict(os.environ, {}, clear=True)
@patch("shotgun.agents.config.provider.get_config_manager")
def test_get_provider_model_anthropic_with_config_key(mock_get_config_manager):
    """Test get_provider_model for Anthropic with API key in config."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        # Set cached config directly
        config = ShotgunConfig(
            anthropic=AnthropicConfig(api_key=SecretStr("test-anthropic-key"))
        )
        manager._config = config
        mock_get_config_manager.return_value = manager

        model = get_provider_model(ProviderType.ANTHROPIC)

        assert isinstance(model, ModelConfig)
        assert model.pydantic_model_name == "anthropic:claude-opus-4-1"
        assert os.environ.get("ANTHROPIC_API_KEY") == "test-anthropic-key"


@patch.dict(os.environ, {"ANTHROPIC_API_KEY": "env-anthropic-key"})
@patch("shotgun.agents.config.provider.get_config_manager")
def test_get_provider_model_anthropic_with_env_key(mock_get_config_manager):
    """Test get_provider_model for Anthropic with API key in environment."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)
        mock_get_config_manager.return_value = manager

        model = get_provider_model(ProviderType.ANTHROPIC)

        assert isinstance(model, ModelConfig)
        assert model.pydantic_model_name == "anthropic:claude-opus-4-1"


@patch.dict(os.environ, {}, clear=True)
@patch("shotgun.agents.config.provider.get_config_manager")
def test_get_provider_model_anthropic_no_key(mock_get_config_manager):
    """Test get_provider_model for Anthropic with no API key."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)
        mock_get_config_manager.return_value = manager

        with pytest.raises(ValueError, match="Anthropic API key not configured"):
            get_provider_model(ProviderType.ANTHROPIC)


@patch.dict(os.environ, {}, clear=True)
@patch("shotgun.agents.config.provider.get_config_manager")
def test_get_provider_model_google_with_config_key(mock_get_config_manager):
    """Test get_provider_model for Google with API key in config."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        # Set cached config directly
        config = ShotgunConfig(
            google=GoogleConfig(api_key=SecretStr("test-google-key"))
        )
        manager._config = config
        mock_get_config_manager.return_value = manager

        model = get_provider_model(ProviderType.GOOGLE)

        assert isinstance(model, ModelConfig)
        assert model.pydantic_model_name == "google-gla:gemini-2.5-pro"
        assert os.environ.get("GOOGLE_API_KEY") == "test-google-key"


@patch.dict(os.environ, {"GOOGLE_API_KEY": "env-google-key"})
@patch("shotgun.agents.config.provider.get_config_manager")
def test_get_provider_model_google_with_env_key(mock_get_config_manager):
    """Test get_provider_model for Google with API key in environment."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)
        mock_get_config_manager.return_value = manager

        model = get_provider_model(ProviderType.GOOGLE)

        assert isinstance(model, ModelConfig)
        assert model.pydantic_model_name == "google-gla:gemini-2.5-pro"


@patch.dict(os.environ, {}, clear=True)
@patch("shotgun.agents.config.provider.get_config_manager")
def test_get_provider_model_google_no_key(mock_get_config_manager):
    """Test get_provider_model for Google with no API key."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)
        mock_get_config_manager.return_value = manager

        with pytest.raises(ValueError, match="Google API key not configured"):
            get_provider_model(ProviderType.GOOGLE)


@patch("shotgun.agents.config.provider.get_config_manager")
def test_get_provider_model_string_provider(mock_get_config_manager):
    """Test get_provider_model with string provider argument."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        # Set cached config directly
        config = ShotgunConfig(openai=OpenAIConfig(api_key=SecretStr("test-key")))
        manager._config = config
        mock_get_config_manager.return_value = manager

        model = get_provider_model("openai")

        assert isinstance(model, ModelConfig)
        assert model.pydantic_model_name == "openai:gpt-5"


@patch("shotgun.agents.config.provider.get_config_manager")
def test_get_provider_model_none_uses_default(mock_get_config_manager):
    """Test get_provider_model with None provider uses default."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        # Set cached config directly
        config = ShotgunConfig(
            default_provider=ProviderType.ANTHROPIC,
            anthropic=AnthropicConfig(api_key=SecretStr("test-key")),
        )
        manager._config = config
        mock_get_config_manager.return_value = manager

        model = get_provider_model(None)

        assert isinstance(model, ModelConfig)
        assert model.pydantic_model_name == "anthropic:claude-opus-4-1"


@patch("shotgun.agents.config.provider.get_config_manager")
def test_get_provider_model_unsupported_provider(mock_get_config_manager):
    """Test get_provider_model with unsupported provider."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)
        mock_get_config_manager.return_value = manager

        with pytest.raises(ValueError, match="is not a valid ProviderType"):
            get_provider_model("unsupported")


def test_update_provider_openai():
    """Test updating OpenAI provider configuration."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        manager.update_provider(ProviderType.OPENAI, api_key="new-openai-key")

        # Verify config was updated and saved
        assert config_path.exists()
        with open(config_path, encoding="utf-8") as f:
            saved_data = json.load(f)

        assert saved_data["openai"]["api_key"] == "new-openai-key"


def test_update_provider_anthropic_string():
    """Test updating Anthropic provider with string provider type."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        manager.update_provider("anthropic", api_key="new-anthropic-key")

        # Verify config was updated and saved
        assert config_path.exists()
        with open(config_path, encoding="utf-8") as f:
            saved_data = json.load(f)

        assert saved_data["anthropic"]["api_key"] == "new-anthropic-key"


def test_update_provider_google():
    """Test updating Google provider configuration."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        manager.update_provider(ProviderType.GOOGLE, api_key="new-google-key")

        # Verify config was updated and saved
        assert config_path.exists()
        with open(config_path, encoding="utf-8") as f:
            saved_data = json.load(f)

        assert saved_data["google"]["api_key"] == "new-google-key"


def test_update_provider_none_api_key():
    """Test updating provider with None API key is ignored."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        # This should not raise an error and should save default config
        manager.update_provider(ProviderType.OPENAI, api_key=None)

        assert config_path.exists()


def test_update_provider_unsupported_fields():
    """Test updating provider with unsupported fields raises error."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        with pytest.raises(ValueError, match="Unsupported configuration fields"):
            manager.update_provider(ProviderType.OPENAI, api_key="key", model="gpt-4")


def test_update_provider_unsupported_provider():
    """Test updating unsupported provider raises error."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        with pytest.raises(ValueError, match="is not a valid ProviderType"):
            manager.update_provider("unsupported", api_key="key")


@patch("shotgun.agents.config.manager.logger")
def test_initialize(mock_logger):
    """Test initialize method creates default config and saves it."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        config = manager.initialize()

        assert isinstance(config, ShotgunConfig)
        assert config.default_provider == ProviderType.OPENAI
        assert config_path.exists()
        mock_logger.info.assert_called_once_with(
            "Configuration initialized at %s", config_path
        )


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
    assert manager.config_path == Path.home() / ".shotgun-sh" / "config.json"
