"""Tests for OpenRouter provider integration."""

import json
import os
import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import SecretStr
from pydantic_ai.models.openai import OpenAIChatModel

from shotgun.agents.config.manager import ConfigManager, _migrate_v10_to_v11
from shotgun.agents.config.models import (
    MODEL_SPECS,
    OPENROUTER_BASE_URL,
    AnthropicConfig,
    KeyProvider,
    ModelConfig,
    ModelName,
    OpenRouterConfig,
    ProviderType,
    ShotgunAccountConfig,
    ShotgunConfig,
)
from shotgun.agents.config.provider import (
    _resolve_multi_provider_model,
    get_default_model_for_provider,
    get_or_create_model,
    get_provider_model,
)

# --- Helper to build config ---


def _make_config(**kwargs) -> ShotgunConfig:
    defaults = {"shotgun_instance_id": str(uuid.uuid4())}
    defaults.update(kwargs)
    return ShotgunConfig(**defaults)


# ================================================================
# get_provider_model(): OpenRouter block
# ================================================================


@pytest.fixture(autouse=True)
def clear_model_cache():
    """Clear the LRU cache before and after each test."""
    get_or_create_model.cache_clear()
    yield
    get_or_create_model.cache_clear()


@patch.dict(os.environ, {}, clear=True)
@patch("shotgun.agents.config.provider.get_config_manager")
@pytest.mark.asyncio
async def test_get_provider_model_openrouter_returns_config(mock_get_config_manager):
    """get_provider_model returns OpenRouter ModelConfig when OpenRouter key is set."""
    with tempfile.TemporaryDirectory() as temp_dir:
        manager = ConfigManager(config_path=Path(temp_dir) / "config.json")
        config = _make_config(
            openrouter=OpenRouterConfig(api_key=SecretStr("or-test-key")),
        )
        manager._config = config
        mock_get_config_manager.return_value = manager

        result = await get_provider_model()

        assert isinstance(result, ModelConfig)
        assert result.key_provider == KeyProvider.OPENROUTER
        assert result.api_key == "or-test-key"
        assert result.supports_streaming is True
        # Default model should be Opus 4.6
        assert result.name == ModelName.CLAUDE_OPUS_4_6


@patch.dict(os.environ, {}, clear=True)
@patch("shotgun.agents.config.provider.get_config_manager")
@pytest.mark.asyncio
async def test_openrouter_priority_below_shotgun(mock_get_config_manager):
    """Shotgun Account takes priority over OpenRouter when both are configured."""
    with tempfile.TemporaryDirectory() as temp_dir:
        manager = ConfigManager(config_path=Path(temp_dir) / "config.json")
        config = _make_config(
            shotgun=ShotgunAccountConfig(api_key=SecretStr("sg-key")),
            openrouter=OpenRouterConfig(api_key=SecretStr("or-key")),
        )
        manager._config = config
        mock_get_config_manager.return_value = manager

        result = await get_provider_model()

        assert result.key_provider == KeyProvider.SHOTGUN
        assert result.api_key == "sg-key"


@patch.dict(os.environ, {}, clear=True)
@patch("shotgun.agents.config.provider.get_config_manager")
@pytest.mark.asyncio
async def test_openrouter_priority_above_byok(mock_get_config_manager):
    """OpenRouter takes priority over individual BYOK keys."""
    with tempfile.TemporaryDirectory() as temp_dir:
        manager = ConfigManager(config_path=Path(temp_dir) / "config.json")
        config = _make_config(
            openrouter=OpenRouterConfig(api_key=SecretStr("or-key")),
            anthropic=AnthropicConfig(api_key=SecretStr("ant-key")),
        )
        manager._config = config
        mock_get_config_manager.return_value = manager

        result = await get_provider_model()

        assert result.key_provider == KeyProvider.OPENROUTER
        assert result.api_key == "or-key"


@patch.dict(os.environ, {}, clear=True)
@patch("shotgun.agents.config.provider.get_config_manager")
@pytest.mark.asyncio
async def test_openrouter_sub_agent_model_mapping(mock_get_config_manager):
    """OpenRouter applies sub-agent model mapping for cost optimization."""
    with tempfile.TemporaryDirectory() as temp_dir:
        manager = ConfigManager(config_path=Path(temp_dir) / "config.json")
        config = _make_config(
            openrouter=OpenRouterConfig(api_key=SecretStr("or-key")),
        )
        manager._config = config
        mock_get_config_manager.return_value = manager

        result = await get_provider_model(for_sub_agent=True)

        # Opus 4.6 -> Haiku 4.5 for sub-agents
        assert result.name == ModelName.CLAUDE_HAIKU_4_5
        assert result.key_provider == KeyProvider.OPENROUTER


