"""Tests for ModelConfig multimodal capability fields."""

from shotgun.agents.config.models import (
    KeyProvider,
    ModelConfig,
    ProviderType,
)


def test_model_config_default_capabilities():
    """Test that ModelConfig defaults to supporting PDF and images."""
    config = ModelConfig(
        name="claude-sonnet-4-5",
        provider=ProviderType.ANTHROPIC,
        key_provider=KeyProvider.BYOK,
        max_input_tokens=200_000,
        max_output_tokens=16_000,
        api_key="test-key",
    )
    assert config.supports_pdf is True
    assert config.supports_images is True


def test_model_config_ollama_no_pdf_support():
    """Test that Ollama models can disable PDF support."""
    config = ModelConfig(
        name="llama3:8b",
        provider=ProviderType.OPENAI_COMPATIBLE,
        key_provider=KeyProvider.BYOK,
        max_input_tokens=128_000,
        max_output_tokens=16_000,
        api_key="ollama",
        supports_pdf=False,
        supports_images=False,
        base_url="http://localhost:11434/v1",
    )
    assert config.supports_pdf is False
    assert config.supports_images is False


def test_model_config_ollama_vision_model():
    """Test that Ollama vision models support images but not PDFs."""
    config = ModelConfig(
        name="llava:7b",
        provider=ProviderType.OPENAI_COMPATIBLE,
        key_provider=KeyProvider.BYOK,
        max_input_tokens=128_000,
        max_output_tokens=16_000,
        api_key="ollama",
        supports_pdf=False,  # Ollama never supports PDFs
        supports_images=True,  # Vision model supports images
        base_url="http://localhost:11434/v1",
    )
    assert config.supports_pdf is False
    assert config.supports_images is True


def test_model_config_cloud_model_full_multimodal():
    """Test that cloud models support both PDF and images by default."""
    config = ModelConfig(
        name="gpt-5.1",
        provider=ProviderType.OPENAI,
        key_provider=KeyProvider.SHOTGUN,
        max_input_tokens=272_000,
        max_output_tokens=128_000,
        api_key="shotgun-key",
    )
    assert config.supports_pdf is True
    assert config.supports_images is True


def test_model_config_explicit_capability_override():
    """Test that capabilities can be explicitly set."""
    config = ModelConfig(
        name="custom-model",
        provider=ProviderType.OPENAI_COMPATIBLE,
        key_provider=KeyProvider.BYOK,
        max_input_tokens=50_000,
        max_output_tokens=10_000,
        api_key="test",
        supports_pdf=True,
        supports_images=False,
    )
    assert config.supports_pdf is True
    assert config.supports_images is False
