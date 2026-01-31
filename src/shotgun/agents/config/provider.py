"""Provider management for LLM configuration."""

from pydantic import SecretStr
from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel, AnthropicModelSettings
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIResponsesModel
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
    get_sub_agent_model,
)
from .streaming_test import check_streaming_capability

logger = get_logger(__name__)

# Global cache for Model instances (singleton pattern)
_model_cache: dict[tuple[ProviderType, KeyProvider, ModelName | str, str], Model] = {}

# Module-level model override for OpenAI-compatible mode (set via --model CLI flag)
_openai_compat_model_override: str | None = None
_openai_compat_sub_agent_model_override: str | None = None

# Default model for OpenAI-compatible endpoints
OPENAI_COMPAT_DEFAULT_MODEL = "gpt-5.2"


def set_openai_compat_model(model: str | None) -> None:
    """Set the model override for OpenAI-compatible endpoints.

    This is called by the CLI when --model is specified.

    Args:
        model: Model name to use, or None to use the default.
    """
    global _openai_compat_model_override
    _openai_compat_model_override = model


def set_openai_compat_sub_agent_model(model: str | None) -> None:
    """Set the sub-agent model override for OpenAI-compatible endpoints.

    This is called by the CLI when --sub-agent-model is specified.

    Args:
        model: Model name to use for sub-agents, or None to use the main model.
    """
    global _openai_compat_sub_agent_model_override
    _openai_compat_sub_agent_model_override = model


def _create_openai_compat_model(
    api_key: str, model_name: str, max_tokens: int
) -> Model:
    """Create a model for OpenAI-compatible endpoints.

    Uses the SHOTGUN_OPENAI_COMPAT_BASE_URL from settings to configure
    the LiteLLM provider with a custom base URL.

    Args:
        api_key: API key for the endpoint
        model_name: Name of the model to use
        max_tokens: Maximum output tokens

    Returns:
        Configured OpenAI-compatible Model instance
    """
    from shotgun.settings import settings

    base_url = settings.openai_compat.base_url
    if not base_url:
        raise ValueError(
            "SHOTGUN_OPENAI_COMPAT_BASE_URL is required for OpenAI-compatible mode"
        )

    # Use OpenAI provider with custom base_url
    openai_provider = OpenAIProvider(api_key=api_key, base_url=base_url)

    # Use OpenAIChatModel for broad compatibility with OpenAI-compatible APIs
    return OpenAIChatModel(
        model_name,
        provider=openai_provider,
        settings=ModelSettings(max_tokens=max_tokens),
    )


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
        return ModelName.CLAUDE_SONNET_4_5

    # Priority 2: Individual provider keys
    if _get_api_key(config.anthropic.api_key):
        return ModelName.CLAUDE_SONNET_4_5
    if _get_api_key(config.openai.api_key):
        return ModelName.GPT_5_2
    if _get_api_key(config.google.api_key):
        return ModelName.GEMINI_3_PRO_PREVIEW

    # Fallback: system-wide default
    return ModelName.CLAUDE_SONNET_4_5


