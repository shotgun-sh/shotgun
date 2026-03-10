"""Pydantic models for configuration."""

from datetime import datetime
from enum import StrEnum
from typing import TypeGuard

from pydantic import BaseModel, Field, PrivateAttr, SecretStr
from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModelSettings


class ProviderType(StrEnum):
    """Provider types for AI services."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"
    OPENAI_COMPATIBLE = "openai_compatible"


class KeyProvider(StrEnum):
    """Authentication method for accessing AI models."""

    BYOK = "byok"  # Bring Your Own Key (individual provider keys)
    SHOTGUN = "shotgun"  # Shotgun Account (unified LiteLLM proxy)
    OPENROUTER = "openrouter"  # OpenRouter (multi-model API aggregator)


ANTHROPIC_ROUTER_CACHE_SETTINGS = AnthropicModelSettings(
    anthropic_cache_tool_definitions="1h",
    anthropic_cache_instructions="1h",
    anthropic_cache_messages="1h",
)

ANTHROPIC_SUB_AGENT_CACHE_SETTINGS = AnthropicModelSettings(
    anthropic_cache_tool_definitions="1h",
    anthropic_cache_instructions="1h",
    anthropic_cache_messages="5m",
)


class ModelName(StrEnum):
    """Available AI model names."""

    GPT_5_1 = "gpt-5.1"
    GPT_5_2 = "gpt-5.2"
    GPT_5_4 = "gpt-5.4"
    GPT_5_4_PRO = "gpt-5.4-pro"
    CLAUDE_OPUS_4_6 = "claude-opus-4-6"
    CLAUDE_SONNET_4_6 = "claude-sonnet-4-6"
    CLAUDE_HAIKU_4_5 = "claude-haiku-4-5"
    GEMINI_2_5_FLASH_LITE = "gemini-2.5-flash-lite"
    GEMINI_3_1_PRO_PREVIEW = "gemini-3.1-pro-preview"
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
    openrouter_model_name: str  # OpenRouter format (e.g., "anthropic/claude-opus-4-6", "google/gemini-3.1-pro-preview")
    short_name: str  # Display name for UI (e.g., "Sonnet 4.6", "GPT-5")


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
    supports_pdf: bool = Field(
        default=True,
        description="Whether this model supports PDF file input. False for Ollama models.",
    )
    supports_images: bool = Field(
        default=True,
        description="Whether this model supports image file input. Depends on model capabilities for Ollama.",
    )
    base_url: str | None = Field(
        default=None,
        description="Base URL for OpenAI-compatible endpoints (e.g., Ollama). If not set, uses settings.",
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
                self.provider, self.key_provider, self.name, self.api_key, self.base_url
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

    @property
    def is_openrouter(self) -> bool:
        """Check if this model is using OpenRouter authentication.

        Returns:
            True if using OpenRouter, False otherwise
        """
        return self.key_provider == KeyProvider.OPENROUTER


def get_model_display_name(name: "ModelName | str") -> str:
    """Get the UI display name for a model.

    For known ModelName enums, returns the short_name from MODEL_SPECS.
    For unknown strings (e.g. Ollama models), returns the string as-is.
    """
    if isinstance(name, ModelName):
        spec = MODEL_SPECS.get(name)
        return spec.short_name if spec else name.value
    return str(name)


# Model specifications registry (static metadata)
MODEL_SPECS: dict[ModelName, ModelSpec] = {
    ModelName.GPT_5_1: ModelSpec(
        name=ModelName.GPT_5_1,
        provider=ProviderType.OPENAI,
        max_input_tokens=272_000,
        max_output_tokens=128_000,
        litellm_proxy_model_name="openai/gpt-5.1",
        openrouter_model_name="openai/gpt-5.1",
        short_name="GPT-5.1",
    ),
    ModelName.GPT_5_2: ModelSpec(
        name=ModelName.GPT_5_2,
        provider=ProviderType.OPENAI,
        max_input_tokens=272_000,
        max_output_tokens=128_000,
        litellm_proxy_model_name="openai/gpt-5.2",
        openrouter_model_name="openai/gpt-5.2",
        short_name="GPT-5.2",
    ),
    ModelName.GPT_5_4: ModelSpec(
        name=ModelName.GPT_5_4,
        provider=ProviderType.OPENAI,
        max_input_tokens=272_000,
        max_output_tokens=128_000,
        litellm_proxy_model_name="openai/gpt-5.4",
        openrouter_model_name="openai/gpt-5.4",
        short_name="GPT-5.4",
    ),
    ModelName.GPT_5_4_PRO: ModelSpec(
        name=ModelName.GPT_5_4_PRO,
        provider=ProviderType.OPENAI,
        max_input_tokens=272_000,
        max_output_tokens=128_000,
        litellm_proxy_model_name="openai/gpt-5.4-pro",
        openrouter_model_name="openai/gpt-5.4-pro",
        short_name="GPT-5.4 Pro",
    ),
    ModelName.CLAUDE_SONNET_4_6: ModelSpec(
        name=ModelName.CLAUDE_SONNET_4_6,
        provider=ProviderType.ANTHROPIC,
        max_input_tokens=200_000,
        max_output_tokens=16_000,
        litellm_proxy_model_name="anthropic/claude-sonnet-4-6",
        openrouter_model_name="anthropic/claude-sonnet-4-6",
        short_name="Sonnet 4.6",
    ),
    ModelName.CLAUDE_HAIKU_4_5: ModelSpec(
        name=ModelName.CLAUDE_HAIKU_4_5,
        provider=ProviderType.ANTHROPIC,
        max_input_tokens=200_000,
        max_output_tokens=64_000,
        litellm_proxy_model_name="anthropic/claude-haiku-4-5",
        openrouter_model_name="anthropic/claude-haiku-4-5",
        short_name="Haiku 4.5",
    ),
    ModelName.CLAUDE_OPUS_4_6: ModelSpec(
        name=ModelName.CLAUDE_OPUS_4_6,
        provider=ProviderType.ANTHROPIC,
        max_input_tokens=200_000,
        max_output_tokens=64_000,
        litellm_proxy_model_name="anthropic/claude-opus-4-6",
        openrouter_model_name="anthropic/claude-opus-4-6",
        short_name="Opus 4.6",
    ),
    ModelName.GEMINI_2_5_FLASH_LITE: ModelSpec(
        name=ModelName.GEMINI_2_5_FLASH_LITE,
        provider=ProviderType.GOOGLE,
        max_input_tokens=1_048_576,
        max_output_tokens=65_536,
        litellm_proxy_model_name="gemini/gemini-2.5-flash-lite",
        openrouter_model_name="google/gemini-2.5-flash-lite",
        short_name="Gemini 2.5 Flash Lite",
    ),
    ModelName.GEMINI_3_1_PRO_PREVIEW: ModelSpec(
        name=ModelName.GEMINI_3_1_PRO_PREVIEW,
        provider=ProviderType.GOOGLE,
        max_input_tokens=1_048_576,
        max_output_tokens=65_536,
        litellm_proxy_model_name="gemini/gemini-3.1-pro-preview",
        openrouter_model_name="google/gemini-3.1-pro-preview",
        short_name="Gemini 3.1 Pro",
    ),
    ModelName.GEMINI_3_FLASH_PREVIEW: ModelSpec(
        name=ModelName.GEMINI_3_FLASH_PREVIEW,
        provider=ProviderType.GOOGLE,
        max_input_tokens=1_048_576,
        max_output_tokens=65_536,
        litellm_proxy_model_name="gemini/gemini-3-flash-preview",
        openrouter_model_name="google/gemini-3-flash-preview",
        short_name="Gemini 3 Flash",
    ),
}

# Default model for each provider (used when auto-selecting models)
DEFAULT_PROVIDER_MODELS: dict[ProviderType, ModelName] = {
    ProviderType.OPENAI: ModelName.GPT_5_2,
    ProviderType.ANTHROPIC: ModelName.CLAUDE_OPUS_4_6,
    ProviderType.GOOGLE: ModelName.GEMINI_3_1_PRO_PREVIEW,
}

# Sub-agent model mappings for cost optimization
# Maps expensive models to cheaper alternatives from the same provider
SUB_AGENT_MODEL_MAPPINGS: dict[ModelName, ModelName] = {
    # Anthropic: premium models use Haiku for sub-agents
    ModelName.CLAUDE_OPUS_4_6: ModelName.CLAUDE_HAIKU_4_5,
    ModelName.CLAUDE_SONNET_4_6: ModelName.CLAUDE_HAIKU_4_5,
    # Gemini: Pro uses Flash for sub-agents
    ModelName.GEMINI_3_1_PRO_PREVIEW: ModelName.GEMINI_3_FLASH_PREVIEW,
    # OpenAI: premium models use 5.1 for sub-agents
    ModelName.GPT_5_2: ModelName.GPT_5_1,
    ModelName.GPT_5_4: ModelName.GPT_5_1,
    ModelName.GPT_5_4_PRO: ModelName.GPT_5_1,
}


def get_sub_agent_model(main_model: ModelName) -> ModelName:
    """Get the cheaper model for sub-agents, or same model if no cheaper alternative."""
    return SUB_AGENT_MODEL_MAPPINGS.get(main_model, main_model)


def resolve_model_name(model_str: str) -> ModelName | None:
    """Resolve a user-provided model string to a ModelName enum.

    Accepts:
      - Direct enum values: "claude-sonnet-4-6"
      - Provider-prefixed: "anthropic/claude-sonnet-4-6"
      - LiteLLM format: "gemini/gemini-3.1-pro-preview" (matches litellm_proxy_model_name)

    Args:
        model_str: User-provided model name string.

    Returns:
        Resolved ModelName or None if unrecognized.
    """
    # Try direct enum match
    for model_name in ModelName:
        if model_str == model_name.value:
            return model_name

    # Try matching against provider-prefixed formats
    for model_name, spec in MODEL_SPECS.items():
        if model_str == spec.litellm_proxy_model_name:
            return model_name
        if model_str == spec.openrouter_model_name:
            return model_name

    return None


def get_valid_model_names() -> list[str]:
    """Return all valid ModelName values for error messages.

    Returns:
        List of all ModelName string values.
    """
    return [m.value for m in ModelName]


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
    tier: int | None = Field(
        default=None,
        description="Detected API tier (1-4). None if not detected, -1 if failed.",
    )


class GoogleConfig(BaseModel):
    """Configuration for Google provider."""

    api_key: SecretStr | None = None


class OpenRouterConfig(BaseModel):
    """Configuration for OpenRouter (multi-model API aggregator)."""

    api_key: SecretStr | None = None


# OpenRouter API base URL
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


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


# Ollama model name prefix - used to identify Ollama models in config
# Format: "ollama/<model_name>" (e.g., "ollama/llama3:8b")
OLLAMA_MODEL_PREFIX = "ollama/"

# Placeholder API key for Ollama (which doesn't require authentication)
OLLAMA_PLACEHOLDER_API_KEY = "ollama"


def is_ollama_model(model_name: ModelName | str | None) -> TypeGuard[str]:
    """Check if a model name represents an Ollama model.

    This is a TypeGuard that narrows the type to str when True.

    Args:
        model_name: Model name (ModelName enum, string, or None).

    Returns:
        True if model name is a string starting with the Ollama prefix.
    """
    return isinstance(model_name, str) and model_name.startswith(OLLAMA_MODEL_PREFIX)


def get_ollama_model_name(prefixed_name: str) -> str:
    """Extract the actual Ollama model name from a prefixed name.

    Args:
        prefixed_name: Model name with "ollama/" prefix.

    Returns:
        Model name without the prefix.
    """
    return prefixed_name.removeprefix(OLLAMA_MODEL_PREFIX)


def get_ollama_api_base_url(base_url: str) -> str:
    """Get the OpenAI-compatible API base URL for Ollama.

    Ollama's OpenAI-compatible API is at /v1/chat/completions, so we need
    to append /v1 to the base URL if not already present.

    Args:
        base_url: Ollama base URL (e.g., "http://localhost:11434").

    Returns:
        API base URL with /v1 suffix (e.g., "http://localhost:11434/v1").
    """
    base_url = base_url.rstrip("/")
    if not base_url.endswith("/v1"):
        base_url = f"{base_url}/v1"
    return base_url


class OllamaConfig(BaseModel):
    """Configuration for local Ollama provider."""

    enabled: bool = Field(
        default=False,
        description="Whether Ollama is enabled as a provider",
    )
    base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama API base URL",
    )


class Context7Config(BaseModel):
    """Configuration for Context7 documentation MCP server (experimental)."""

    api_key: SecretStr | None = None


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
    openrouter: OpenRouterConfig = Field(default_factory=OpenRouterConfig)
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    context7: Context7Config = Field(default_factory=Context7Config)
    selected_model: ModelName | str | None = Field(
        default=None,
        description="User-selected model (ModelName enum or 'ollama/<model>' string)",
    )
    shotgun_instance_id: str = Field(
        description="Unique shotgun instance identifier (also used for anonymous telemetry)",
    )
    config_version: int = Field(default=12, description="Configuration schema version")
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
