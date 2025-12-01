"""Async HTTP client for Shotgun Specs API."""

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Literal

import aiofiles
import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from shotgun.agents.config import get_config_manager
from shotgun.logging_config import get_logger

from .constants import (
    FILES_PATH,
    PERMISSIONS_PATH,
    PUBLIC_FILE_PATH,
    PUBLIC_SPEC_FILES_PATH,
    PUBLIC_SPEC_PATH,
    SHOTGUN_WEB_BASE_URL,
    SPECS_BASE_PATH,
    SPECS_DETAIL_PATH,
    VERSION_BY_ID_PATH,
    VERSION_CLOSE_PATH,
    VERSION_SET_LATEST_PATH,
    VERSIONS_PATH,
    WORKSPACES_PATH,
)
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
    FileListResponse,
    FileUploadResponse,
    PermissionCheckResponse,
    PublicSpecResponse,
    SpecCreateRequest,
    SpecCreateResponse,
    SpecFileResponse,
    SpecListResponse,
    SpecResponse,
    SpecUpdateRequest,
    SpecVersionResponse,
    VersionCloseResponse,
    VersionCreateResponse,
    VersionListResponse,
    VersionWithFilesResponse,
    WorkspaceListResponse,
    WorkspaceNotFoundError,
)

logger = get_logger(__name__)

# Chunk size for file uploads (1MB)
UPLOAD_CHUNK_SIZE = 1024 * 1024


