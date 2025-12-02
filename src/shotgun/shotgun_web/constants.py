"""Constants for Shotgun Web API."""

# Import from centralized API endpoints module
from shotgun.api_endpoints import SHOTGUN_WEB_BASE_URL

# API endpoints
UNIFICATION_TOKEN_CREATE_PATH = "/api/unification/token/create"  # noqa: S105
UNIFICATION_TOKEN_STATUS_PATH = "/api/unification/token/{token}/status"  # noqa: S105
ME_PATH = "/api/me"

# Polling configuration
DEFAULT_POLL_INTERVAL_SECONDS = 3
DEFAULT_TOKEN_TIMEOUT_SECONDS = 1800  # 30 minutes

# Workspaces API endpoint
WORKSPACES_PATH = "/api/workspaces"

# Specs API endpoints
PERMISSIONS_PATH = "/api/workspaces/{workspace_id}/specs/permissions"
SPECS_BASE_PATH = "/api/workspaces/{workspace_id}/specs"
SPECS_DETAIL_PATH = "/api/workspaces/{workspace_id}/specs/{spec_id}"
VERSIONS_PATH = "/api/workspaces/{workspace_id}/specs/{spec_id}/versions"
VERSION_DETAIL_PATH = (
    "/api/workspaces/{workspace_id}/specs/{spec_id}/versions/{version_id}"
)
VERSION_CLOSE_PATH = (
    "/api/workspaces/{workspace_id}/specs/{spec_id}/versions/{version_id}/close"
)
VERSION_SET_LATEST_PATH = (
    "/api/workspaces/{workspace_id}/specs/{spec_id}/versions/{version_id}/set-latest"
)
FILES_PATH = (
    "/api/workspaces/{workspace_id}/specs/{spec_id}/versions/{version_id}/files"
)
FILE_DETAIL_PATH = "/api/workspaces/{workspace_id}/specs/{spec_id}/versions/{version_id}/files/{file_id}"
PUBLIC_SPEC_PATH = "/api/public/specs/{spec_id}"
PUBLIC_SPEC_FILES_PATH = "/api/public/specs/{spec_id}/files"
PUBLIC_FILE_PATH = "/api/public/specs/{spec_id}/files/{file_id}"

# CLI convenience endpoint (version lookup by ID only)
VERSION_BY_ID_PATH = "/api/versions/{version_id}"

# Re-export for backward compatibility
__all__ = [
    "SHOTGUN_WEB_BASE_URL",
    "UNIFICATION_TOKEN_CREATE_PATH",
    "UNIFICATION_TOKEN_STATUS_PATH",
    "ME_PATH",
    "DEFAULT_POLL_INTERVAL_SECONDS",
    "DEFAULT_TOKEN_TIMEOUT_SECONDS",
    # Workspaces endpoint
    "WORKSPACES_PATH",
    # Specs endpoints
    "PERMISSIONS_PATH",
    "SPECS_BASE_PATH",
    "SPECS_DETAIL_PATH",
    "VERSIONS_PATH",
    "VERSION_DETAIL_PATH",
    "VERSION_CLOSE_PATH",
    "VERSION_SET_LATEST_PATH",
    "FILES_PATH",
    "FILE_DETAIL_PATH",
    "PUBLIC_SPEC_PATH",
    "PUBLIC_SPEC_FILES_PATH",
    "PUBLIC_FILE_PATH",
    "VERSION_BY_ID_PATH",
]
