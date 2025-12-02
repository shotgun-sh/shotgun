"""Pydantic models for Shotgun Web API."""

from datetime import datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field


class TokenStatus(StrEnum):
    """Token status enum matching API specification."""

    PENDING = "pending"
    COMPLETED = "completed"
    AWAITING_PAYMENT = "awaiting_payment"
    EXPIRED = "expired"


class TokenCreateRequest(BaseModel):
    """Request model for creating a unification token."""

    shotgun_instance_id: str = Field(
        description="CLI-provided UUID for shotgun instance"
    )


class TokenCreateResponse(BaseModel):
    """Response model for token creation."""

    token: str = Field(description="Secure authentication token")
    auth_url: str = Field(description="Web authentication URL for user to complete")
    expires_in_seconds: int = Field(description="Token expiration time in seconds")


class TokenStatusResponse(BaseModel):
    """Response model for token status check."""

    status: TokenStatus = Field(description="Current token status")
    supabase_key: str | None = Field(
        default=None,
        description="Supabase user JWT (only returned when status=completed)",
    )
    litellm_key: str | None = Field(
        default=None,
        description="LiteLLM virtual key (only returned when status=completed)",
    )
    message: str | None = Field(
        default=None, description="Human-readable status message"
    )


# ============================================================================
# Specs API Enums
# ============================================================================


class SpecVersionState(StrEnum):
    """Spec version lifecycle states."""

    UPLOADING = "uploading"
    READY = "ready"
    FAILED = "failed"


class WorkspaceRole(StrEnum):
    """User roles within a workspace."""

    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"


# ============================================================================
# Workspace Models
# ============================================================================


class WorkspaceResponse(BaseModel):
    """Workspace details."""

    id: str = Field(description="Workspace UUID")
    name: str = Field(description="Workspace name")


class MeWorkspaceResponse(BaseModel):
    """Workspace info from /api/me endpoint."""

    id: str = Field(description="Workspace UUID")
    name: str = Field(description="Workspace name")
    role: str = Field(description="User's role in workspace")


class MeResponse(BaseModel):
    """Response from /api/me endpoint."""

    id: str = Field(description="User UUID")
    email: str = Field(description="User email")
    first_name: str | None = Field(default=None, description="User's first name")
    last_name: str | None = Field(default=None, description="User's last name")
    workspace: MeWorkspaceResponse = Field(description="User's workspace info")
    has_completed_unification: bool = Field(
        description="Whether unification is complete"
    )
    last_unification_at: datetime | None = Field(
        default=None, description="Last unification timestamp"
    )


class WorkspaceListResponse(BaseModel):
    """Response for listing user's workspaces."""

    workspaces: list[WorkspaceResponse] = Field(
        description="List of workspaces the user has access to"
    )


# ============================================================================
# File Metadata (for file scanner)
# ============================================================================


class FileMetadata(BaseModel):
    """Metadata for a file discovered by the file scanner."""

    relative_path: str = Field(description="Path relative to .shotgun/ directory")
    absolute_path: Path = Field(description="Absolute path to the file")
    size_bytes: int = Field(description="File size in bytes")


# ============================================================================
# Specs API Request Models
# ============================================================================


class SpecCreateRequest(BaseModel):
    """Request to create a new spec."""

    name: str = Field(
        description="Human-readable spec name, unique per workspace",
        min_length=1,
        max_length=255,
    )
    description: str | None = Field(
        default=None,
        description="Optional description of the spec",
        max_length=2000,
    )


class SpecUpdateRequest(BaseModel):
    """Request to update spec metadata or visibility."""

    name: str | None = Field(
        default=None,
        description="Update spec name",
        min_length=1,
        max_length=255,
    )
    description: str | None = Field(
        default=None,
        description="Update description",
        max_length=2000,
    )
    is_public: bool | None = Field(
        default=None,
        description="Update visibility (public or team-only)",
    )


