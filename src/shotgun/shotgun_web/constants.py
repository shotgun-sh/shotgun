"""Constants for Shotgun Web API."""

import os

# Shotgun Web API base URL
# Default to production URL, can be overridden with environment variable
SHOTGUN_WEB_BASE_URL = os.environ.get(
    "SHOTGUN_WEB_BASE_URL", "https://api-701197220809.us-east1.run.app"
)

# API endpoints
UNIFICATION_TOKEN_CREATE_PATH = "/api/unification/token/create"  # noqa: S105
UNIFICATION_TOKEN_STATUS_PATH = "/api/unification/token/{token}/status"  # noqa: S105

# Polling configuration
DEFAULT_POLL_INTERVAL_SECONDS = 3
DEFAULT_TOKEN_TIMEOUT_SECONDS = 1800  # 30 minutes
