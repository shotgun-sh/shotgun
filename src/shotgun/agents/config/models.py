"""Pydantic models for configuration."""

from enum import Enum

from pydantic import BaseModel, Field, SecretStr


class ProviderType(str, Enum):
    """Provider types for AI services."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"


class OpenAIConfig(BaseModel):
    """Configuration for OpenAI provider."""

    api_key: SecretStr | None = None


class AnthropicConfig(BaseModel):
    """Configuration for Anthropic provider."""

    api_key: SecretStr | None = None


class GoogleConfig(BaseModel):
    """Configuration for Google provider."""

    api_key: SecretStr | None = None


class ShotgunConfig(BaseModel):
    """Main configuration for Shotgun CLI."""

    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)
    anthropic: AnthropicConfig = Field(default_factory=AnthropicConfig)
    google: GoogleConfig = Field(default_factory=GoogleConfig)
    default_provider: ProviderType = Field(
        default=ProviderType.OPENAI, description="Default AI provider to use"
    )
