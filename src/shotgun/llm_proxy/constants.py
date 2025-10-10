"""LiteLLM proxy constants and configuration."""

# Import from centralized API endpoints module
from shotgun.api_endpoints import (
    LITELLM_PROXY_ANTHROPIC_BASE,
    LITELLM_PROXY_BASE_URL,
    LITELLM_PROXY_OPENAI_BASE,
)

# Re-export for backward compatibility
__all__ = [
    "LITELLM_PROXY_BASE_URL",
    "LITELLM_PROXY_ANTHROPIC_BASE",
    "LITELLM_PROXY_OPENAI_BASE",
]
