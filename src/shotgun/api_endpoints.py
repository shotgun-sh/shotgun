"""Shotgun backend service API endpoints and URLs."""

from shotgun.settings import settings

# Shotgun Web API base URL (for authentication/subscription)
# Can be overridden with SHOTGUN_WEB_BASE_URL environment variable
SHOTGUN_WEB_BASE_URL = settings.api.web_base_url

# Shotgun's LiteLLM proxy base URL (for AI model requests)
# Can be overridden with SHOTGUN_ACCOUNT_LLM_BASE_URL environment variable
LITELLM_PROXY_BASE_URL = settings.api.account_llm_base_url

# Provider-specific LiteLLM proxy endpoints
LITELLM_PROXY_ANTHROPIC_BASE = f"{LITELLM_PROXY_BASE_URL}/anthropic"
LITELLM_PROXY_OPENAI_BASE = LITELLM_PROXY_BASE_URL
