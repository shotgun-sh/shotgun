"""Unit tests for provider module."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import SecretStr

from shotgun.agents.config.manager import ConfigManager
from shotgun.agents.config.models import (
    AnthropicConfig,
    GoogleConfig,
    ModelConfig,
    OpenAIConfig,
    ProviderType,
    ShotgunConfig,
)
from shotgun.agents.config.provider import _get_api_key, get_provider_model


@patch.dict(os.environ, {}, clear=True)
@patch("shotgun.agents.config.provider.get_config_manager")
def test_get_provider_model_openai_with_config_key(mock_get_config_manager):
    """Test get_provider_model for OpenAI with API key in config."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        # Set cached config directly
        import uuid

        config = ShotgunConfig(
            user_id=str(uuid.uuid4()),
            config_version=1,
            openai=OpenAIConfig(api_key=SecretStr("test-openai-key")),
        )
        manager._config = config
        mock_get_config_manager.return_value = manager

        model = get_provider_model(ProviderType.OPENAI)

        assert isinstance(model, ModelConfig)
        assert model.name == "gpt-5"
        assert model.name == "gpt-5"
        assert model.provider == ProviderType.OPENAI
        assert model.api_key == "test-openai-key"


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
        assert model.name == "gpt-5"


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
        import uuid

        config = ShotgunConfig(
            user_id=str(uuid.uuid4()),
            config_version=1,
            anthropic=AnthropicConfig(api_key=SecretStr("test-anthropic-key")),
        )
        manager._config = config
        mock_get_config_manager.return_value = manager

        model = get_provider_model(ProviderType.ANTHROPIC)

        assert isinstance(model, ModelConfig)
        assert model.name == "claude-opus-4-1"
        assert model.api_key == "test-anthropic-key"


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
        assert model.name == "claude-opus-4-1"


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
        import uuid

        config = ShotgunConfig(
            user_id=str(uuid.uuid4()),
            config_version=1,
            google=GoogleConfig(api_key=SecretStr("test-google-key")),
        )
        manager._config = config
        mock_get_config_manager.return_value = manager

        model = get_provider_model(ProviderType.GOOGLE)

        assert isinstance(model, ModelConfig)
        assert model.name == "gemini-2.5-pro"
        assert model.api_key == "test-google-key"


@patch.dict(os.environ, {"GEMINI_API_KEY": "env-google-key"})
@patch("shotgun.agents.config.provider.get_config_manager")
def test_get_provider_model_google_with_env_key(mock_get_config_manager):
    """Test get_provider_model for Google with API key in environment."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)
        mock_get_config_manager.return_value = manager

        model = get_provider_model(ProviderType.GOOGLE)

        assert isinstance(model, ModelConfig)
        assert model.name == "gemini-2.5-pro"


@patch.dict(os.environ, {}, clear=True)
@patch("shotgun.agents.config.provider.get_config_manager")
def test_get_provider_model_google_no_key(mock_get_config_manager):
    """Test get_provider_model for Google with no API key."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)
        mock_get_config_manager.return_value = manager

        with pytest.raises(ValueError, match="Gemini API key not configured"):
            get_provider_model(ProviderType.GOOGLE)


@patch("shotgun.agents.config.provider.get_config_manager")
def test_get_provider_model_with_enum(mock_get_config_manager):
    """Test get_provider_model with ProviderType enum argument."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        # Set cached config directly
        import uuid

        config = ShotgunConfig(
            user_id=str(uuid.uuid4()),
            config_version=1,
            openai=OpenAIConfig(api_key=SecretStr("test-key")),
        )
        manager._config = config
        mock_get_config_manager.return_value = manager

        model = get_provider_model(ProviderType.OPENAI)

        assert isinstance(model, ModelConfig)
        assert model.name == "gpt-5"


@patch("shotgun.agents.config.provider.get_config_manager")
def test_get_provider_model_none_uses_default(mock_get_config_manager):
    """Test get_provider_model with None provider uses default."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        # Set cached config directly
        import uuid

        config = ShotgunConfig(
            user_id=str(uuid.uuid4()),
            config_version=1,
            default_provider=ProviderType.ANTHROPIC,
            anthropic=AnthropicConfig(api_key=SecretStr("test-key")),
        )
        manager._config = config
        mock_get_config_manager.return_value = manager

        model = get_provider_model(None)

        assert isinstance(model, ModelConfig)
        assert model.name == "claude-opus-4-1"


