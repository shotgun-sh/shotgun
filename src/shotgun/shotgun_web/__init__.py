"""Shotgun Web API client for subscription, authentication, and shared specs."""

from .client import ShotgunWebClient, check_token_status, create_unification_token
from .exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    PayloadTooLargeError,
    RateLimitExceededError,
    ShotgunWebError,
    UnauthorizedError,
)
from .models import (
    # Specs models
    ErrorDetail,
    ErrorResponse,
    FileListResponse,
    FileMetadata,
    FileUploadRequest,
    FileUploadResponse,
    PermissionCheckResponse,
    PublicSpecResponse,
    SpecCreateRequest,
    SpecCreateResponse,
    SpecFileResponse,
    SpecListResponse,
    SpecResponse,
    SpecUpdateRequest,
    SpecVersionCreateRequest,
    SpecVersionResponse,
    SpecVersionState,
    # Token models
    TokenCreateRequest,
    TokenCreateResponse,
    TokenStatus,
    TokenStatusResponse,
    VersionCloseResponse,
    VersionCreateResponse,
    VersionListResponse,
    WorkspaceRole,
)
from .specs_client import SpecsClient

__all__ = [
    # Existing exports
    "ShotgunWebClient",
    "create_unification_token",
    "check_token_status",
    "TokenCreateRequest",
    "TokenCreateResponse",
    "TokenStatus",
    "TokenStatusResponse",
    # Specs client
    "SpecsClient",
    # Exceptions
    "ShotgunWebError",
    "UnauthorizedError",
    "ForbiddenError",
    "NotFoundError",
    "ConflictError",
    "PayloadTooLargeError",
    "RateLimitExceededError",
    # Specs models
    "ErrorDetail",
    "ErrorResponse",
    "FileListResponse",
    "FileMetadata",
    "FileUploadRequest",
    "FileUploadResponse",
    "PermissionCheckResponse",
    "PublicSpecResponse",
    "SpecCreateRequest",
    "SpecCreateResponse",
    "SpecFileResponse",
    "SpecListResponse",
    "SpecResponse",
    "SpecUpdateRequest",
    "SpecVersionCreateRequest",
    "SpecVersionResponse",
    "SpecVersionState",
    "VersionCloseResponse",
    "VersionCreateResponse",
    "VersionListResponse",
    "WorkspaceRole",
]
