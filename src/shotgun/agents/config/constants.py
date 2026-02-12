"""Configuration constants for Shotgun agents."""

from enum import StrEnum, auto

# Field names
API_KEY_FIELD = "api_key"
SUPABASE_JWT_FIELD = "supabase_jwt"
SHOTGUN_INSTANCE_ID_FIELD = "shotgun_instance_id"
CONFIG_VERSION_FIELD = "config_version"


class ConfigSection(StrEnum):
    """Configuration file section names (JSON keys)."""

    OPENAI = auto()
    ANTHROPIC = auto()
    GOOGLE = auto()
    SHOTGUN = auto()
    CONTEXT7 = auto()


# Backwards compatibility - deprecated
OPENAI_PROVIDER = ConfigSection.OPENAI.value
ANTHROPIC_PROVIDER = ConfigSection.ANTHROPIC.value
GOOGLE_PROVIDER = ConfigSection.GOOGLE.value
SHOTGUN_PROVIDER = ConfigSection.SHOTGUN.value

# Token limits
MEDIUM_TEXT_8K_TOKENS = 8192  # Default max_tokens for web search requests
SUB_AGENT_MAX_OUTPUT_TOKENS = (
    2000  # Max output tokens for sub-agents delegated by Router
)

# Web search behavior thresholds
# These control when warnings are shown to agents about excessive web searching
WEB_SEARCH_WARNING_THRESHOLD = 3  # Show caution message at this count
WEB_SEARCH_STOP_THRESHOLD = 5  # Show stop message at this count