def get_or_create_model(
    provider: ProviderType,
    key_provider: "KeyProvider",
    model_name: ModelName | str,
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

        # Get max_tokens from MODEL_SPECS (only for known models)
        if isinstance(model_name, ModelName) and model_name in MODEL_SPECS:
            max_tokens = MODEL_SPECS[model_name].max_output_tokens
        else:
            # Fallback defaults based on provider
            max_tokens = {
                ProviderType.OPENAI: 16_000,
                ProviderType.ANTHROPIC: 32_000,
                ProviderType.GOOGLE: 64_000,
                ProviderType.OPENAI_COMPATIBLE: 16_000,
            }.get(provider, 16_000)

        # Handle OpenAI-compatible endpoints (uses settings for base_url)
        if provider == ProviderType.OPENAI_COMPATIBLE:
            _model_cache[cache_key] = _create_openai_compat_model(
                api_key, str(model_name), max_tokens
            )
            return _model_cache[cache_key]

        # Use LiteLLM proxy for Shotgun Account, native providers for BYOK
        # At this point, model_name must be a ModelName (string handled above via OPENAI_COMPATIBLE)
        if not isinstance(model_name, ModelName):
            raise ValueError(
                f"Unknown model name: {model_name}. "
                "For custom models, set SHOTGUN_OPENAI_COMPAT_BASE_URL."
            )

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
                # Note: Use OpenAIChatModel (not OpenAIResponsesModel) because LiteLLM's
                # streaming Responses API doesn't return tool calls properly for Gemini 3
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
                _model_cache[cache_key] = OpenAIResponsesModel(
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
    for_sub_agent: bool = False,
) -> ModelConfig:
    """Get a fully configured ModelConfig with API key and Model instance.

    Args:
        provider_or_model: Either a ProviderType, ModelName, or None.
            - If ModelName: returns that specific model with appropriate API key
            - If ProviderType: returns default model for that provider (backward compatible)
            - If None: uses default provider with its default model
        for_sub_agent: If True, substitute cheaper model for cost optimization.

    Returns:
        ModelConfig with API key configured and lazy Model instance

    Raises:
        ValueError: If provider is not configured properly or model not found

    Note:
        When SHOTGUN_OPENAI_COMPAT_BASE_URL is set, this function bypasses all
        other provider configuration and uses the OpenAI-compatible endpoint.
        The model name comes from SHOTGUN_OPENAI_COMPAT_DEFAULT_MODEL (default: gpt-4).
    """
    from shotgun.settings import settings

    # PRIORITY 0: Check for OpenAI-compatible mode
    # When both SHOTGUN_OPENAI_COMPAT_BASE_URL and API_KEY are set, bypass all other providers
    if settings.openai_compat.base_url and settings.openai_compat.api_key:
        compat_api_key = settings.openai_compat.api_key

        # Use CLI override if set, otherwise use hardcoded default
        main_model = _openai_compat_model_override or OPENAI_COMPAT_DEFAULT_MODEL

        # For sub-agents, use sub-agent model if specified, otherwise fall back to main model
        if for_sub_agent and _openai_compat_sub_agent_model_override:
            model_name = _openai_compat_sub_agent_model_override
            logger.info(
                "Using OpenAI-compatible endpoint: %s with sub-agent model: %s",
                settings.openai_compat.base_url,
                model_name,
            )
        else:
            model_name = main_model
            logger.info(
                "Using OpenAI-compatible endpoint: %s with model: %s",
                settings.openai_compat.base_url,
                model_name,
            )

        return ModelConfig(
            name=model_name,
            provider=ProviderType.OPENAI_COMPATIBLE,
            key_provider=KeyProvider.BYOK,
            max_input_tokens=128_000,  # Reasonable default for OpenAI-compatible
            max_output_tokens=16_000,
            api_key=compat_api_key,
            supports_streaming=True,
        )

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
        elif isinstance(provider_or_model, ProviderType):
            # Specific provider requested - use default model for that provider
            # This is important for web search tools that need specific provider APIs
            provider_defaults = {
                ProviderType.OPENAI: ModelName.GPT_5_2,
                ProviderType.ANTHROPIC: ModelName.CLAUDE_SONNET_4_5,
                ProviderType.GOOGLE: ModelName.GEMINI_3_FLASH_PREVIEW,
            }
            model_name = provider_defaults.get(
                provider_or_model,
                config.selected_model or get_default_model_for_provider(config),
            )
        else:
            # No specific model requested - use selected or default
            model_name = config.selected_model or get_default_model_for_provider(config)

        # Gracefully fall back if the selected model doesn't exist (backwards compatibility)
        if model_name not in MODEL_SPECS:
            model_name = get_default_model_for_provider(config)

        # Apply sub-agent model mapping for cost optimization
        if for_sub_agent:
            original_model = model_name
            model_name = get_sub_agent_model(model_name)
            if model_name != original_model:
                logger.debug(
                    "Sub-agent model substitution: %s -> %s",
                    original_model.value,
                    model_name.value,
                )

        spec = MODEL_SPECS[model_name]

        # Use Shotgun Account with determined model (provider = actual LLM provider)
        # Shotgun accounts always support streaming (via LiteLLM proxy)
        return ModelConfig(
            name=spec.name,
            provider=spec.provider,  # Actual LLM provider (OPENAI/ANTHROPIC/GOOGLE)
            key_provider=KeyProvider.SHOTGUN,  # Authenticated via Shotgun Account
            max_input_tokens=spec.max_input_tokens,
            max_output_tokens=spec.max_output_tokens,
            api_key=shotgun_api_key,
            supports_streaming=True,  # Shotgun accounts always support streaming
        )

    # Priority 2: Fall back to individual provider keys

    # Check if a specific model was requested
    if isinstance(provider_or_model, ModelName):
        # Look up the model spec
        if provider_or_model not in MODEL_SPECS:
            requested_model = None  # Fall back to provider default
            provider_enum = None  # Will be determined below
        else:
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
            requested_model = None  # Will use provider's default model
        else:
            # No provider specified - check if user has a selected model
            if config.selected_model and config.selected_model in MODEL_SPECS:
                selected_spec = MODEL_SPECS[config.selected_model]
                # Only use selected model if its provider has a configured key
                if _has_provider_key(config, selected_spec.provider):
                    provider_enum = selected_spec.provider
                    requested_model = config.selected_model
                else:
                    # Selected model's provider has no key - fall back to finding available provider
                    provider_enum = None
                    requested_model = None
            else:
                provider_enum = None
                requested_model = None

            # If no selected model or its provider unavailable, find first available provider
            if provider_enum is None:
                for provider in ProviderType:
                    if _has_provider_key(config, provider):
                        provider_enum = provider
                        break

            if provider_enum is None:
                raise ValueError(
                    "No provider keys configured. Set via environment variables or config."
                )

    if provider_enum == ProviderType.OPENAI:
        api_key = _get_api_key(config.openai.api_key, "OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OpenAI API key not configured. Set via config or OPENAI_API_KEY env var."
            )

        # Use requested model or default to gpt-5.2
        model_name = requested_model if requested_model else ModelName.GPT_5_2
        # Gracefully fall back if model doesn't exist
        if model_name not in MODEL_SPECS:
            model_name = ModelName.GPT_5_2

        # Apply sub-agent model mapping for cost optimization
        if for_sub_agent:
            original_model = model_name
            model_name = get_sub_agent_model(model_name)
            if model_name != original_model:
                logger.debug(
                    "Sub-agent model substitution: %s -> %s",
                    original_model.value,
                    model_name.value,
                )

        spec = MODEL_SPECS[model_name]

        # Check and test streaming capability for GPT-5 family models
        supports_streaming = True  # Default to True for all models
        if model_name in (
            ModelName.GPT_5_1,
            ModelName.GPT_5_2,
        ):
            # Check if streaming capability has been tested
            streaming_capability = config.openai.supports_streaming

            if streaming_capability is None:
                # Not tested yet - run streaming test (test once for all GPT-5 models)
                logger.info("Testing streaming capability for OpenAI GPT-5 family...")
                streaming_capability = await check_streaming_capability(
                    api_key, model_name.value
                )

                # Save result to config (applies to all OpenAI models)
                config.openai.supports_streaming = streaming_capability
                await config_manager.save(config)
                logger.info(
                    f"Streaming test result: "
                    f"{'enabled' if streaming_capability else 'disabled'}"
                )

            supports_streaming = streaming_capability

        # Create fully configured ModelConfig
        return ModelConfig(
            name=spec.name,
            provider=spec.provider,
            key_provider=KeyProvider.BYOK,
            max_input_tokens=spec.max_input_tokens,
            max_output_tokens=spec.max_output_tokens,
            api_key=api_key,
            supports_streaming=supports_streaming,
        )

    elif provider_enum == ProviderType.ANTHROPIC:
        api_key = _get_api_key(config.anthropic.api_key, "ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "Anthropic API key not configured. Set via config or ANTHROPIC_API_KEY env var."
            )

        # Use requested model or default to claude-sonnet-4-5
        model_name = requested_model if requested_model else ModelName.CLAUDE_SONNET_4_5
        # Gracefully fall back if model doesn't exist
        if model_name not in MODEL_SPECS:
            model_name = ModelName.CLAUDE_SONNET_4_5

        # Apply sub-agent model mapping for cost optimization
        if for_sub_agent:
            original_model = model_name
            model_name = get_sub_agent_model(model_name)
            if model_name != original_model:
                logger.debug(
                    "Sub-agent model substitution: %s -> %s",
                    original_model.value,
                    model_name.value,
                )

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
        api_key = _get_api_key(config.google.api_key, "GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "Gemini API key not configured. Set via config or GEMINI_API_KEY env var."
            )

        # Use requested model or default to gemini-3-pro-preview
        model_name = (
            requested_model if requested_model else ModelName.GEMINI_3_PRO_PREVIEW
        )
        # Gracefully fall back if model doesn't exist
        if model_name not in MODEL_SPECS:
            model_name = ModelName.GEMINI_3_PRO_PREVIEW

        # Apply sub-agent model mapping for cost optimization
        if for_sub_agent:
            original_model = model_name
            model_name = get_sub_agent_model(model_name)
            if model_name != original_model:
                logger.debug(
                    "Sub-agent model substitution: %s -> %s",
                    original_model.value,
                    model_name.value,
                )

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


def _get_api_key(
    config_key: SecretStr | None, env_var_name: str | None = None
) -> str | None:
    """Get API key from config or environment variable.

    Args:
        config_key: API key from configuration
        env_var_name: Optional environment variable name to check as fallback

    Returns:
        API key string or None
    """
    # First check config
    if config_key is not None:
        return config_key.get_secret_value()

    # Fallback to environment variable
    if env_var_name:
        import os

        return os.environ.get(env_var_name)

    return None