class SpecVersionCreateRequest(BaseModel):
    """Request to create a new version for an existing spec."""

    spec_id: str = Field(description="ID of the spec to create version for")
    label: str | None = Field(
        default=None,
        description="Optional version label (e.g., 'v1.0', 'initial')",
        max_length=100,
    )
    notes: str | None = Field(
        default=None,
        description="Optional version notes",
        max_length=2000,
    )


class FileUploadRequest(BaseModel):
    """Request to upload a file to a spec version."""

    spec_id: str = Field(description="Spec ID")
    version_id: str = Field(description="Version ID")
    relative_path: str = Field(
        description="Path relative to .shotgun/ directory",
        max_length=1000,
    )
    size_bytes: int = Field(description="File size in bytes", gt=0)
    content_hash: str = Field(
        description="SHA-256 hash of file content (hex encoded)",
        min_length=64,
        max_length=64,
    )


# ============================================================================
# Specs API Response Models
# ============================================================================


class SpecFileResponse(BaseModel):
    """Response model for a spec file."""

    id: str = Field(description="File record ID")
    relative_path: str = Field(description="Path relative to .shotgun/")
    bucket_key: str = Field(description="Full key in object storage")
    size_bytes: int = Field(description="File size in bytes")
    content_hash: str = Field(description="SHA-256 hash (hex)")
    content_type: str | None = Field(
        default=None,
        description="MIME type (e.g., text/markdown, application/json)",
    )
    created_on: datetime | None = Field(
        default=None, description="Upload timestamp (None until upload completes)"
    )
    download_url: str | None = Field(
        default=None,
        description="Pre-signed download URL (temporary)",
    )


class SpecVersionResponse(BaseModel):
    """Response model for a spec version."""

    id: str = Field(description="Version ID")
    spec_id: str = Field(description="Parent spec ID")
    workspace_id: str | None = Field(default=None, description="Workspace ID")
    state: SpecVersionState = Field(description="Version state")
    is_latest: bool = Field(description="Whether this is the latest version")
    label: str | None = Field(default=None, description="Version label")
    notes: str | None = Field(default=None, description="Version notes")
    created_by: str = Field(description="User ID who created this version")
    created_by_email: str | None = Field(
        default=None,
        description="Email of user who created version (hidden for anonymous viewers)",
    )
    created_on: datetime | None = Field(default=None, description="Creation timestamp")
    file_count: int | None = Field(
        default=None,
        description="Number of files in this version",
    )
    total_size_bytes: int | None = Field(
        default=None,
        description="Total size of all files",
    )
    web_url: str | None = Field(
        default=None,
        description="URL to view this version in the web UI",
    )


class SpecResponse(BaseModel):
    """Response model for a spec."""

    id: str = Field(description="Spec ID")
    workspace_id: str = Field(description="Workspace ID")
    name: str = Field(description="Spec name")
    description: str | None = Field(default=None, description="Spec description")
    is_public: bool = Field(
        default=False,
        description="Whether spec is publicly accessible",
    )
    created_by: str = Field(description="User ID who created the spec")
    created_by_email: str | None = Field(
        default=None,
        description="Email of original creator (hidden for anonymous viewers)",
    )
    created_on: datetime | None = Field(default=None, description="Creation timestamp")
    updated_on: datetime | None = Field(
        default=None, description="Last update timestamp"
    )
    updated_by_email: str | None = Field(
        default=None,
        description="Email of user who last updated (hidden for anonymous viewers)",
    )
    latest_version: SpecVersionResponse | None = Field(
        default=None,
        description="Latest version details (if exists)",
    )
    version_count: int = Field(description="Total number of versions")


class PublicSpecResponse(BaseModel):
    """Response model for public spec access (redacted for anonymous users)."""

    id: str = Field(description="Spec ID")
    name: str = Field(description="Spec name")
    description: str | None = Field(default=None, description="Spec description")
    created_on: datetime = Field(description="Creation timestamp")
    updated_on: datetime = Field(description="Last update timestamp")
    latest_version: SpecVersionResponse | None = Field(
        default=None,
        description="Latest version details (without sensitive user info)",
    )


