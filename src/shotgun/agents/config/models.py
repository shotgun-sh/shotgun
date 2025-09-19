"""Pydantic models for configuration."""

from enum import Enum

from pydantic import BaseModel, Field, PrivateAttr, SecretStr
from pydantic_ai.models import Model


class ProviderType(str, Enum):
    """Provider types for AI services."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"


class ModelSpec(BaseModel):
    """Static specification for a model - just metadata."""

    name: str  # Model identifier (e.g., "gpt-5", "claude-opus-4-1")
    provider: ProviderType
    max_input_tokens: int
    max_output_tokens: int


class ModelConfig(BaseModel):
    """A fully configured model with API key and settings."""

    name: str  # Model identifier (e.g., "gpt-5", "claude-opus-4-1")
    provider: ProviderType
    max_input_tokens: int
    max_output_tokens: int
    api_key: str
    _model_instance: Model | None = PrivateAttr(default=None)

    class Config:
        arbitrary_types_allowed = True

    @property
    def model_instance(self) -> Model:
        """Lazy load the Model instance."""
        if self._model_instance is None:
            from .provider import get_or_create_model

            self._model_instance = get_or_create_model(
                self.provider, self.name, self.api_key
            )
        return self._model_instance

    @property
    def pydantic_model_name(self) -> str:
        """Compute the full Pydantic AI model identifier. For backward compatibility."""
        provider_prefix = {
            ProviderType.OPENAI: "openai",
            ProviderType.ANTHROPIC: "anthropic",
            ProviderType.GOOGLE: "google-gla",
        }
        return f"{provider_prefix[self.provider]}:{self.name}"


# Model specifications registry (static metadata)
MODEL_SPECS: dict[str, ModelSpec] = {
    "gpt-5": ModelSpec(
        name="gpt-5",
        provider=ProviderType.OPENAI,
        max_input_tokens=400_000,
        max_output_tokens=128_000,
    ),
    "gpt-4o": ModelSpec(
        name="gpt-4o",
        provider=ProviderType.OPENAI,
        max_input_tokens=128_000,
        max_output_tokens=16_000,
    ),
    "claude-opus-4-1": ModelSpec(
        name="claude-opus-4-1",
        provider=ProviderType.ANTHROPIC,
        max_input_tokens=200_000,
        max_output_tokens=32_000,
    ),
    "claude-3-5-sonnet-latest": ModelSpec(
        name="claude-3-5-sonnet-latest",
        provider=ProviderType.ANTHROPIC,
        max_input_tokens=200_000,
        max_output_tokens=20_000,
    ),
    "gemini-2.5-pro": ModelSpec(
        name="gemini-2.5-pro",
        provider=ProviderType.GOOGLE,
        max_input_tokens=1_000_000,
        max_output_tokens=64_000,
    ),
}


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
    user_id: str = Field(description="Unique anonymous user identifier")
    config_version: int = Field(default=1, description="Configuration schema version")
