"""Pydantic models for configuration."""

from enum import Enum

from pydantic import BaseModel, Field, SecretStr


class ProviderType(str, Enum):
    """Provider types for AI services."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"


class ModelConfig(BaseModel):
    """Configuration for an LLM model."""

    name: str  # Model identifier (e.g., "gpt-5", "claude-opus-4-1")
    provider: ProviderType
    max_input_tokens: int
    max_output_tokens: int

    @property
    def pydantic_model_name(self) -> str:
        """Compute the full Pydantic AI model identifier."""
        provider_prefix = {
            ProviderType.OPENAI: "openai",
            ProviderType.ANTHROPIC: "anthropic",
            ProviderType.GOOGLE: "google-gla",
        }
        return f"{provider_prefix[self.provider]}:{self.name}"


# OpenAI Models
GPT_5 = ModelConfig(
    name="gpt-5",
    provider=ProviderType.OPENAI,
    max_input_tokens=400_000,
    max_output_tokens=128_000,
)

GPT_4O = ModelConfig(
    name="gpt-4o",
    provider=ProviderType.OPENAI,
    max_input_tokens=128_000,
    max_output_tokens=16_000,
)

# Anthropic Models
CLAUDE_OPUS_4_1 = ModelConfig(
    name="claude-opus-4-1",
    provider=ProviderType.ANTHROPIC,
    max_input_tokens=200_000,
    max_output_tokens=32_000,
)

CLAUDE_3_5_SONNET = ModelConfig(
    name="claude-3-5-sonnet-latest",
    provider=ProviderType.ANTHROPIC,
    max_input_tokens=200_000,
    max_output_tokens=20_000,
)

# Google Models
GEMINI_2_5_PRO = ModelConfig(
    name="gemini-2.5-pro",
    provider=ProviderType.GOOGLE,
    max_input_tokens=1_000_000,
    max_output_tokens=64_000,
)

# List of all available models
AVAILABLE_MODELS = [
    GPT_5,
    GPT_4O,
    CLAUDE_OPUS_4_1,
    CLAUDE_3_5_SONNET,
    GEMINI_2_5_PRO,
]


def get_model_by_name(name: str) -> ModelConfig:
    """Find a model configuration by name."""
    for model in AVAILABLE_MODELS:
        if model.name == name:
            return model
    raise ValueError(f"Model '{name}' not found")


class OpenAIConfig(BaseModel):
    """Configuration for OpenAI provider."""

    api_key: SecretStr | None = None
    model_name: str = "gpt-5"


class AnthropicConfig(BaseModel):
    """Configuration for Anthropic provider."""

    api_key: SecretStr | None = None
    model_name: str = "claude-opus-4-1"


class GoogleConfig(BaseModel):
    """Configuration for Google provider."""

    api_key: SecretStr | None = None
    model_name: str = "gemini-2.5-pro"


class ShotgunConfig(BaseModel):
    """Main configuration for Shotgun CLI."""

    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)
    anthropic: AnthropicConfig = Field(default_factory=AnthropicConfig)
    google: GoogleConfig = Field(default_factory=GoogleConfig)
    default_provider: ProviderType = Field(
        default=ProviderType.OPENAI, description="Default AI provider to use"
    )
