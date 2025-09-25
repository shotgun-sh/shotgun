"""Provider management for LLM configuration."""

import os

from pydantic import SecretStr
from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel, AnthropicModelSettings
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

from shotgun.logging_config import get_logger

from .constants import (
    ANTHROPIC_API_KEY_ENV,
    GEMINI_API_KEY_ENV,
    OPENAI_API_KEY_ENV,
)
from .manager import get_config_manager
from .models import MODEL_SPECS, ModelConfig, ProviderType

logger = get_logger(__name__)

# Global cache for Model instances (singleton pattern)
_model_cache: dict[tuple[ProviderType, str, str], Model] = {}


def get_or_create_model(provider: ProviderType, model_name: str, api_key: str) -> Model:
    """Get or create a singleton Model instance.

    Args:
        provider: Provider type
        model_name: Name of the model
        api_key: API key for the provider

    Returns:
        Cached or newly created Model instance

    Raises:
        ValueError: If provider is not supported
    """
    cache_key = (provider, model_name, api_key)

    if cache_key not in _model_cache:
        logger.debug("Creating new %s model instance: %s", provider.value, model_name)

        if provider == ProviderType.OPENAI:
            # Get max_tokens from MODEL_SPECS to use full capacity
            if model_name in MODEL_SPECS:
                max_tokens = MODEL_SPECS[model_name].max_output_tokens
            else:
                max_tokens = 16_000  # Default for GPT models

            openai_provider = OpenAIProvider(api_key=api_key)
            _model_cache[cache_key] = OpenAIChatModel(
                model_name,
                provider=openai_provider,
                settings=ModelSettings(max_tokens=max_tokens),
            )
        elif provider == ProviderType.ANTHROPIC:
            # Get max_tokens from MODEL_SPECS to use full capacity
            if model_name in MODEL_SPECS:
                max_tokens = MODEL_SPECS[model_name].max_output_tokens
            else:
                max_tokens = 32_000  # Default for Claude models

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
            # Get max_tokens from MODEL_SPECS to use full capacity
            if model_name in MODEL_SPECS:
                max_tokens = MODEL_SPECS[model_name].max_output_tokens
            else:
                max_tokens = 64_000  # Default for Gemini models

            google_provider = GoogleProvider(api_key=api_key)
            _model_cache[cache_key] = GoogleModel(
                model_name,
                provider=google_provider,
                settings=ModelSettings(max_tokens=max_tokens),
            )
        else:
            raise ValueError(f"Unsupported provider: {provider}")
    else:
        logger.debug("Reusing cached %s model instance: %s", provider.value, model_name)

    return _model_cache[cache_key]


def get_provider_model(provider: ProviderType | None = None) -> ModelConfig:
    """Get a fully configured ModelConfig with API key and Model instance.

    Args:
        provider: Provider to get model for. If None, uses default provider

    Returns:
        ModelConfig with API key configured and lazy Model instance

    Raises:
        ValueError: If provider is not configured properly or model not found
    """
    config_manager = get_config_manager()
    config = config_manager.load()
    # Convert string to ProviderType enum if needed
    provider_enum = (
        provider
        if isinstance(provider, ProviderType)
        else ProviderType(provider)
        if provider
        else config.default_provider
    )

    if provider_enum == ProviderType.OPENAI:
        api_key = _get_api_key(config.openai.api_key, OPENAI_API_KEY_ENV)
        if not api_key:
            raise ValueError(
                f"OpenAI API key not configured. Set via environment variable {OPENAI_API_KEY_ENV} or config."
            )

        # Get model spec
        model_name = config.openai.model_name
        if model_name not in MODEL_SPECS:
            raise ValueError(f"Model '{model_name}' not found")
        spec = MODEL_SPECS[model_name]

        # Create fully configured ModelConfig
        return ModelConfig(
            name=spec.name,
            provider=spec.provider,
            max_input_tokens=spec.max_input_tokens,
            max_output_tokens=spec.max_output_tokens,
            api_key=api_key,
        )

    elif provider_enum == ProviderType.ANTHROPIC:
        api_key = _get_api_key(config.anthropic.api_key, ANTHROPIC_API_KEY_ENV)
        if not api_key:
            raise ValueError(
                f"Anthropic API key not configured. Set via environment variable {ANTHROPIC_API_KEY_ENV} or config."
            )

        # Get model spec
        model_name = config.anthropic.model_name
        if model_name not in MODEL_SPECS:
            raise ValueError(f"Model '{model_name}' not found")
        spec = MODEL_SPECS[model_name]

        # Create fully configured ModelConfig
        return ModelConfig(
            name=spec.name,
            provider=spec.provider,
            max_input_tokens=spec.max_input_tokens,
            max_output_tokens=spec.max_output_tokens,
            api_key=api_key,
        )

    elif provider_enum == ProviderType.GOOGLE:
        api_key = _get_api_key(config.google.api_key, GEMINI_API_KEY_ENV)
        if not api_key:
            raise ValueError(
                f"Gemini API key not configured. Set via environment variable {GEMINI_API_KEY_ENV} or config."
            )

        # Get model spec
        model_name = config.google.model_name
        if model_name not in MODEL_SPECS:
            raise ValueError(f"Model '{model_name}' not found")
        spec = MODEL_SPECS[model_name]

        # Create fully configured ModelConfig
        return ModelConfig(
            name=spec.name,
            provider=spec.provider,
            max_input_tokens=spec.max_input_tokens,
            max_output_tokens=spec.max_output_tokens,
            api_key=api_key,
        )

    else:
        raise ValueError(f"Unsupported provider: {provider_enum}")


def _get_api_key(config_key: SecretStr | None, env_var: str) -> str | None:
    """Get API key from config or environment variable.

    Args:
        config_key: API key from configuration
        env_var: Environment variable name to check

    Returns:
        API key string or None
    """
    if config_key is not None:
        return config_key.get_secret_value()

    return os.getenv(env_var)
