"""Pydantic models for configuration."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, PrivateAttr, SecretStr
from pydantic_ai.direct import model_request
from pydantic_ai.messages import ModelMessage, ModelResponse
from pydantic_ai.models import Model
from pydantic_ai.settings import ModelSettings


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

    def get_model_settings(self, max_tokens: int | None = None) -> ModelSettings:
        """Get ModelSettings with optional token override.

        This provides flexibility for specific use cases that need different
        token limits while defaulting to maximum utilization.

        Args:
            max_tokens: Optional override for max_tokens. If None, uses max_output_tokens

        Returns:
            ModelSettings configured with specified or maximum tokens
        """
        return ModelSettings(
            max_tokens=max_tokens if max_tokens is not None else self.max_output_tokens
        )


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
        max_output_tokens=8_192,
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


async def shotgun_model_request(
    model_config: ModelConfig,
    messages: list[ModelMessage],
    max_tokens: int | None = None,
    **kwargs: Any,
) -> ModelResponse:
    """Model request wrapper that uses full token capacity by default.

    This wrapper ensures all LLM calls in Shotgun use the maximum available
    token capacity of each model, improving response quality and completeness.
    The most common issue this fixes is truncated summaries that were cut off
    at default token limits (e.g., 4096 for Claude models).

    Args:
        model_config: ModelConfig instance with model settings and API key
        messages: Messages to send to the model
        max_tokens: Optional override for max_tokens. If None, uses model's max_output_tokens
        **kwargs: Additional arguments passed to model_request

    Returns:
        ModelResponse from the model

    Example:
        # Uses full token capacity (e.g., 4096 for Claude, 128k for GPT-5)
        response = await shotgun_model_request(model_config, messages)

        # Override for specific use case
        response = await shotgun_model_request(model_config, messages, max_tokens=1000)
    """
    # Get properly configured ModelSettings with maximum or overridden token limit
    model_settings = model_config.get_model_settings(max_tokens)

    # Make the model request with full token utilization
    return await model_request(
        model=model_config.model_instance,
        messages=messages,
        model_settings=model_settings,
        **kwargs,
    )
