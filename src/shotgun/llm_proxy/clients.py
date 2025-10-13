"""Client creation utilities for LiteLLM proxy."""

from pydantic_ai.providers.anthropic import AnthropicProvider
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


def create_anthropic_proxy_provider(api_key: str) -> AnthropicProvider:
    """Create Anthropic provider configured for LiteLLM proxy.

    This provider uses native Anthropic API format while routing through
    the LiteLLM proxy. This preserves Anthropic-specific features like
    tool_choice and web search.

    The provider's .client attribute provides access to the async Anthropic
    client (AsyncAnthropic), which should be used for all API operations
    including token counting.

    Args:
        api_key: Shotgun API key

    Returns:
        AnthropicProvider configured to use LiteLLM proxy /anthropic endpoint
    """
    return AnthropicProvider(
        api_key=api_key,
        base_url=LITELLM_PROXY_ANTHROPIC_BASE,
    )
