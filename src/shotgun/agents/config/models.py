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
    OPENAI_COMPATIBLE = "openai_compatible"


class KeyProvider(StrEnum):
    """Authentication method for accessing AI models."""

    BYOK = "byok"  # Bring Your Own Key (individual provider keys)
    SHOTGUN = "shotgun"  # Shotgun Account (unified LiteLLM proxy)


class ModelName(StrEnum):
    """Available AI model names."""

    GPT_5_1 = "gpt-5.1"
    GPT_5_2 = "gpt-5.2"
    CLAUDE_OPUS_4_5 = "claude-opus-4-5"
    CLAUDE_SONNET_4_5 = "claude-sonnet-4-5"
    CLAUDE_HAIKU_4_5 = "claude-haiku-4-5"
    GEMINI_2_5_FLASH_LITE = "gemini-2.5-flash-lite"
    GEMINI_3_PRO_PREVIEW = "gemini-3-pro-preview"
    GEMINI_3_FLASH_PREVIEW = "gemini-3-flash-preview"


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

    name: ModelName | str  # Model identifier (str for OpenAI-compatible endpoints)
    provider: ProviderType  # Actual LLM provider (openai, anthropic, google, openai_compatible)
    key_provider: KeyProvider  # Authentication method (byok or shotgun)
    max_input_tokens: int
    max_output_tokens: int
    api_key: str
    supports_streaming: bool = Field(
        default=True,
        description="Whether this model configuration supports streaming. False only for BYOK GPT-5 models without streaming enabled.",
    )
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
    def name_str(self) -> str:
        """Get the model name as a string.

        Handles both ModelName enum and plain string (for OpenAI-compatible).
        """
        if isinstance(self.name, str):
            return self.name
        return self.name.value

    @property
    def pydantic_model_name(self) -> str:
        """Compute the full Pydantic AI model identifier. For backward compatibility."""
        if self.provider == ProviderType.OPENAI_COMPATIBLE:
            # For OpenAI-compatible endpoints, use openai prefix with the model name
            return f"openai:{self.name_str}"
        provider_prefix = {
            ProviderType.OPENAI: "openai",
            ProviderType.ANTHROPIC: "anthropic",
            ProviderType.GOOGLE: "google-gla",
        }
        return f"{provider_prefix[self.provider]}:{self.name_str}"

    @property
    def is_shotgun_account(self) -> bool:
        """Check if this model is using Shotgun Account authentication.

        Returns:
            True if using Shotgun Account, False if BYOK
        """
        return self.key_provider == KeyProvider.SHOTGUN


# Model specifications registry (static metadata)
MODEL_SPECS: dict[ModelName, ModelSpec] = {
    ModelName.GPT_5_1: ModelSpec(
        name=ModelName.GPT_5_1,
        provider=ProviderType.OPENAI,
        max_input_tokens=272_000,
        max_output_tokens=128_000,
        litellm_proxy_model_name="openai/gpt-5.1",
        short_name="GPT-5.1",
    ),
    ModelName.GPT_5_2: ModelSpec(
        name=ModelName.GPT_5_2,
        provider=ProviderType.OPENAI,
        max_input_tokens=272_000,
        max_output_tokens=128_000,
        litellm_proxy_model_name="openai/gpt-5.2",
        short_name="GPT-5.2",
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
    ModelName.CLAUDE_OPUS_4_5: ModelSpec(
        name=ModelName.CLAUDE_OPUS_4_5,
        provider=ProviderType.ANTHROPIC,
        max_input_tokens=200_000,
        max_output_tokens=64_000,
        litellm_proxy_model_name="anthropic/claude-opus-4-5",
        short_name="Opus 4.5",
    ),
    ModelName.GEMINI_2_5_FLASH_LITE: ModelSpec(
        name=ModelName.GEMINI_2_5_FLASH_LITE,
        provider=ProviderType.GOOGLE,
        max_input_tokens=1_048_576,
        max_output_tokens=65_536,
        litellm_proxy_model_name="gemini/gemini-2.5-flash-lite",
        short_name="Gemini 2.5 Flash Lite",
    ),
    ModelName.GEMINI_3_PRO_PREVIEW: ModelSpec(
        name=ModelName.GEMINI_3_PRO_PREVIEW,
        provider=ProviderType.GOOGLE,
        max_input_tokens=1_048_576,
        max_output_tokens=65_536,
        litellm_proxy_model_name="gemini/gemini-3-pro-preview",
        short_name="Gemini 3 Pro",
    ),
    ModelName.GEMINI_3_FLASH_PREVIEW: ModelSpec(
        name=ModelName.GEMINI_3_FLASH_PREVIEW,
        provider=ProviderType.GOOGLE,
        max_input_tokens=1_048_576,
        max_output_tokens=65_536,
        litellm_proxy_model_name="gemini/gemini-3-flash-preview",
        short_name="Gemini 3 Flash",
    ),
}

# Sub-agent model mappings for cost optimization
# Maps expensive models to cheaper alternatives from the same provider
SUB_AGENT_MODEL_MAPPINGS: dict[ModelName, ModelName] = {
    # Anthropic: premium models use Haiku for sub-agents
    ModelName.CLAUDE_OPUS_4_5: ModelName.CLAUDE_HAIKU_4_5,
    ModelName.CLAUDE_SONNET_4_5: ModelName.CLAUDE_HAIKU_4_5,
    # Gemini: Pro uses Flash for sub-agents
    ModelName.GEMINI_3_PRO_PREVIEW: ModelName.GEMINI_3_FLASH_PREVIEW,
    # OpenAI: 5.2 uses 5.1 for sub-agents
    ModelName.GPT_5_2: ModelName.GPT_5_1,
}


def get_sub_agent_model(main_model: ModelName) -> ModelName:
    """Get the cheaper model for sub-agents, or same model if no cheaper alternative."""
    return SUB_AGENT_MODEL_MAPPINGS.get(main_model, main_model)


class OpenAIConfig(BaseModel):
    """Configuration for OpenAI provider."""

    api_key: SecretStr | None = None
    supports_streaming: bool | None = Field(
        default=None,
        description="Whether streaming is supported for this API key. None = not tested yet",
    )


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
    workspace_id: str | None = Field(
        default=None, description="Default workspace ID for shared specs"
    )

    @property
    def has_valid_account(self) -> bool:
        """Check if the user has a valid Shotgun Account configured.

        Returns:
            True if api_key is set and non-empty, False otherwise
        """
        if self.api_key is None:
            return False
        value = self.api_key.get_secret_value()
        return bool(value and value.strip())


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
    config_version: int = Field(default=5, description="Configuration schema version")
    shown_welcome_screen: bool = Field(
        default=False,
        description="Whether the welcome screen has been shown to the user",
    )
    marketing: MarketingConfig = Field(
        default_factory=MarketingConfig,
        description="Marketing messages configuration and tracking",
    )
    migration_failed: bool = Field(
        default=False,
        description="Whether the last config migration failed (cleared after user configures a provider)",
    )
    migration_backup_path: str | None = Field(
        default=None,
        description="Path to the backup file created when migration failed",
    )
    router_mode: str = Field(
        default="planning",
        description="Router execution mode: 'planning' or 'drafting'",
    )
