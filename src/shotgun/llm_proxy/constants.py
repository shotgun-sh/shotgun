"""LiteLLM proxy constants and configuration."""

# Shotgun's LiteLLM proxy base URL
LITELLM_PROXY_BASE_URL = "https://litellm-701197220809.us-east1.run.app"

# Provider-specific endpoints
LITELLM_PROXY_ANTHROPIC_BASE = f"{LITELLM_PROXY_BASE_URL}/anthropic"
LITELLM_PROXY_OPENAI_BASE = LITELLM_PROXY_BASE_URL
