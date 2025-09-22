"""Configuration constants for Shotgun agents."""

# Field names
API_KEY_FIELD = "api_key"
MODEL_NAME_FIELD = "model_name"
DEFAULT_PROVIDER_FIELD = "default_provider"
USER_ID_FIELD = "user_id"
CONFIG_VERSION_FIELD = "config_version"

# Provider names (for consistency with data dict keys)
OPENAI_PROVIDER = "openai"
ANTHROPIC_PROVIDER = "anthropic"
GOOGLE_PROVIDER = "google"

# Environment variable names
OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
ANTHROPIC_API_KEY_ENV = "ANTHROPIC_API_KEY"
GEMINI_API_KEY_ENV = "GEMINI_API_KEY"
