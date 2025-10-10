"""Shotgun backend service API endpoints and URLs."""

# Shotgun Web API base URL (for authentication/subscription)
# Can be overridden with environment variable
SHOTGUN_WEB_BASE_URL = "https://api-219702594231.us-east4.run.app"
# Shotgun's LiteLLM proxy base URL (for AI model requests)
LITELLM_PROXY_BASE_URL = "https://litellm-219702594231.us-east4.run.app"

# Provider-specific LiteLLM proxy endpoints
LITELLM_PROXY_ANTHROPIC_BASE = f"{LITELLM_PROXY_BASE_URL}/anthropic"
LITELLM_PROXY_OPENAI_BASE = LITELLM_PROXY_BASE_URL
