"""Tests for agents.config.models module."""

from shotgun.agents.config.models import (
    ANTHROPIC_ROUTER_CACHE_SETTINGS,
    ANTHROPIC_SUB_AGENT_CACHE_SETTINGS,
    MODEL_SPECS,
    OPENAI_CACHE_SETTINGS,
    KeyProvider,
    ModelConfig,
    ModelName,
    OllamaConfig,
    ProviderType,
    get_cache_settings,
)


def test_model_spec_short_name_claude_sonnet():
    """Test ModelSpec short_name for Claude Sonnet 4.5."""
    spec = MODEL_SPECS[ModelName.CLAUDE_SONNET_4_5]
    assert spec.short_name == "Sonnet 4.5"


def test_model_spec_short_name_claude_opus():
    """Test ModelSpec short_name for Claude Opus 4.5."""
    spec = MODEL_SPECS[ModelName.CLAUDE_OPUS_4_5]
    assert spec.short_name == "Opus 4.5"


def test_model_spec_short_name_claude_haiku():
    """Test ModelSpec short_name for Claude Haiku 4.5."""
    spec = MODEL_SPECS[ModelName.CLAUDE_HAIKU_4_5]
    assert spec.short_name == "Haiku 4.5"


def test_model_spec_short_name_gpt_5_1():
    """Test ModelSpec short_name for GPT-5.1."""
    spec = MODEL_SPECS[ModelName.GPT_5_1]
    assert spec.short_name == "GPT-5.1"


def test_model_spec_short_name_gpt_5_2():
    """Test ModelSpec short_name for GPT-5.2."""
    spec = MODEL_SPECS[ModelName.GPT_5_2]
    assert spec.short_name == "GPT-5.2"


def test_model_spec_short_name_gemini_3_pro():
    """Test ModelSpec short_name for Gemini 3 Pro."""
    spec = MODEL_SPECS[ModelName.GEMINI_3_PRO_PREVIEW]
    assert spec.short_name == "Gemini 3 Pro"


def test_model_spec_short_name_gemini_3_flash():
    """Test ModelSpec short_name for Gemini 3 Flash."""
    spec = MODEL_SPECS[ModelName.GEMINI_3_FLASH_PREVIEW]
    assert spec.short_name == "Gemini 3 Flash"


def test_all_models_have_short_name():
    """Test that all ModelName enum values have a short_name in MODEL_SPECS."""
    for model_name in ModelName:
        spec = MODEL_SPECS[model_name]
        # Should have a short_name field
        assert hasattr(spec, "short_name")
        # Should not return the enum string representation
        assert spec.short_name != str(model_name)
        # Should return a non-empty string
        assert len(spec.short_name) > 0


def test_ollama_config_default_values():
    """Test OllamaConfig has correct default values."""
    config = OllamaConfig()
    assert config.enabled is False
    assert config.base_url == "http://localhost:11434"


def test_ollama_config_custom_values():
    """Test OllamaConfig can be created with custom values."""
    config = OllamaConfig(enabled=True, base_url="http://192.168.1.100:11434")
    assert config.enabled is True
    assert config.base_url == "http://192.168.1.100:11434"


def test_model_config_base_url_default():
    """Test ModelConfig has None base_url by default."""
    config = ModelConfig(
        name=ModelName.GPT_5_2,
        provider=ProviderType.OPENAI,
        key_provider=KeyProvider.BYOK,
        max_input_tokens=128_000,
        max_output_tokens=16_000,
        api_key="test-key",
    )
    assert config.base_url is None


def test_model_config_with_base_url():
    """Test ModelConfig can have a base_url for OpenAI-compatible endpoints."""
    config = ModelConfig(
        name="qwen3:32b",
        provider=ProviderType.OPENAI_COMPATIBLE,
        key_provider=KeyProvider.BYOK,
        max_input_tokens=128_000,
        max_output_tokens=16_000,
        api_key="ollama",
        base_url="http://localhost:11434/v1",
    )
    assert config.base_url == "http://localhost:11434/v1"
    assert config.name == "qwen3:32b"
    assert config.provider == ProviderType.OPENAI_COMPATIBLE


def test_get_cache_settings_anthropic_router():
    """Test that Anthropic router gets 1h message cache settings."""
    settings = get_cache_settings(ProviderType.ANTHROPIC, is_router=True)
    assert settings is ANTHROPIC_ROUTER_CACHE_SETTINGS
    assert settings["anthropic_cache_messages"] == "1h"


def test_get_cache_settings_anthropic_sub_agent():
    """Test that Anthropic sub-agents get 5m message cache settings."""
    settings = get_cache_settings(ProviderType.ANTHROPIC, is_router=False)
    assert settings is ANTHROPIC_SUB_AGENT_CACHE_SETTINGS
    assert settings["anthropic_cache_messages"] == "5m"


def test_get_cache_settings_openai():
    """Test that OpenAI models get OpenAI-specific cache settings."""
    settings = get_cache_settings(ProviderType.OPENAI, is_router=True)
    assert settings is OPENAI_CACHE_SETTINGS


def test_get_cache_settings_openai_same_for_router_and_sub_agent():
    """Test that OpenAI cache settings are the same regardless of is_router."""
    router_settings = get_cache_settings(ProviderType.OPENAI, is_router=True)
    sub_agent_settings = get_cache_settings(ProviderType.OPENAI, is_router=False)
    assert router_settings == sub_agent_settings


def test_get_cache_settings_google_returns_empty():
    """Test that Google provider returns empty model settings."""
    settings = get_cache_settings(ProviderType.GOOGLE)
    assert settings == {}


def test_get_cache_settings_openai_compatible_returns_empty():
    """Test that OpenAI-compatible provider returns empty model settings."""
    settings = get_cache_settings(ProviderType.OPENAI_COMPATIBLE)
    assert settings == {}
