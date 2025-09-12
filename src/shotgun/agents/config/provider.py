"""Provider management for LLM configuration."""

import os

from pydantic import SecretStr

from shotgun.logging_config import setup_logger

from .manager import get_config_manager
from .models import ProviderType

logger = setup_logger(__name__)


def get_provider_model(provider: ProviderType | None = None) -> str:
    """Get configured Pydantic AI model string for the specified provider.

    Args:
        provider: Provider to get model for. If None, uses default provider

    Returns:
        Model string identifier (e.g., "openai:gpt-4o", "anthropic:claude-3-5-sonnet-latest")

    Raises:
        ValueError: If provider is not configured properly
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
        api_key = _get_api_key(config.openai.api_key, "OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OpenAI API key not configured. Set via environment variable OPENAI_API_KEY or config."
            )
        # Set the API key in environment if not already there
        if "OPENAI_API_KEY" not in os.environ:
            os.environ["OPENAI_API_KEY"] = api_key

        return "openai:gpt-5"

    elif provider_enum == ProviderType.ANTHROPIC:
        api_key = _get_api_key(config.anthropic.api_key, "ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "Anthropic API key not configured. Set via environment variable ANTHROPIC_API_KEY or config."
            )
        # Set the API key in environment if not already there
        if "ANTHROPIC_API_KEY" not in os.environ:
            os.environ["ANTHROPIC_API_KEY"] = api_key

        return "anthropic:claude-opus-4-1"

    elif provider_enum == ProviderType.GOOGLE:
        api_key = _get_api_key(config.google.api_key, "GOOGLE_API_KEY")
        if not api_key:
            raise ValueError(
                "Google API key not configured. Set via environment variable GOOGLE_API_KEY or config."
            )
        # Set the API key in environment if not already there
        if "GOOGLE_API_KEY" not in os.environ:
            os.environ["GOOGLE_API_KEY"] = api_key

        return "google-gla:gemini-2.5-pro"

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
