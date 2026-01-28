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
@pytest.mark.asyncio
async def test_get_provider_model_openai_with_config_key(mock_get_config_manager):
    """Test get_provider_model for OpenAI with API key in config."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        # Set cached config directly
        import uuid

        config = ShotgunConfig(
            shotgun_instance_id=str(uuid.uuid4()),
            openai=OpenAIConfig(api_key=SecretStr("test-openai-key")),
        )
        manager._config = config
        mock_get_config_manager.return_value = manager

        model = await get_provider_model(ProviderType.OPENAI)

        assert isinstance(model, ModelConfig)
        assert model.name == "gpt-5.2"
        assert model.name == "gpt-5.2"
        assert model.provider == ProviderType.OPENAI
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
            shotgun_instance_id=str(uuid.uuid4()),
            anthropic=AnthropicConfig(api_key=SecretStr("test-anthropic-key")),
        )
        manager._config = config
        mock_get_config_manager.return_value = manager

        model = await get_provider_model(ProviderType.ANTHROPIC)

        assert isinstance(model, ModelConfig)
        assert model.name == "claude-sonnet-4-5"
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
            shotgun_instance_id=str(uuid.uuid4()),
            google=GoogleConfig(api_key=SecretStr("test-google-key")),
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
async def test_get_provider_model_with_enum(mock_get_config_manager):
    """Test get_provider_model with ProviderType enum argument."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        # Set cached config directly
        import uuid

        config = ShotgunConfig(
            shotgun_instance_id=str(uuid.uuid4()),
            openai=OpenAIConfig(api_key=SecretStr("test-key")),
        )
        manager._config = config
        mock_get_config_manager.return_value = manager

        model = await get_provider_model(ProviderType.OPENAI)

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
            shotgun_instance_id=str(uuid.uuid4()),
            anthropic=AnthropicConfig(api_key=SecretStr("test-key")),
        )
        manager._config = config
        mock_get_config_manager.return_value = manager

        model = await get_provider_model(None)

        assert isinstance(model, ModelConfig)
        assert model.name == "claude-sonnet-4-5"


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


@patch.dict(os.environ, {"OPENAI_API_KEY": "existing-env-key"}, clear=False)
@patch("shotgun.agents.config.provider.get_config_manager")
@pytest.mark.asyncio
async def test_get_provider_model_prefers_config_over_env(mock_get_config_manager):
    """Test get_provider_model prefers config API key over environment variable."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        # Set cached config directly
        import uuid

        config = ShotgunConfig(
            shotgun_instance_id=str(uuid.uuid4()),
            openai=OpenAIConfig(api_key=SecretStr("config-key")),
        )
        manager._config = config
        mock_get_config_manager.return_value = manager

        model = await get_provider_model(ProviderType.OPENAI)

        assert isinstance(model, ModelConfig)
        assert model.name == "gpt-5.2"
        # Should use config key, not environment variable
        assert model.api_key == "config-key"


def test_get_api_key_from_config():
    """Test _get_api_key returns config key when available."""
    config_key = SecretStr("config-key")

    result = _get_api_key(config_key)

    assert result == "config-key"


@patch.dict(os.environ, {}, clear=True)
def test_get_api_key_none():
    """Test _get_api_key returns None when config key is None."""
    result = _get_api_key(None)

    assert result is None


@patch("shotgun.agents.config.provider.get_config_manager")
@pytest.mark.asyncio
async def test_get_provider_model_provider_enum_conversion(mock_get_config_manager):
    """Test get_provider_model properly converts string to ProviderType enum."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        # Set cached config directly
        import uuid

        config = ShotgunConfig(
            shotgun_instance_id=str(uuid.uuid4()),
            anthropic=AnthropicConfig(api_key=SecretStr("test-key")),
        )
        manager._config = config
        mock_get_config_manager.return_value = manager

        # Test with string representation to verify enum conversion
        model = await get_provider_model("anthropic")

        assert isinstance(model, ModelConfig)
        assert model.name == "claude-sonnet-4-5"