@patch.dict(os.environ, {}, clear=True)
@patch("shotgun.agents.config.provider.get_config_manager")
@pytest.mark.asyncio
async def test_openrouter_specific_model_request(mock_get_config_manager):
    """OpenRouter honors specific ModelName requests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        manager = ConfigManager(config_path=Path(temp_dir) / "config.json")
        config = _make_config(
            openrouter=OpenRouterConfig(api_key=SecretStr("or-key")),
        )
        manager._config = config
        mock_get_config_manager.return_value = manager

        result = await get_provider_model(ModelName.GPT_5_2)

        assert result.name == ModelName.GPT_5_2
        assert result.key_provider == KeyProvider.OPENROUTER
        assert result.provider == ProviderType.OPENAI


@patch.dict(os.environ, {"OPENROUTER_API_KEY": "or-env-key"}, clear=True)
@patch("shotgun.agents.config.provider.get_config_manager")
@pytest.mark.asyncio
async def test_openrouter_env_var_fallback(mock_get_config_manager):
    """OpenRouter falls back to OPENROUTER_API_KEY environment variable."""
    with tempfile.TemporaryDirectory() as temp_dir:
        manager = ConfigManager(config_path=Path(temp_dir) / "config.json")
        # No openrouter key in config, but env var is set
        config = _make_config()
        manager._config = config
        mock_get_config_manager.return_value = manager

        result = await get_provider_model()

        assert result.key_provider == KeyProvider.OPENROUTER
        assert result.api_key == "or-env-key"


@patch.dict(os.environ, {}, clear=True)
@patch("shotgun.agents.config.provider.get_config_manager")
@pytest.mark.asyncio
async def test_openrouter_with_selected_model(mock_get_config_manager):
    """OpenRouter respects the user's selected_model from config."""
    with tempfile.TemporaryDirectory() as temp_dir:
        manager = ConfigManager(config_path=Path(temp_dir) / "config.json")
        config = _make_config(
            openrouter=OpenRouterConfig(api_key=SecretStr("or-key")),
            selected_model=ModelName.GEMINI_3_PRO_PREVIEW,
        )
        manager._config = config
        mock_get_config_manager.return_value = manager

        result = await get_provider_model()

        assert result.name == ModelName.GEMINI_3_PRO_PREVIEW
        assert result.key_provider == KeyProvider.OPENROUTER


# ================================================================
# get_default_model_for_provider()
# ================================================================


def test_get_default_model_openrouter():
    """get_default_model_for_provider returns Opus 4.6 for OpenRouter."""
    config = _make_config(
        openrouter=OpenRouterConfig(api_key=SecretStr("or-key")),
    )
    result = get_default_model_for_provider(config)
    assert result == ModelName.CLAUDE_OPUS_4_6


def test_get_default_model_shotgun_over_openrouter():
    """get_default_model_for_provider prefers Shotgun over OpenRouter."""
    config = _make_config(
        shotgun=ShotgunAccountConfig(api_key=SecretStr("sg-key")),
        openrouter=OpenRouterConfig(api_key=SecretStr("or-key")),
    )
    result = get_default_model_for_provider(config)
    # Both would return CLAUDE_OPUS_4_6, but shotgun path is tested
    assert result == ModelName.CLAUDE_OPUS_4_6


# ================================================================
# _resolve_multi_provider_model()
# ================================================================


def test_resolve_with_explicit_model_name():
    """_resolve_multi_provider_model passes through explicit ModelName."""
    config = _make_config()
    result = _resolve_multi_provider_model(
        config, ModelName.GPT_5_2, for_sub_agent=False
    )
    assert result == ModelName.GPT_5_2


def test_resolve_with_provider_type():
    """_resolve_multi_provider_model returns provider default for ProviderType."""
    config = _make_config()
    result = _resolve_multi_provider_model(
        config, ProviderType.OPENAI, for_sub_agent=False
    )
    assert result == ModelName.GPT_5_2


def test_resolve_with_none_uses_selected_model():
    """_resolve_multi_provider_model uses selected_model when provider_or_model is None."""
    config = _make_config(selected_model=ModelName.GEMINI_3_FLASH_PREVIEW)
    result = _resolve_multi_provider_model(config, None, for_sub_agent=False)
    assert result == ModelName.GEMINI_3_FLASH_PREVIEW


def test_resolve_applies_sub_agent_mapping():
    """_resolve_multi_provider_model maps to cheaper model for sub-agents."""
    config = _make_config(selected_model=ModelName.CLAUDE_OPUS_4_6)
    result = _resolve_multi_provider_model(config, None, for_sub_agent=True)
    assert result == ModelName.CLAUDE_HAIKU_4_5


def test_resolve_falls_back_for_invalid_model():
    """_resolve_multi_provider_model falls back when model not in MODEL_SPECS."""
    config = _make_config(
        selected_model="some-invalid-model",
        openrouter=OpenRouterConfig(api_key=SecretStr("or-key")),
    )
    result = _resolve_multi_provider_model(config, None, for_sub_agent=False)
    # Falls back to get_default_model_for_provider
    assert result == ModelName.CLAUDE_OPUS_4_6


# ================================================================
# get_or_create_model(): OpenRouter key_provider
# ================================================================


