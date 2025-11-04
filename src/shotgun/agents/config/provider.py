"""Provider management for LLM configuration."""

from pydantic import SecretStr
from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel, AnthropicModelSettings
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

from shotgun.llm_proxy import (
    create_anthropic_proxy_provider,
    create_litellm_provider,
)
from shotgun.logging_config import get_logger

from .manager import get_config_manager
from .models import (
    MODEL_SPECS,
    KeyProvider,
    ModelConfig,
    ModelName,
    ProviderType,
    ShotgunConfig,
)

logger = get_logger(__name__)

# Global cache for Model instances (singleton pattern)
_model_cache: dict[tuple[ProviderType, KeyProvider, ModelName, str], Model] = {}


def get_default_model_for_provider(config: ShotgunConfig) -> ModelName:
    """Get the default model based on which provider/account is configured.

    Checks API keys in priority order and returns appropriate default model.
    Treats Shotgun Account as a provider context.

    Args:
        config: Shotgun configuration containing API keys

    Returns:
        Default ModelName for the configured provider/account
    """
    # Priority 1: Shotgun Account
    if _get_api_key(config.shotgun.api_key):
        return ModelName.GPT_5

    # Priority 2: Individual provider keys
    if _get_api_key(config.anthropic.api_key):
        return ModelName.CLAUDE_HAIKU_4_5
    if _get_api_key(config.openai.api_key):
        return ModelName.GPT_5
    if _get_api_key(config.google.api_key):
        return ModelName.GEMINI_2_5_PRO

    # Fallback: system-wide default
    return ModelName.CLAUDE_HAIKU_4_5


def get_or_create_model(
    provider: ProviderType,
    key_provider: "KeyProvider",
    model_name: ModelName,
    api_key: str,
) -> Model:
    """Get or create a singleton Model instance.

    Args:
        provider: Actual LLM provider (openai, anthropic, google)
        key_provider: Authentication method (byok or shotgun)
        model_name: Name of the model
        api_key: API key for the provider

    Returns:
        Cached or newly created Model instance

    Raises:
        ValueError: If provider is not supported
    """
    cache_key = (provider, key_provider, model_name, api_key)

    if cache_key not in _model_cache:
        logger.debug(
            "Creating new %s model instance via %s: %s",
            provider.value,
            key_provider.value,
            model_name,
        )

        # Get max_tokens from MODEL_SPECS
        if model_name in MODEL_SPECS:
            max_tokens = MODEL_SPECS[model_name].max_output_tokens
        else:
            # Fallback defaults based on provider
            max_tokens = {
                ProviderType.OPENAI: 16_000,
                ProviderType.ANTHROPIC: 32_000,
                ProviderType.GOOGLE: 64_000,
            }.get(provider, 16_000)

        # Use LiteLLM proxy for Shotgun Account, native providers for BYOK
        if key_provider == KeyProvider.SHOTGUN:
            # Shotgun Account uses LiteLLM proxy with native model types where possible
            if model_name in MODEL_SPECS:
                litellm_model_name = MODEL_SPECS[model_name].litellm_proxy_model_name
            else:
                # Fallback for unmapped models
                litellm_model_name = f"openai/{model_name.value}"

            # Use native provider types to preserve API formats and features
            if provider == ProviderType.ANTHROPIC:
                # Anthropic: Use native AnthropicProvider with /anthropic endpoint
                # This preserves Anthropic-specific features like tool_choice
                # Note: Web search for Shotgun Account uses Gemini only (not Anthropic)
                # Note: Anthropic API expects model name without prefix (e.g., "claude-sonnet-4-5")
                anthropic_provider = create_anthropic_proxy_provider(api_key)
                _model_cache[cache_key] = AnthropicModel(
                    model_name.value,  # Use model name without "anthropic/" prefix
                    provider=anthropic_provider,
                    settings=AnthropicModelSettings(
                        max_tokens=max_tokens,
                        timeout=600,  # 10 minutes timeout for large responses
                    ),
                )
            else:
                # OpenAI and Google: Use LiteLLMProvider (OpenAI-compatible format)
                # Google's GoogleProvider doesn't support base_url, so use LiteLLM
                litellm_provider = create_litellm_provider(api_key)
                _model_cache[cache_key] = OpenAIChatModel(
                    litellm_model_name,
                    provider=litellm_provider,
                    settings=ModelSettings(max_tokens=max_tokens),
                )
        elif key_provider == KeyProvider.BYOK:
            # Use native provider implementations with user's API keys
            if provider == ProviderType.OPENAI:
                openai_provider = OpenAIProvider(api_key=api_key)
                _model_cache[cache_key] = OpenAIChatModel(
                    model_name,
                    provider=openai_provider,
                    settings=ModelSettings(max_tokens=max_tokens),
                )
            elif provider == ProviderType.ANTHROPIC:
                anthropic_provider = AnthropicProvider(api_key=api_key)
                _model_cache[cache_key] = AnthropicModel(
                    model_name,
                    provider=anthropic_provider,
                    settings=AnthropicModelSettings(
                        max_tokens=max_tokens,
                        timeout=600,  # 10 minutes timeout for large responses
                    ),
                )
            elif provider == ProviderType.GOOGLE:
                google_provider = GoogleProvider(api_key=api_key)
                _model_cache[cache_key] = GoogleModel(
                    model_name,
                    provider=google_provider,
                    settings=ModelSettings(max_tokens=max_tokens),
                )
            else:
                raise ValueError(f"Unsupported provider: {provider}")
        else:
            raise ValueError(f"Unsupported key provider: {key_provider}")
    else:
        logger.debug("Reusing cached %s model instance: %s", provider.value, model_name)

    return _model_cache[cache_key]