@patch.dict(os.environ, {}, clear=True)
@patch("shotgun.agents.config.provider.get_config_manager")
@pytest.mark.asyncio
async def test_get_provider_model_with_env_key_precedence(mock_get_config_manager):
    """Test that environment variables are not overridden if already set."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        # Set config with API key
        import uuid

        config = ShotgunConfig(
            shotgun_instance_id=str(uuid.uuid4()),
            anthropic=AnthropicConfig(api_key=SecretStr("config-anthropic-key")),
        )
        manager._config = config
        mock_get_config_manager.return_value = manager

        # Pre-set environment variable
        os.environ["ANTHROPIC_API_KEY"] = "existing-env-key"

        model = await get_provider_model(ProviderType.ANTHROPIC)

        assert isinstance(model, ModelConfig)
        assert model.name == "claude-sonnet-4-5"
        assert model.provider == ProviderType.ANTHROPIC
        # Config key takes precedence over environment variable
        assert model.api_key == "config-anthropic-key"
        # Environment variable should remain unchanged
        assert os.environ.get("ANTHROPIC_API_KEY") == "existing-env-key"


@patch.dict(os.environ, {}, clear=True)
@patch("shotgun.agents.config.provider.get_config_manager")
@pytest.mark.asyncio
async def test_get_provider_model_api_key_environment_isolation(
    mock_get_config_manager,
):
    """Test get_provider_model doesn't leak API keys between providers."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        manager = ConfigManager(config_path=config_path)

        # Set cached config with multiple provider keys
        import uuid

        config = ShotgunConfig(
            shotgun_instance_id=str(uuid.uuid4()),
            openai=OpenAIConfig(api_key=SecretStr("openai-key")),
            anthropic=AnthropicConfig(api_key=SecretStr("anthropic-key")),
        )
        manager._config = config
        mock_get_config_manager.return_value = manager

        # Test OpenAI provider
        openai_model = await get_provider_model(ProviderType.OPENAI)
        assert openai_model.api_key == "openai-key"

        # Test Anthropic provider
        anthropic_model = await get_provider_model(ProviderType.ANTHROPIC)
        assert anthropic_model.api_key == "anthropic-key"

        # Verify environment variables are NOT set (we no longer set them)
        assert os.environ.get("OPENAI_API_KEY") is None
        assert os.environ.get("ANTHROPIC_API_KEY") is None


@patch.dict(
    os.environ,
    {
        "SHOTGUN_OPENAI_COMPAT_BASE_URL": "https://api.example.com/v1",
        "SHOTGUN_OPENAI_COMPAT_API_KEY": "test-compat-key",
    },
    clear=False,
)
@pytest.mark.asyncio
async def test_get_provider_model_openai_compatible_mode():
    """Test get_provider_model returns OpenAI-compatible config when env vars are set."""
    from shotgun import settings as settings_module
    from shotgun.agents.config.provider import set_openai_compat_model

    settings_module.settings = settings_module.Settings()
    set_openai_compat_model(None)  # Reset any previous override

    try:
        model = await get_provider_model()

        assert isinstance(model, ModelConfig)
        assert model.name == "gpt-5.2"  # Default model
        assert model.provider == ProviderType.OPENAI_COMPATIBLE
        assert model.api_key == "test-compat-key"
        assert model.supports_streaming is True
        assert model.max_input_tokens == 128_000
        assert model.max_output_tokens == 16_000
    finally:
        settings_module.settings = settings_module.Settings()
        set_openai_compat_model(None)


@patch.dict(
    os.environ,
    {
        "SHOTGUN_OPENAI_COMPAT_BASE_URL": "https://api.example.com/v1",
        "SHOTGUN_OPENAI_COMPAT_API_KEY": "test-compat-key",
    },
    clear=False,
)
@pytest.mark.asyncio
async def test_get_provider_model_openai_compatible_with_custom_model():
    """Test get_provider_model uses --model override when set."""
    from shotgun import settings as settings_module
    from shotgun.agents.config.provider import set_openai_compat_model

    settings_module.settings = settings_module.Settings()
    set_openai_compat_model("custom-model")

    try:
        model = await get_provider_model()

        assert isinstance(model, ModelConfig)
        assert model.name == "custom-model"
        assert model.provider == ProviderType.OPENAI_COMPATIBLE
        assert model.api_key == "test-compat-key"
    finally:
        settings_module.settings = settings_module.Settings()
        set_openai_compat_model(None)


@patch.dict(
    os.environ,
    {
        "SHOTGUN_OPENAI_COMPAT_BASE_URL": "https://api.example.com/v1",
    },
    clear=False,
)
@pytest.mark.asyncio
async def test_get_provider_model_openai_compatible_missing_api_key():
    """Test get_provider_model falls back to normal provider when only base_url is set.

    OpenAI-compatible mode requires BOTH base_url AND api_key to be set.
    If only base_url is set, it should be ignored and normal provider selection continues.
    """
    from shotgun import settings as settings_module

    settings_module.settings = settings_module.Settings()

    try:
        # Without api_key, OpenAI-compatible mode should NOT be activated
        # This will fail if no other provider is configured, which is expected
        with pytest.raises(ValueError, match="No provider keys configured"):
            await get_provider_model()
    finally:
        settings_module.settings = settings_module.Settings()