class SpecListResponse(BaseModel):
    """Response model for listing specs in a workspace."""

    specs: list[SpecResponse] = Field(description="List of specs")
    total: int = Field(description="Total number of specs")
    page: int = Field(default=1, description="Current page number")
    page_size: int = Field(default=50, description="Items per page")


class VersionListResponse(BaseModel):
    """Response model for listing versions of a spec."""

    versions: list[SpecVersionResponse] = Field(description="List of versions")
    spec_id: str = Field(description="Spec ID these versions belong to")
    total: int = Field(description="Total number of versions")
    page: int = Field(default=1, description="Current page number")
    page_size: int = Field(default=50, description="Items per page")


class FileListResponse(BaseModel):
    """Response model for listing files in a version."""

    files: list[SpecFileResponse] = Field(description="List of files")
    version_id: str = Field(description="Version ID these files belong to")
    total: int = Field(description="Total number of files")


class SpecCreateResponse(BaseModel):
    """Response after creating a spec with initial version."""

    spec: SpecResponse = Field(description="Created spec details")
    version: SpecVersionResponse = Field(
        description="Initial version in uploading state"
    )
    upload_url: str | None = Field(
        default=None, description="Base URL for file uploads"
    )


class VersionCreateResponse(BaseModel):
    """Response after creating a new version."""

    version: SpecVersionResponse = Field(
        description="Created version in uploading state"
    )
    upload_url: str | None = Field(
        default=None, description="Base URL for file uploads"
    )


class FileUploadResponse(BaseModel):
    """Response after uploading a file."""

    file: SpecFileResponse = Field(description="Uploaded file details")
    upload_url: str = Field(description="Pre-signed URL to upload file content to")


class VersionCloseResponse(BaseModel):
    """Response after closing a version."""

    version: SpecVersionResponse = Field(description="Closed version details")
    web_url: str = Field(description="Web URL to view this version")


class VersionWithFilesResponse(BaseModel):
    """Response for GET /api/versions/{version_id} endpoint.

    This is a convenience endpoint for CLI that returns version info
    plus all files without requiring workspace_id/spec_id in the path.
    """

    version: SpecVersionResponse = Field(description="Version details")
    spec_name: str = Field(description="Name of the parent spec")
    spec_id: str = Field(description="Parent spec ID")
    workspace_id: str = Field(description="Workspace ID")
    files: list[SpecFileResponse] = Field(description="Files in this version")
    download_urls_expire_at: datetime | None = Field(
        default=None,
        description="When presigned download URLs expire (UTC)",
    )
    web_url: str | None = Field(
        default=None,
        description="URL to view this version in the web UI",
    )


class PermissionCheckResponse(BaseModel):
    """Response for permission check."""

    workspace_id: str = Field(description="Workspace ID")
    user_role: WorkspaceRole = Field(description="User's role in workspace")
    can_create_specs: bool = Field(description="Whether user can create specs")
    can_upload_versions: bool = Field(description="Whether user can upload versions")
    can_set_latest: bool = Field(description="Whether user can set latest version")
    can_change_visibility: bool = Field(
        description="Whether user can change spec visibility (public/team)"
    )


# ============================================================================
# Specs API Error Response Models
# ============================================================================


class ErrorDetail(BaseModel):
    """Detailed error information."""

    field: str | None = Field(default=None, description="Field that caused error")
    message: str = Field(description="Error message")
    code: str | None = Field(default=None, description="Machine-readable error code")


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str = Field(description="Error type or category")
    message: str = Field(description="Human-readable error message")
    details: list[ErrorDetail] | None = Field(
        default=None,
        description="Detailed error information",
    )
    request_id: str | None = Field(
        default=None,
        description="Request ID for debugging",
    )


# ============================================================================
# Custom Exceptions
# ============================================================================


class WorkspaceNotFoundError(Exception):
    """Raised when user has no workspaces."""
