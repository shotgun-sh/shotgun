"""Client creation utilities for LiteLLM proxy."""

from anthropic import Anthropic
from pydantic_ai.providers.litellm import LiteLLMProvider

from .constants import LITELLM_PROXY_ANTHROPIC_BASE, LITELLM_PROXY_BASE_URL


def create_litellm_provider(api_key: str) -> LiteLLMProvider:
    """Create LiteLLM provider for Shotgun Account.

    Args:
        api_key: Shotgun API key

    Returns:
        Configured LiteLLM provider pointing to Shotgun's proxy
    """
    return LiteLLMProvider(
        api_base=LITELLM_PROXY_BASE_URL,
        api_key=api_key,
    )


def create_anthropic_proxy_client(api_key: str) -> Anthropic:
    """Create Anthropic client configured for LiteLLM proxy.

    This client will proxy token counting requests through the
    LiteLLM proxy to Anthropic's actual token counting API.

    Args:
        api_key: Shotgun API key

    Returns:
        Anthropic client configured to use LiteLLM proxy
    """
    return Anthropic(
        api_key=api_key,
        base_url=LITELLM_PROXY_ANTHROPIC_BASE,
    )