class SpecsClient:
    """Async HTTP client for Shotgun Specs API."""

    def __init__(self, base_url: str | None = None, timeout: float = 30.0):
        """Initialize Specs client.

        Args:
            base_url: Base URL for Shotgun Web API. If None, uses SHOTGUN_WEB_BASE_URL
            timeout: Request timeout in seconds
        """
        self.base_url = base_url or SHOTGUN_WEB_BASE_URL
        self.timeout = timeout

    async def _get_auth_token(self) -> str:
        """Get supabase_jwt from ConfigManager.

        Returns:
            JWT token string

        Raises:
            UnauthorizedError: If user is not authenticated
        """
        config_manager = get_config_manager()
        config = await config_manager.load()
        jwt = config.shotgun.supabase_jwt
        if jwt is None:
            raise UnauthorizedError("Not authenticated. Run 'shotgun auth' to login.")
        return jwt.get_secret_value()

    def _raise_for_status(self, response: httpx.Response) -> None:
        """Raise typed exception based on HTTP status code.

        Args:
            response: HTTP response to check

        Raises:
            UnauthorizedError: 401 status
            ForbiddenError: 403 status
            NotFoundError: 404 status
            ConflictError: 409 status
            PayloadTooLargeError: 413 status
            RateLimitExceededError: 429 status
            ShotgunWebError: Other 4xx/5xx status codes
        """
        if response.is_success:
            return

        status = response.status_code
        try:
            error_data = response.json()
            message = error_data.get("message", response.text)
        except Exception:
            message = response.text

        if status == 401:
            raise UnauthorizedError(message)
        elif status == 403:
            raise ForbiddenError(message)
        elif status == 404:
            raise NotFoundError(message)
        elif status == 409:
            raise ConflictError(message)
        elif status == 413:
            raise PayloadTooLargeError(message)
        elif status == 429:
            raise RateLimitExceededError(message)
        else:
            raise ShotgunWebError(f"HTTP {status}: {message}")

    # =========================================================================
    # Workspace Methods
    # =========================================================================

    async def list_workspaces(self) -> WorkspaceListResponse:
        """List workspaces the current user has access to.

        Returns:
            WorkspaceListResponse with list of workspaces
        """
        token = await self._get_auth_token()
        url = f"{self.base_url}{WORKSPACES_PATH}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
            )
            self._raise_for_status(response)
            data = response.json()
            # Handle both formats: raw list or {"workspaces": [...]}
            if isinstance(data, list):
                data = {"workspaces": data}
            return WorkspaceListResponse.model_validate(data)

    async def get_or_fetch_workspace_id(self) -> str:
        """Get workspace_id from config or fetch it using current JWT.

        Returns:
            workspace_id string

        Raises:
            UnauthorizedError: If not authenticated
            WorkspaceNotFoundError: If user has no workspaces
        """
        config_manager = get_config_manager()
        config = await config_manager.load()

        # Check if already cached
        if config.shotgun.workspace_id:
            return config.shotgun.workspace_id

        # Fetch using existing JWT
        response = await self.list_workspaces()
        if not response.workspaces:
            raise WorkspaceNotFoundError("No workspaces found for user")

        workspace_id = response.workspaces[0].id

        # Cache for future use
        await config_manager.update_shotgun_account(workspace_id=workspace_id)

        return workspace_id

    # =========================================================================
    # Permission Methods
    # =========================================================================

    async def check_permissions(self, workspace_id: str) -> PermissionCheckResponse:
        """Check user permissions in workspace.

        Args:
            workspace_id: Workspace UUID

        Returns:
            PermissionCheckResponse with user's role and capabilities
        """
        token = await self._get_auth_token()
        url = f"{self.base_url}{PERMISSIONS_PATH.format(workspace_id=workspace_id)}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
            )
            self._raise_for_status(response)
            return PermissionCheckResponse.model_validate(response.json())

    # =========================================================================
    # Spec Methods
    # =========================================================================

    async def list_specs(
        self,
        workspace_id: str,
        page: int = 1,
        page_size: int = 50,
        sort: Literal["name", "created_on", "updated_on"] = "updated_on",
        order: Literal["asc", "desc"] = "desc",
    ) -> SpecListResponse:
        """List specs in workspace.

        Args:
            workspace_id: Workspace UUID
            page: Page number (1-indexed)
            page_size: Items per page (max 100)
            sort: Sort field
            order: Sort order

        Returns:
            SpecListResponse with paginated specs
        """
        token = await self._get_auth_token()
        url = f"{self.base_url}{SPECS_BASE_PATH.format(workspace_id=workspace_id)}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                url,
                params={
                    "page": page,
                    "page_size": page_size,
                    "sort": sort,
                    "order": order,
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            self._raise_for_status(response)
            return SpecListResponse.model_validate(response.json())

    async def get_spec(self, workspace_id: str, spec_id: str) -> SpecResponse:
        """Get spec details.

        Args:
            workspace_id: Workspace UUID
            spec_id: Spec UUID

        Returns:
            SpecResponse with spec details
        """
        token = await self._get_auth_token()
        url = f"{self.base_url}{SPECS_DETAIL_PATH.format(workspace_id=workspace_id, spec_id=spec_id)}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
            )
            self._raise_for_status(response)
            return SpecResponse.model_validate(response.json())

    async def create_spec(
        self,
        workspace_id: str,
        name: str,
        description: str | None = None,
    ) -> SpecCreateResponse:
        """Create a new spec with initial version in uploading state.

        Args:
            workspace_id: Workspace UUID
            name: Spec name (unique per workspace)
            description: Optional spec description

        Returns:
            SpecCreateResponse with spec, initial version, and upload URL
        """
        token = await self._get_auth_token()
        url = f"{self.base_url}{SPECS_BASE_PATH.format(workspace_id=workspace_id)}"
        request_data = SpecCreateRequest(name=name, description=description)
        request_body = request_data.model_dump(exclude_none=True)

        logger.debug(
            "Creating spec: POST %s with body=%s",
            url,
            request_body,
        )

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                url,
                json=request_body,
                headers={"Authorization": f"Bearer {token}"},
            )
            if not response.is_success:
                logger.error(
                    "create_spec failed: POST %s returned %d - %s",
                    url,
                    response.status_code,
                    response.text,
                )
            self._raise_for_status(response)
            return SpecCreateResponse.model_validate(response.json())

    async def update_spec(
        self,
        workspace_id: str,
        spec_id: str,
        name: str | None = None,
        description: str | None = None,
        is_public: bool | None = None,
    ) -> SpecResponse:
        """Update spec metadata or visibility.

        Args:
            workspace_id: Workspace UUID
            spec_id: Spec UUID
            name: New spec name
            description: New description
            is_public: New visibility setting

        Returns:
            Updated SpecResponse
        """
        token = await self._get_auth_token()
        url = f"{self.base_url}{SPECS_DETAIL_PATH.format(workspace_id=workspace_id, spec_id=spec_id)}"
        request_data = SpecUpdateRequest(
            name=name, description=description, is_public=is_public
        )

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.patch(
                url,
                json=request_data.model_dump(exclude_none=True),
                headers={"Authorization": f"Bearer {token}"},
            )
            self._raise_for_status(response)
            return SpecResponse.model_validate(response.json())

    # =========================================================================
    # Version Methods
    # =========================================================================

    async def list_versions(
        self,
        workspace_id: str,
        spec_id: str,
        page: int = 1,
        page_size: int = 50,
        state: str | None = None,
    ) -> VersionListResponse:
        """List versions of a spec.

        Args:
            workspace_id: Workspace UUID
            spec_id: Spec UUID
            page: Page number
            page_size: Items per page
            state: Filter by version state

        Returns:
            VersionListResponse with paginated versions
        """
        token = await self._get_auth_token()
        url = f"{self.base_url}{VERSIONS_PATH.format(workspace_id=workspace_id, spec_id=spec_id)}"
        params: dict[str, int | str] = {"page": page, "page_size": page_size}
        if state:
            params["state"] = state

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                url,
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )
            self._raise_for_status(response)
            return VersionListResponse.model_validate(response.json())

    async def create_version(
        self,
        workspace_id: str,
        spec_id: str,
        label: str | None = None,
        notes: str | None = None,
    ) -> VersionCreateResponse:
        """Create a new version for an existing spec.

        Args:
            workspace_id: Workspace UUID
            spec_id: Spec UUID
            label: Optional version label
            notes: Optional version notes

        Returns:
            VersionCreateResponse with version and upload URL
        """
        token = await self._get_auth_token()
        url = f"{self.base_url}{VERSIONS_PATH.format(workspace_id=workspace_id, spec_id=spec_id)}"
        request_data = {"spec_id": spec_id}
        if label:
            request_data["label"] = label
        if notes:
            request_data["notes"] = notes

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                url,
                json=request_data,
                headers={"Authorization": f"Bearer {token}"},
            )
            self._raise_for_status(response)
            return VersionCreateResponse.model_validate(response.json())

    async def close_version(
        self,
        workspace_id: str,
        spec_id: str,
        version_id: str,
    ) -> VersionCloseResponse:
        """Close/finalize a version.

        Transitions version from uploading to ready state.

        Args:
            workspace_id: Workspace UUID
            spec_id: Spec UUID
            version_id: Version UUID

        Returns:
            VersionCloseResponse with closed version and web URL
        """
        token = await self._get_auth_token()
        url = f"{self.base_url}{VERSION_CLOSE_PATH.format(workspace_id=workspace_id, spec_id=spec_id, version_id=version_id)}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {token}"},
            )
            self._raise_for_status(response)
            return VersionCloseResponse.model_validate(response.json())

    async def set_latest_version(
        self,
        workspace_id: str,
        spec_id: str,
        version_id: str,
    ) -> SpecVersionResponse:
        """Set version as latest.

        Args:
            workspace_id: Workspace UUID
            spec_id: Spec UUID
            version_id: Version UUID

        Returns:
            Updated SpecVersionResponse
        """
        token = await self._get_auth_token()
        url = f"{self.base_url}{VERSION_SET_LATEST_PATH.format(workspace_id=workspace_id, spec_id=spec_id, version_id=version_id)}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {token}"},
            )
            self._raise_for_status(response)
            return SpecVersionResponse.model_validate(response.json())

    async def get_version_with_files(self, version_id: str) -> VersionWithFilesResponse:
        """Get version metadata and files by version ID only.

        This is a convenience endpoint for CLI that doesn't require
        workspace_id or spec_id in the request path.

        Args:
            version_id: Version UUID

        Returns:
            VersionWithFilesResponse with version details, spec info, and files

        Raises:
            UnauthorizedError: If not authenticated
            NotFoundError: If version not found
            ForbiddenError: If user lacks access to the spec
        """
        token = await self._get_auth_token()
        url = f"{self.base_url}{VERSION_BY_ID_PATH.format(version_id=version_id)}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
            )
            self._raise_for_status(response)
            return VersionWithFilesResponse.model_validate(response.json())

    # =========================================================================
    # File Methods
    # =========================================================================

    async def list_files(
        self,
        workspace_id: str,
        spec_id: str,
        version_id: str,
        include_download_urls: bool = False,
    ) -> FileListResponse:
        """List files in a version.

        Args:
            workspace_id: Workspace UUID
            spec_id: Spec UUID
            version_id: Version UUID
            include_download_urls: Include pre-signed download URLs

        Returns:
            FileListResponse with files
        """
        token = await self._get_auth_token()
        url = f"{self.base_url}{FILES_PATH.format(workspace_id=workspace_id, spec_id=spec_id, version_id=version_id)}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                url,
                params={"include_download_urls": include_download_urls},
                headers={"Authorization": f"Bearer {token}"},
            )
            self._raise_for_status(response)
            return FileListResponse.model_validate(response.json())

    @retry(
        retry=retry_if_exception_type((httpx.HTTPError, ShotgunWebError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        reraise=True,
    )
    async def initiate_file_upload(
        self,
        workspace_id: str,
        spec_id: str,
        version_id: str,
        relative_path: str,
        size_bytes: int,
        content_hash: str,
    ) -> FileUploadResponse:
        """Initiate file upload to a version.

        Retries on transient failures with exponential backoff.

        Args:
            workspace_id: Workspace UUID
            spec_id: Spec UUID
            version_id: Version UUID
            relative_path: Path relative to .shotgun/
            size_bytes: File size in bytes
            content_hash: SHA-256 hash of file content

        Returns:
            FileUploadResponse with file details and pre-signed upload URL
        """
        token = await self._get_auth_token()
        url = f"{self.base_url}{FILES_PATH.format(workspace_id=workspace_id, spec_id=spec_id, version_id=version_id)}"
        request_data = {
            "spec_id": spec_id,
            "version_id": version_id,
            "relative_path": relative_path,
            "size_bytes": size_bytes,
            "content_hash": content_hash,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                url,
                json=request_data,
                headers={"Authorization": f"Bearer {token}"},
            )
            self._raise_for_status(response)
            return FileUploadResponse.model_validate(response.json())

    @retry(
        retry=retry_if_exception_type((httpx.HTTPError, ShotgunWebError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        reraise=True,
    )
    async def upload_file_to_presigned_url(
        self,
        presigned_url: str,
        file_path: Path,
    ) -> None:
        """Upload file content to pre-signed URL.

        Streams file in 1MB chunks with retry logic for transient failures.

        Args:
            presigned_url: Pre-signed URL to upload to
            file_path: Path to file to upload

        Raises:
            ShotgunWebError: If upload fails after retries
        """
        logger.debug("Uploading file %s to presigned URL", file_path)

        async def file_stream() -> AsyncIterator[bytes]:
            async with aiofiles.open(file_path, "rb") as f:
                while chunk := await f.read(UPLOAD_CHUNK_SIZE):
                    yield chunk

        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.put(
                presigned_url,
                content=file_stream(),
            )
            if not response.is_success:
                raise ShotgunWebError(
                    f"Failed to upload file: HTTP {response.status_code}"
                )

        logger.debug("Successfully uploaded file %s", file_path)

    # =========================================================================
    # Public Access Methods (No Authentication Required)
    # =========================================================================

    async def get_public_spec(self, spec_id: str) -> PublicSpecResponse:
        """Get public spec details.

        No authentication required.

        Args:
            spec_id: Spec UUID

        Returns:
            PublicSpecResponse with spec details (latest version only)
        """
        url = f"{self.base_url}{PUBLIC_SPEC_PATH.format(spec_id=spec_id)}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url)
            self._raise_for_status(response)
            return PublicSpecResponse.model_validate(response.json())

    async def get_public_spec_files(
        self,
        spec_id: str,
        include_download_urls: bool = True,
    ) -> FileListResponse:
        """List files in latest version of public spec.

        No authentication required.

        Args:
            spec_id: Spec UUID
            include_download_urls: Include pre-signed download URLs

        Returns:
            FileListResponse with files from latest version
        """
        url = f"{self.base_url}{PUBLIC_SPEC_FILES_PATH.format(spec_id=spec_id)}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                url,
                params={"include_download_urls": include_download_urls},
            )
            self._raise_for_status(response)
            return FileListResponse.model_validate(response.json())

    async def get_public_file(self, spec_id: str, file_id: str) -> SpecFileResponse:
        """Get file details from public spec.

        No authentication required.

        Args:
            spec_id: Spec UUID
            file_id: File UUID

        Returns:
            SpecFileResponse with file details and download URL
        """
        url = f"{self.base_url}{PUBLIC_FILE_PATH.format(spec_id=spec_id, file_id=file_id)}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url)
            self._raise_for_status(response)
            return SpecFileResponse.model_validate(response.json())