@patch("shotgun.agents.config.provider.get_config_manager")
def test_get_provider_model_unsupported_provider(mock_get_config_manager):
    """Test get_provider_model with unsupported provider."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)
        mock_get_config_manager.return_value = manager

        with pytest.raises(ValueError, match="is not a valid ProviderType"):
            get_provider_model("unsupported")


@patch.dict(os.environ, {"OPENAI_API_KEY": "existing-env-key"}, clear=False)
@patch("shotgun.agents.config.provider.get_config_manager")
def test_get_provider_model_prefers_config_over_env(mock_get_config_manager):
    """Test get_provider_model prefers config API key over environment variable."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        # Set cached config directly
        import uuid

        config = ShotgunConfig(
            user_id=str(uuid.uuid4()),
            config_version=1,
            openai=OpenAIConfig(api_key=SecretStr("config-key")),
        )
        manager._config = config
        mock_get_config_manager.return_value = manager

        model = get_provider_model(ProviderType.OPENAI)

        assert isinstance(model, ModelConfig)
        assert model.name == "gpt-5"
        # Should use config key, not environment variable
        assert model.api_key == "config-key"


def test_get_api_key_from_config():
    """Test _get_api_key returns config key when available."""
    config_key = SecretStr("config-key")

    result = _get_api_key(config_key, "ENV_VAR")

    assert result == "config-key"


@patch.dict(os.environ, {"ENV_VAR": "env-key"})
def test_get_api_key_from_env():
    """Test _get_api_key returns environment key when config key is None."""
    result = _get_api_key(None, "ENV_VAR")

    assert result == "env-key"


@patch.dict(os.environ, {}, clear=True)
def test_get_api_key_none():
    """Test _get_api_key returns None when neither config nor env key available."""
    result = _get_api_key(None, "ENV_VAR")

    assert result is None


@patch.dict(os.environ, {"ENV_VAR": "env-key"})
def test_get_api_key_config_takes_precedence():
    """Test _get_api_key prefers config key over environment variable."""
    config_key = SecretStr("config-key")

    result = _get_api_key(config_key, "ENV_VAR")

    assert result == "config-key"


@patch("shotgun.agents.config.provider.get_config_manager")
def test_get_provider_model_provider_enum_conversion(mock_get_config_manager):
    """Test get_provider_model properly converts string to ProviderType enum."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        # Set cached config directly
        import uuid

        config = ShotgunConfig(
            user_id=str(uuid.uuid4()),
            config_version=1,
            anthropic=AnthropicConfig(api_key=SecretStr("test-key")),
        )
        manager._config = config
        mock_get_config_manager.return_value = manager

        # Test with string representation to verify enum conversion
        model = get_provider_model("anthropic")

        assert isinstance(model, ModelConfig)
        assert model.name == "claude-opus-4-1"


@patch.dict(os.environ, {}, clear=True)
@patch("shotgun.agents.config.provider.get_config_manager")
def test_get_provider_model_with_env_key_precedence(mock_get_config_manager):
    """Test that environment variables are not overridden if already set."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        # Set config with API key
        import uuid

        config = ShotgunConfig(
            user_id=str(uuid.uuid4()),
            config_version=1,
            anthropic=AnthropicConfig(api_key=SecretStr("config-anthropic-key")),
        )
        manager._config = config
        mock_get_config_manager.return_value = manager

        # Pre-set environment variable
        os.environ["ANTHROPIC_API_KEY"] = "existing-env-key"

        model = get_provider_model(ProviderType.ANTHROPIC)

        assert isinstance(model, ModelConfig)
        assert model.name == "claude-opus-4-1"
        assert model.provider == ProviderType.ANTHROPIC
        # Config key takes precedence over environment variable
        assert model.api_key == "config-anthropic-key"
        # Environment variable should remain unchanged
        assert os.environ.get("ANTHROPIC_API_KEY") == "existing-env-key"


@patch.dict(os.environ, {}, clear=True)
@patch("shotgun.agents.config.provider.get_config_manager")
def test_get_provider_model_api_key_environment_isolation(mock_get_config_manager):
    """Test get_provider_model doesn't leak API keys between providers."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        # Set cached config with multiple provider keys
        import uuid

        config = ShotgunConfig(
            user_id=str(uuid.uuid4()),
            config_version=1,
            openai=OpenAIConfig(api_key=SecretStr("openai-key")),
            anthropic=AnthropicConfig(api_key=SecretStr("anthropic-key")),
        )
        manager._config = config
        mock_get_config_manager.return_value = manager

        # Test OpenAI provider
        openai_model = get_provider_model(ProviderType.OPENAI)
        assert openai_model.api_key == "openai-key"

        # Test Anthropic provider
        anthropic_model = get_provider_model(ProviderType.ANTHROPIC)
        assert anthropic_model.api_key == "anthropic-key"

        # Verify environment variables are NOT set (we no longer set them)
        assert os.environ.get("OPENAI_API_KEY") is None
        assert os.environ.get("ANTHROPIC_API_KEY") is None
