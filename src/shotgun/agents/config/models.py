"""Pydantic models for configuration."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, PrivateAttr, SecretStr
from pydantic_ai.models import Model


class ProviderType(StrEnum):
    """Provider types for AI services."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"


class KeyProvider(StrEnum):
    """Authentication method for accessing AI models."""

    BYOK = "byok"  # Bring Your Own Key (individual provider keys)
    SHOTGUN = "shotgun"  # Shotgun Account (unified LiteLLM proxy)


class ModelName(StrEnum):
    """Available AI model names."""

    GPT_5 = "gpt-5"
    GPT_5_MINI = "gpt-5-mini"
    CLAUDE_OPUS_4_1 = "claude-opus-4-1"
    CLAUDE_SONNET_4_5 = "claude-sonnet-4-5"
    CLAUDE_HAIKU_4_5 = "claude-haiku-4-5"
    GEMINI_2_5_PRO = "gemini-2.5-pro"
    GEMINI_2_5_FLASH = "gemini-2.5-flash"


class ModelSpec(BaseModel):
    """Static specification for a model - just metadata."""

    name: ModelName  # Model identifier
    provider: ProviderType
    max_input_tokens: int
    max_output_tokens: int
    litellm_proxy_model_name: (
        str  # LiteLLM format (e.g., "openai/gpt-5", "gemini/gemini-2-pro")
    )
    short_name: str  # Display name for UI (e.g., "Sonnet 4.5", "GPT-5")


class ModelConfig(BaseModel):
    """A fully configured model with API key and settings."""

    name: ModelName  # Model identifier
    provider: ProviderType  # Actual LLM provider (openai, anthropic, google)
    key_provider: KeyProvider  # Authentication method (byok or shotgun)
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
                self.provider, self.key_provider, self.name, self.api_key
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
MODEL_SPECS: dict[ModelName, ModelSpec] = {
    ModelName.GPT_5: ModelSpec(
        name=ModelName.GPT_5,
        provider=ProviderType.OPENAI,
        max_input_tokens=400_000,
        max_output_tokens=128_000,
        litellm_proxy_model_name="openai/gpt-5",
        short_name="GPT-5",
    ),
    ModelName.GPT_5_MINI: ModelSpec(
        name=ModelName.GPT_5_MINI,
        provider=ProviderType.OPENAI,
        max_input_tokens=400_000,
        max_output_tokens=128_000,
        litellm_proxy_model_name="openai/gpt-5-mini",
        short_name="GPT-5 Mini",
    ),
    ModelName.CLAUDE_OPUS_4_1: ModelSpec(
        name=ModelName.CLAUDE_OPUS_4_1,
        provider=ProviderType.ANTHROPIC,
        max_input_tokens=200_000,
        max_output_tokens=32_000,
        litellm_proxy_model_name="anthropic/claude-opus-4-1",
        short_name="Opus 4.1",
    ),
    ModelName.CLAUDE_SONNET_4_5: ModelSpec(
        name=ModelName.CLAUDE_SONNET_4_5,
        provider=ProviderType.ANTHROPIC,
        max_input_tokens=200_000,
        max_output_tokens=16_000,
        litellm_proxy_model_name="anthropic/claude-sonnet-4-5",
        short_name="Sonnet 4.5",
    ),
    ModelName.CLAUDE_HAIKU_4_5: ModelSpec(
        name=ModelName.CLAUDE_HAIKU_4_5,
        provider=ProviderType.ANTHROPIC,
        max_input_tokens=200_000,
        max_output_tokens=64_000,
        litellm_proxy_model_name="anthropic/claude-haiku-4-5",
        short_name="Haiku 4.5",
    ),
    ModelName.GEMINI_2_5_PRO: ModelSpec(
        name=ModelName.GEMINI_2_5_PRO,
        provider=ProviderType.GOOGLE,
        max_input_tokens=1_000_000,
        max_output_tokens=64_000,
        litellm_proxy_model_name="gemini/gemini-2.5-pro",
        short_name="Gemini 2.5 Pro",
    ),
    ModelName.GEMINI_2_5_FLASH: ModelSpec(
        name=ModelName.GEMINI_2_5_FLASH,
        provider=ProviderType.GOOGLE,
        max_input_tokens=1_000_000,
        max_output_tokens=64_000,
        litellm_proxy_model_name="gemini/gemini-2.5-flash",
        short_name="Gemini 2.5 Flash",
    ),
}


class OpenAIConfig(BaseModel):
    """Configuration for OpenAI provider."""

    api_key: SecretStr | None = None


class AnthropicConfig(BaseModel):
    """Configuration for Anthropic provider."""

    api_key: SecretStr | None = None


class GoogleConfig(BaseModel):
    """Configuration for Google provider."""

    api_key: SecretStr | None = None


class ShotgunAccountConfig(BaseModel):
    """Configuration for Shotgun Account (LiteLLM proxy)."""

    api_key: SecretStr | None = None
    supabase_jwt: SecretStr | None = Field(
        default=None, description="Supabase authentication JWT"
    )


class MarketingMessageRecord(BaseModel):
    """Record of when a marketing message was shown to the user."""

    shown_at: datetime = Field(description="Timestamp when the message was shown")


class MarketingConfig(BaseModel):
    """Configuration for marketing messages shown to users."""

    messages: dict[str, MarketingMessageRecord] = Field(
        default_factory=dict,
        description="Tracking which marketing messages have been shown. Key is message ID (e.g., 'github_star_v1')",
    )


class ShotgunConfig(BaseModel):
    """Main configuration for Shotgun CLI."""

    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)
    anthropic: AnthropicConfig = Field(default_factory=AnthropicConfig)
    google: GoogleConfig = Field(default_factory=GoogleConfig)
    shotgun: ShotgunAccountConfig = Field(default_factory=ShotgunAccountConfig)
    selected_model: ModelName | None = Field(
        default=None,
        description="User-selected model",
    )
    shotgun_instance_id: str = Field(
        description="Unique shotgun instance identifier (also used for anonymous telemetry)",
    )
    config_version: int = Field(default=4, description="Configuration schema version")
    shown_welcome_screen: bool = Field(
        default=False,
        description="Whether the welcome screen has been shown to the user",
    )
    marketing: MarketingConfig = Field(
        default_factory=MarketingConfig,
        description="Marketing messages configuration and tracking",
    )