async def get_provider_model(
    provider_or_model: ProviderType | ModelName | None = None,
) -> ModelConfig:
    """Get a fully configured ModelConfig with API key and Model instance.

    Args:
        provider_or_model: Either a ProviderType, ModelName, or None.
            - If ModelName: returns that specific model with appropriate API key
            - If ProviderType: returns default model for that provider (backward compatible)
            - If None: uses default provider with its default model

    Returns:
        ModelConfig with API key configured and lazy Model instance

    Raises:
        ValueError: If provider is not configured properly or model not found
    """
    config_manager = get_config_manager()
    # Use cached config for read-only access (performance)
    config = await config_manager.load(force_reload=False)

    # Priority 1: Check if Shotgun key exists - if so, use it for ANY model
    shotgun_api_key = _get_api_key(config.shotgun.api_key)
    if shotgun_api_key:
        # Determine which model to use
        if isinstance(provider_or_model, ModelName):
            # Specific model requested - honor it (e.g., web search tools)
            model_name = provider_or_model
        else:
            # No specific model requested - use selected or default
            model_name = config.selected_model or ModelName.GPT_5

        if model_name not in MODEL_SPECS:
            raise ValueError(f"Model '{model_name.value}' not found")
        spec = MODEL_SPECS[model_name]

        # Use Shotgun Account with determined model (provider = actual LLM provider)
        return ModelConfig(
            name=spec.name,
            provider=spec.provider,  # Actual LLM provider (OPENAI/ANTHROPIC/GOOGLE)
            key_provider=KeyProvider.SHOTGUN,  # Authenticated via Shotgun Account
            max_input_tokens=spec.max_input_tokens,
            max_output_tokens=spec.max_output_tokens,
            api_key=shotgun_api_key,
        )

    # Priority 2: Fall back to individual provider keys

    # Check if a specific model was requested
    if isinstance(provider_or_model, ModelName):
        # Look up the model spec
        if provider_or_model not in MODEL_SPECS:
            raise ValueError(f"Model '{provider_or_model.value}' not found")
        spec = MODEL_SPECS[provider_or_model]
        provider_enum = spec.provider
        requested_model = provider_or_model
    else:
        # Convert string to ProviderType enum if needed (backward compatible)
        if provider_or_model:
            provider_enum = (
                provider_or_model
                if isinstance(provider_or_model, ProviderType)
                else ProviderType(provider_or_model)
            )
        else:
            # No provider specified - find first available provider with a key
            provider_enum = None
            for provider in ProviderType:
                if _has_provider_key(config, provider):
                    provider_enum = provider
                    break

            if provider_enum is None:
                raise ValueError(
                    "No provider keys configured. Set via environment variables or config."
                )

        requested_model = None  # Will use provider's default model

    if provider_enum == ProviderType.OPENAI:
        api_key = _get_api_key(config.openai.api_key)
        if not api_key:
            raise ValueError("OpenAI API key not configured. Set via config.")

        # Use requested model or default to gpt-5
        model_name = requested_model if requested_model else ModelName.GPT_5
        if model_name not in MODEL_SPECS:
            raise ValueError(f"Model '{model_name.value}' not found")
        spec = MODEL_SPECS[model_name]

        # Create fully configured ModelConfig
        return ModelConfig(
            name=spec.name,
            provider=spec.provider,
            key_provider=KeyProvider.BYOK,
            max_input_tokens=spec.max_input_tokens,
            max_output_tokens=spec.max_output_tokens,
            api_key=api_key,
        )

    elif provider_enum == ProviderType.ANTHROPIC:
        api_key = _get_api_key(config.anthropic.api_key)
        if not api_key:
            raise ValueError("Anthropic API key not configured. Set via config.")

        # Use requested model or default to claude-haiku-4-5
        model_name = requested_model if requested_model else ModelName.CLAUDE_HAIKU_4_5
        if model_name not in MODEL_SPECS:
            raise ValueError(f"Model '{model_name.value}' not found")
        spec = MODEL_SPECS[model_name]

        # Create fully configured ModelConfig
        return ModelConfig(
            name=spec.name,
            provider=spec.provider,
            key_provider=KeyProvider.BYOK,
            max_input_tokens=spec.max_input_tokens,
            max_output_tokens=spec.max_output_tokens,
            api_key=api_key,
        )

    elif provider_enum == ProviderType.GOOGLE:
        api_key = _get_api_key(config.google.api_key)
        if not api_key:
            raise ValueError("Gemini API key not configured. Set via config.")

        # Use requested model or default to gemini-2.5-pro
        model_name = requested_model if requested_model else ModelName.GEMINI_2_5_PRO
        if model_name not in MODEL_SPECS:
            raise ValueError(f"Model '{model_name.value}' not found")
        spec = MODEL_SPECS[model_name]

        # Create fully configured ModelConfig
        return ModelConfig(
            name=spec.name,
            provider=spec.provider,
            key_provider=KeyProvider.BYOK,
            max_input_tokens=spec.max_input_tokens,
            max_output_tokens=spec.max_output_tokens,
            api_key=api_key,
        )

    else:
        raise ValueError(f"Unsupported provider: {provider_enum}")


def _has_provider_key(config: "ShotgunConfig", provider: ProviderType) -> bool:
    """Check if a provider has a configured API key.

    Args:
        config: Shotgun configuration
        provider: Provider to check

    Returns:
        True if provider has a configured API key
    """
    if provider == ProviderType.OPENAI:
        return bool(_get_api_key(config.openai.api_key))
    elif provider == ProviderType.ANTHROPIC:
        return bool(_get_api_key(config.anthropic.api_key))
    elif provider == ProviderType.GOOGLE:
        return bool(_get_api_key(config.google.api_key))
    return False


def _get_api_key(config_key: SecretStr | None) -> str | None:
    """Get API key from config.

    Args:
        config_key: API key from configuration

    Returns:
        API key string or None
    """
    if config_key is not None:
        return config_key.get_secret_value()

    return None
