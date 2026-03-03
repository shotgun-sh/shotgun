"""Tests for agents.config.models module."""

from shotgun.agents.config.models import (
    MODEL_SPECS,
    KeyProvider,
    ModelConfig,
    ModelName,
    OllamaConfig,
    ProviderType,
    get_valid_model_names,
    resolve_model_name,
)


def test_model_spec_short_name_claude_sonnet():
    """Test ModelSpec short_name for Claude Sonnet 4.6."""
    spec = MODEL_SPECS[ModelName.CLAUDE_SONNET_4_6]
    assert spec.short_name == "Sonnet 4.6"


def test_model_spec_short_name_claude_opus():
    """Test ModelSpec short_name for Claude Opus 4.6."""
    spec = MODEL_SPECS[ModelName.CLAUDE_OPUS_4_6]
    assert spec.short_name == "Opus 4.6"


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


def test_model_spec_short_name_gemini_3_1_pro():
    """Test ModelSpec short_name for Gemini 3.1 Pro."""
    spec = MODEL_SPECS[ModelName.GEMINI_3_1_PRO_PREVIEW]
    assert spec.short_name == "Gemini 3.1 Pro"


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


def test_resolve_model_name_exact_match():
    """Test resolve_model_name with exact enum value."""
    assert resolve_model_name("claude-sonnet-4-6") == ModelName.CLAUDE_SONNET_4_6
    assert resolve_model_name("gpt-5.2") == ModelName.GPT_5_2
    assert (
        resolve_model_name("gemini-3.1-pro-preview") == ModelName.GEMINI_3_1_PRO_PREVIEW
    )


def test_resolve_model_name_provider_prefixed():
    """Test resolve_model_name with provider-prefixed format."""
    assert (
        resolve_model_name("anthropic/claude-sonnet-4-6") == ModelName.CLAUDE_SONNET_4_6
    )
    assert resolve_model_name("openai/gpt-5.2") == ModelName.GPT_5_2


def test_resolve_model_name_litellm_format():
    """Test resolve_model_name with LiteLLM format."""
    assert (
        resolve_model_name("gemini/gemini-3.1-pro-preview")
        == ModelName.GEMINI_3_1_PRO_PREVIEW
    )
    assert (
        resolve_model_name("gemini/gemini-3-flash-preview")
        == ModelName.GEMINI_3_FLASH_PREVIEW
    )


def test_resolve_model_name_openrouter_format():
    """Test resolve_model_name with OpenRouter format (different from LiteLLM for Google)."""
    assert (
        resolve_model_name("google/gemini-3.1-pro-preview")
        == ModelName.GEMINI_3_1_PRO_PREVIEW
    )


def test_resolve_model_name_unknown_returns_none():
    """Test resolve_model_name returns None for unknown models."""
    assert resolve_model_name("fake-model-999") is None
    assert resolve_model_name("unknown/model") is None
    assert resolve_model_name("") is None


def test_get_valid_model_names_returns_all_values():
    """Test get_valid_model_names returns all ModelName values."""
    valid = get_valid_model_names()
    assert len(valid) == len(ModelName)
    for model_name in ModelName:
        assert model_name.value in valid