@patch.dict(
    os.environ,
    {
        "SHOTGUN_OPENAI_COMPAT_BASE_URL": "https://api.example.com/v1",
        "SHOTGUN_OPENAI_COMPAT_API_KEY": "test-key",
    },
    clear=False,
)
@pytest.mark.asyncio
async def test_get_provider_model_openai_compatible_default_model():
    """Test get_provider_model uses 'gpt-5.2' as default when no --model is specified."""
    from shotgun import settings as settings_module
    from shotgun.agents.config.provider import set_openai_compat_model

    settings_module.settings = settings_module.Settings()
    set_openai_compat_model(None)  # Reset any previous override

    try:
        model = await get_provider_model()

        assert isinstance(model, ModelConfig)
        # Default model should be "gpt-5.2" when not specified
        assert model.name == "gpt-5.2"
        assert model.provider == ProviderType.OPENAI_COMPATIBLE
    finally:
        settings_module.settings = settings_module.Settings()
        set_openai_compat_model(None)


@patch.dict(
    os.environ,
    {
        "SHOTGUN_OPENAI_COMPAT_BASE_URL": "https://api.example.com/v1",
        "SHOTGUN_OPENAI_COMPAT_API_KEY": "test-key",
    },
    clear=False,
)
@pytest.mark.asyncio
async def test_get_provider_model_openai_compatible_bypasses_other_providers():
    """Test OpenAI-compatible mode takes priority over configured providers."""
    from shotgun import settings as settings_module
    from shotgun.agents.config.provider import set_openai_compat_model

    settings_module.settings = settings_module.Settings()
    set_openai_compat_model(None)  # Reset any previous override

    try:
        # Even when passing a specific provider, OpenAI-compat mode takes priority
        model = await get_provider_model(ProviderType.ANTHROPIC)

        assert isinstance(model, ModelConfig)
        assert model.provider == ProviderType.OPENAI_COMPATIBLE
        # Ignores the requested Anthropic provider
    finally:
        settings_module.settings = settings_module.Settings()
        set_openai_compat_model(None)


@patch.dict(
    os.environ,
    {
        "SHOTGUN_OPENAI_COMPAT_BASE_URL": "https://api.example.com/v1",
        "SHOTGUN_OPENAI_COMPAT_API_KEY": "test-compat-key",
    },
    clear=False,
)
@pytest.mark.asyncio
async def test_get_provider_model_openai_compatible_sub_agent_model():
    """Test get_provider_model uses --sub-agent-model for sub-agents."""
    from shotgun import settings as settings_module
    from shotgun.agents.config.provider import (
        set_openai_compat_model,
        set_openai_compat_sub_agent_model,
    )

    settings_module.settings = settings_module.Settings()
    set_openai_compat_model("gpt-5.2")
    set_openai_compat_sub_agent_model("gpt-5.1")

    try:
        # Router model (for_sub_agent=False) should use main model
        router_model = await get_provider_model(for_sub_agent=False)
        assert isinstance(router_model, ModelConfig)
        assert router_model.name == "gpt-5.2"
        assert router_model.provider == ProviderType.OPENAI_COMPATIBLE

        # Sub-agent model (for_sub_agent=True) should use sub-agent model
        sub_agent_model = await get_provider_model(for_sub_agent=True)
        assert isinstance(sub_agent_model, ModelConfig)
        assert sub_agent_model.name == "gpt-5.1"
        assert sub_agent_model.provider == ProviderType.OPENAI_COMPATIBLE
    finally:
        settings_module.settings = settings_module.Settings()
        set_openai_compat_model(None)
        set_openai_compat_sub_agent_model(None)


@patch.dict(
    os.environ,
    {
        "SHOTGUN_OPENAI_COMPAT_BASE_URL": "https://api.example.com/v1",
        "SHOTGUN_OPENAI_COMPAT_API_KEY": "test-compat-key",
    },
    clear=False,
)
@pytest.mark.asyncio
async def test_get_provider_model_openai_compatible_sub_agent_fallback_to_main():
    """Test sub-agent uses main model when --sub-agent-model is not set."""
    from shotgun import settings as settings_module
    from shotgun.agents.config.provider import (
        set_openai_compat_model,
        set_openai_compat_sub_agent_model,
    )

    settings_module.settings = settings_module.Settings()
    set_openai_compat_model("gpt-5.2")
    set_openai_compat_sub_agent_model(None)  # Not set

    try:
        # Sub-agent should fall back to main model when sub-agent model not set
        sub_agent_model = await get_provider_model(for_sub_agent=True)
        assert isinstance(sub_agent_model, ModelConfig)
        assert sub_agent_model.name == "gpt-5.2"  # Falls back to main model
        assert sub_agent_model.provider == ProviderType.OPENAI_COMPATIBLE
    finally:
        settings_module.settings = settings_module.Settings()
        set_openai_compat_model(None)
        set_openai_compat_sub_agent_model(None)
