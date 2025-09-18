"""Utility functions for web search tools."""

from shotgun.agents.config import get_provider_model
from shotgun.agents.config.models import ProviderType


def is_provider_available(provider: ProviderType) -> bool:
    """Check if a provider has API key configured.

    Args:
        provider: The provider to check

    Returns:
        True if the provider has valid credentials configured (from config or env)
    """
    try:
        get_provider_model(provider)
        return True
    except ValueError:
        return False
