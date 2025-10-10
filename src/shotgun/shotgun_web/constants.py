"""Constants for Shotgun Web API."""

# Import from centralized API endpoints module
from shotgun.api_endpoints import SHOTGUN_WEB_BASE_URL

# API endpoints
UNIFICATION_TOKEN_CREATE_PATH = "/api/unification/token/create"  # noqa: S105
UNIFICATION_TOKEN_STATUS_PATH = "/api/unification/token/{token}/status"  # noqa: S105

# Polling configuration
DEFAULT_POLL_INTERVAL_SECONDS = 3
DEFAULT_TOKEN_TIMEOUT_SECONDS = 1800  # 30 minutes

# Re-export for backward compatibility
__all__ = [
    "SHOTGUN_WEB_BASE_URL",
    "UNIFICATION_TOKEN_CREATE_PATH",
    "UNIFICATION_TOKEN_STATUS_PATH",
    "DEFAULT_POLL_INTERVAL_SECONDS",
    "DEFAULT_TOKEN_TIMEOUT_SECONDS",
]