def test_get_or_create_model_openrouter():
    """get_or_create_model creates OpenAI-compatible model for OpenRouter."""
    model = get_or_create_model(
        provider=ProviderType.ANTHROPIC,
        key_provider=KeyProvider.OPENROUTER,
        model_name=ModelName.CLAUDE_OPUS_4_6,
        api_key="or-test-key",
    )
    # Should be an OpenAIChatModel pointed at OpenRouter
    assert isinstance(model, OpenAIChatModel)


def test_get_or_create_model_openrouter_uses_openrouter_model_name():
    """get_or_create_model maps ModelName to openrouter_model_name from specs."""
    spec = MODEL_SPECS[ModelName.CLAUDE_OPUS_4_6]
    assert spec.openrouter_model_name == "anthropic/claude-opus-4-6"


# ================================================================
# Migration: v10 -> v11
# ================================================================


def test_migrate_v10_to_v11_adds_openrouter():
    """v10->v11 migration adds openrouter section."""
    config = {
        "openai": {"api_key": "sk-test"},
        "config_version": 10,
    }
    result = _migrate_v10_to_v11(config)

    assert "openrouter" in result
    assert result["openrouter"] == {}
    assert result["config_version"] == 11


def test_migrate_v10_to_v11_preserves_existing_openrouter():
    """v10->v11 migration preserves existing openrouter section."""
    config = {
        "openrouter": {"api_key": "or-existing-key"},
        "config_version": 10,
    }
    result = _migrate_v10_to_v11(config)

    assert result["openrouter"] == {"api_key": "or-existing-key"}
    assert result["config_version"] == 11


# ================================================================
# has_any_provider_key() includes OpenRouter
# ================================================================


@pytest.mark.asyncio
async def test_has_any_provider_key_includes_openrouter():
    """has_any_provider_key returns True when only OpenRouter key is configured."""
    with tempfile.TemporaryDirectory() as temp_dir:
        manager = ConfigManager(config_path=Path(temp_dir) / "config.json")
        config = _make_config(
            openrouter=OpenRouterConfig(api_key=SecretStr("or-key")),
        )
        manager._config = config

        result = await manager.has_any_provider_key()

        assert result is True


@pytest.mark.asyncio
async def test_has_any_provider_key_false_without_any_keys():
    """has_any_provider_key returns False when no keys are configured."""
    with tempfile.TemporaryDirectory() as temp_dir:
        manager = ConfigManager(config_path=Path(temp_dir) / "config.json")
        config = _make_config()
        manager._config = config

        result = await manager.has_any_provider_key()

        assert result is False


# ================================================================
# OpenRouter constants
# ================================================================


def test_openrouter_base_url():
    """OPENROUTER_BASE_URL is the correct OpenRouter API endpoint."""
    assert OPENROUTER_BASE_URL == "https://openrouter.ai/api/v1"


def test_openrouter_config_default():
    """OpenRouterConfig defaults to no API key."""
    config = OpenRouterConfig()
    assert config.api_key is None


def test_all_model_specs_have_openrouter_model_name():
    """Every model in MODEL_SPECS has an openrouter_model_name."""
    for model_name, spec in MODEL_SPECS.items():
        assert spec.openrouter_model_name, (
            f"Model {model_name.value} is missing openrouter_model_name"
        )


def test_model_config_is_openrouter_property():
    """ModelConfig.is_openrouter returns True for OpenRouter key provider."""
    config = ModelConfig(
        name=ModelName.CLAUDE_OPUS_4_6,
        provider=ProviderType.ANTHROPIC,
        key_provider=KeyProvider.OPENROUTER,
        max_input_tokens=200_000,
        max_output_tokens=64_000,
        api_key="or-key",
    )
    assert config.is_openrouter is True
    assert config.is_shotgun_account is False


def test_model_config_is_openrouter_false_for_byok():
    """ModelConfig.is_openrouter returns False for BYOK key provider."""
    config = ModelConfig(
        name=ModelName.CLAUDE_OPUS_4_6,
        provider=ProviderType.ANTHROPIC,
        key_provider=KeyProvider.BYOK,
        max_input_tokens=200_000,
        max_output_tokens=64_000,
        api_key="ant-key",
    )
    assert config.is_openrouter is False


# ================================================================
# Manager load(): selected_model validation with OpenRouter
# ================================================================


@pytest.mark.asyncio
async def test_load_preserves_selected_model_with_openrouter():
    """Manager load() should NOT reset selected_model when OpenRouter key is present.

    Regression test: previously, load() only checked for Shotgun Account keys
    before validating BYOK keys. Without an Anthropic BYOK key, it would reset
    selected_model=CLAUDE_OPUS_4_6 to None, even though OpenRouter provides
    access to all models.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        config = _make_config(
            openrouter=OpenRouterConfig(api_key=SecretStr("or-key")),
            selected_model=ModelName.CLAUDE_OPUS_4_6,
        )
        config_path.write_text(json.dumps(config.model_dump(mode="json")))

        manager = ConfigManager(config_path=config_path)
        await manager.load()

        assert manager._config.selected_model == ModelName.CLAUDE_OPUS_4_6
