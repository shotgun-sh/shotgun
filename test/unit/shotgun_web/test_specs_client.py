"""Tests for shotgun_web.specs_client module."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr

from shotgun.shotgun_web.constants import SHOTGUN_WEB_BASE_URL
from shotgun.shotgun_web.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    PayloadTooLargeError,
    RateLimitExceededError,
    ShotgunWebError,
    UnauthorizedError,
)
from shotgun.shotgun_web.specs_client import SpecsClient


@pytest.fixture
def specs_client() -> SpecsClient:
    """Create a SpecsClient instance for testing."""
    return SpecsClient(base_url="https://test.example.com", timeout=10.0)


@pytest.fixture
def mock_config():
    """Mock the ConfigManager and config for auth tests."""
    mock_config_obj = MagicMock()
    mock_config_obj.shotgun.supabase_jwt = SecretStr("test-jwt-token")
    return mock_config_obj


@pytest.fixture
def mock_config_no_jwt():
    """Mock the ConfigManager without JWT for auth tests."""
    mock_config_obj = MagicMock()
    mock_config_obj.shotgun.supabase_jwt = None
    return mock_config_obj


def test_specs_client_init_default():
    """Test SpecsClient initialization with defaults."""
    client = SpecsClient()
    assert client.base_url == SHOTGUN_WEB_BASE_URL
    assert client.timeout == 30.0


def test_specs_client_init_custom():
    """Test SpecsClient initialization with custom values."""
    client = SpecsClient(base_url="https://custom.example.com", timeout=60.0)
    assert client.base_url == "https://custom.example.com"
    assert client.timeout == 60.0


@pytest.mark.asyncio
async def test_get_auth_token_success(specs_client: SpecsClient, mock_config):
    """Test _get_auth_token returns JWT when authenticated."""
    mock_manager = AsyncMock()
    mock_manager.load.return_value = mock_config

    with patch(
        "shotgun.shotgun_web.specs_client.get_config_manager",
        return_value=mock_manager,
    ):
        token = await specs_client._get_auth_token()
        assert token == "test-jwt-token"  # noqa: S105


@pytest.mark.asyncio
async def test_get_auth_token_not_authenticated(
    specs_client: SpecsClient, mock_config_no_jwt
):
    """Test _get_auth_token raises UnauthorizedError when not authenticated."""
    mock_manager = AsyncMock()
    mock_manager.load.return_value = mock_config_no_jwt

    with patch(
        "shotgun.shotgun_web.specs_client.get_config_manager",
        return_value=mock_manager,
    ):
        with pytest.raises(UnauthorizedError, match="Not authenticated"):
            await specs_client._get_auth_token()


def test_raise_for_status_success(specs_client: SpecsClient):
    """Test _raise_for_status does not raise on success."""
    response = MagicMock()
    response.is_success = True
    # Should not raise
    specs_client._raise_for_status(response)


def test_raise_for_status_401(specs_client: SpecsClient):
    """Test _raise_for_status raises UnauthorizedError on 401."""
    response = MagicMock()
    response.is_success = False
    response.status_code = 401
    response.json.return_value = {"message": "Invalid token"}

    with pytest.raises(UnauthorizedError, match="Invalid token"):
        specs_client._raise_for_status(response)


def test_raise_for_status_403(specs_client: SpecsClient):
    """Test _raise_for_status raises ForbiddenError on 403."""
    response = MagicMock()
    response.is_success = False
    response.status_code = 403
    response.json.return_value = {"message": "Access denied"}

    with pytest.raises(ForbiddenError, match="Access denied"):
        specs_client._raise_for_status(response)


def test_raise_for_status_404(specs_client: SpecsClient):
    """Test _raise_for_status raises NotFoundError on 404."""
    response = MagicMock()
    response.is_success = False
    response.status_code = 404
    response.json.return_value = {"message": "Not found"}

    with pytest.raises(NotFoundError, match="Not found"):
        specs_client._raise_for_status(response)


def test_raise_for_status_409(specs_client: SpecsClient):
    """Test _raise_for_status raises ConflictError on 409."""
    response = MagicMock()
    response.is_success = False
    response.status_code = 409
    response.json.return_value = {"message": "Name already exists"}

    with pytest.raises(ConflictError, match="Name already exists"):
        specs_client._raise_for_status(response)


def test_raise_for_status_413(specs_client: SpecsClient):
    """Test _raise_for_status raises PayloadTooLargeError on 413."""
    response = MagicMock()
    response.is_success = False
    response.status_code = 413
    response.json.return_value = {"message": "File too large"}

    with pytest.raises(PayloadTooLargeError, match="File too large"):
        specs_client._raise_for_status(response)


def test_raise_for_status_429(specs_client: SpecsClient):
    """Test _raise_for_status raises RateLimitExceededError on 429."""
    response = MagicMock()
    response.is_success = False
    response.status_code = 429
    response.json.return_value = {"message": "Rate limit exceeded"}

    with pytest.raises(RateLimitExceededError, match="Rate limit exceeded"):
        specs_client._raise_for_status(response)


def test_raise_for_status_500(specs_client: SpecsClient):
    """Test _raise_for_status raises ShotgunWebError on 500."""
    response = MagicMock()
    response.is_success = False
    response.status_code = 500
    response.json.return_value = {"message": "Internal error"}

    with pytest.raises(ShotgunWebError, match="HTTP 500: Internal error"):
        specs_client._raise_for_status(response)


def test_raise_for_status_json_parse_error(specs_client: SpecsClient):
    """Test _raise_for_status handles JSON parse errors."""
    response = MagicMock()
    response.is_success = False
    response.status_code = 500
    response.json.side_effect = ValueError("Invalid JSON")
    response.text = "Server error"

    with pytest.raises(ShotgunWebError, match="HTTP 500: Server error"):
        specs_client._raise_for_status(response)


def _create_mock_async_client(mock_response):
    """Helper to create a properly mocked async httpx client."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.patch = AsyncMock(return_value=mock_response)
    mock_client.put = AsyncMock(return_value=mock_response)
    return mock_client


# Helper function to create valid SpecVersionResponse data
def _version_data(
    version_id: str = "version-123",
    spec_id: str = "spec-123",
    workspace_id: str = "workspace-123",
    version_number: int = 1,
    state: str = "ready",
    is_latest: bool = True,
) -> dict:
    return {
        "id": version_id,
        "spec_id": spec_id,
        "workspace_id": workspace_id,
        "state": state,
        "is_latest": is_latest,
        "label": f"v{version_number}",
        "notes": None,
        "created_by": "user-123",
        "created_by_email": "user@example.com",
        "created_at": "2024-01-01T00:00:00Z",
        "file_count": 4,
        "total_size_bytes": 10000,
    }


# Helper function to create valid SpecResponse data
def _spec_data(
    spec_id: str = "spec-123",
    workspace_id: str = "workspace-123",
    name: str = "Test Spec",
    is_public: bool = False,
) -> dict:
    return {
        "id": spec_id,
        "workspace_id": workspace_id,
        "name": name,
        "description": "A test spec",
        "is_public": is_public,
        "created_by": "user-123",
        "created_by_email": "user@example.com",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
        "updated_by_email": "user@example.com",
        "latest_version": None,
        "version_count": 1,
    }


# Helper function to create valid SpecFileResponse data
def _file_data(
    file_id: str = "file-123",
    relative_path: str = "research.md",
    size_bytes: int = 1024,
) -> dict:
    return {
        "id": file_id,
        "relative_path": relative_path,
        "bucket_key": f"specs/spec-123/version-123/{relative_path}",
        "size_bytes": size_bytes,
        "content_hash": "a" * 64,
        "content_type": "text/markdown",
        "uploaded_at": "2024-01-01T00:00:00Z",
        "download_url": f"https://storage.example.com/download/{file_id}",
    }


@pytest.mark.asyncio
async def test_check_permissions(specs_client: SpecsClient, mock_config):
    """Test check_permissions API call."""
    mock_manager = AsyncMock()
    mock_manager.load.return_value = mock_config

    mock_response = MagicMock()
    mock_response.is_success = True
    mock_response.json.return_value = {
        "workspace_id": "workspace-123",
        "user_role": "editor",
        "can_create_specs": True,
        "can_upload_versions": True,
        "can_set_latest": True,
        "can_change_visibility": False,
    }

    mock_client = _create_mock_async_client(mock_response)

    with (
        patch(
            "shotgun.shotgun_web.specs_client.get_config_manager",
            return_value=mock_manager,
        ),
        patch(
            "httpx.AsyncClient",
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_client)),
        ),
    ):
        result = await specs_client.check_permissions("workspace-123")

        assert result.user_role == "editor"
        assert result.can_create_specs is True
        assert result.can_upload_versions is True
        assert result.can_change_visibility is False


@pytest.mark.asyncio
async def test_list_specs(specs_client: SpecsClient, mock_config):
    """Test list_specs API call."""
    mock_manager = AsyncMock()
    mock_manager.load.return_value = mock_config

    mock_response = MagicMock()
    mock_response.is_success = True
    mock_response.json.return_value = {
        "specs": [_spec_data()],
        "total": 1,
        "page": 1,
        "page_size": 50,
    }

    mock_client = _create_mock_async_client(mock_response)

    with (
        patch(
            "shotgun.shotgun_web.specs_client.get_config_manager",
            return_value=mock_manager,
        ),
        patch(
            "httpx.AsyncClient",
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_client)),
        ),
    ):
        result = await specs_client.list_specs("workspace-123")

        assert result.total == 1
        assert len(result.specs) == 1
        assert result.specs[0].name == "Test Spec"


@pytest.mark.asyncio
async def test_get_spec(specs_client: SpecsClient, mock_config):
    """Test get_spec API call."""
    mock_manager = AsyncMock()
    mock_manager.load.return_value = mock_config

    mock_response = MagicMock()
    mock_response.is_success = True
    mock_response.json.return_value = _spec_data(is_public=True)

    mock_client = _create_mock_async_client(mock_response)

    with (
        patch(
            "shotgun.shotgun_web.specs_client.get_config_manager",
            return_value=mock_manager,
        ),
        patch(
            "httpx.AsyncClient",
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_client)),
        ),
    ):
        result = await specs_client.get_spec("workspace-123", "spec-123")

        assert result.id == "spec-123"
        assert result.name == "Test Spec"
        assert result.is_public is True


@pytest.mark.asyncio
async def test_create_spec(specs_client: SpecsClient, mock_config):
    """Test create_spec API call."""
    mock_manager = AsyncMock()
    mock_manager.load.return_value = mock_config

    mock_response = MagicMock()
    mock_response.is_success = True
    mock_response.json.return_value = {
        "spec": _spec_data(name="New Spec"),
        "version": _version_data(state="uploading"),
        "upload_url": "https://storage.example.com/upload",
    }

    mock_client = _create_mock_async_client(mock_response)

    with (
        patch(
            "shotgun.shotgun_web.specs_client.get_config_manager",
            return_value=mock_manager,
        ),
        patch(
            "httpx.AsyncClient",
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_client)),
        ),
    ):
        result = await specs_client.create_spec(
            "workspace-123", "New Spec", description="Test description"
        )

        assert result.spec.id == "spec-123"
        assert result.spec.name == "New Spec"
        assert result.version.state == "uploading"


@pytest.mark.asyncio
async def test_update_spec(specs_client: SpecsClient, mock_config):
    """Test update_spec API call."""
    mock_manager = AsyncMock()
    mock_manager.load.return_value = mock_config

    mock_response = MagicMock()
    mock_response.is_success = True
    mock_response.json.return_value = _spec_data(name="Updated Spec", is_public=True)

    mock_client = _create_mock_async_client(mock_response)

    with (
        patch(
            "shotgun.shotgun_web.specs_client.get_config_manager",
            return_value=mock_manager,
        ),
        patch(
            "httpx.AsyncClient",
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_client)),
        ),
    ):
        result = await specs_client.update_spec(
            "workspace-123", "spec-123", name="Updated Spec", is_public=True
        )

        assert result.name == "Updated Spec"
        assert result.is_public is True


@pytest.mark.asyncio
async def test_list_versions(specs_client: SpecsClient, mock_config):
    """Test list_versions API call."""
    mock_manager = AsyncMock()
    mock_manager.load.return_value = mock_config

    mock_response = MagicMock()
    mock_response.is_success = True
    mock_response.json.return_value = {
        "versions": [_version_data()],
        "spec_id": "spec-123",
        "total": 1,
        "page": 1,
        "page_size": 50,
    }

    mock_client = _create_mock_async_client(mock_response)

    with (
        patch(
            "shotgun.shotgun_web.specs_client.get_config_manager",
            return_value=mock_manager,
        ),
        patch(
            "httpx.AsyncClient",
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_client)),
        ),
    ):
        result = await specs_client.list_versions("workspace-123", "spec-123")

        assert result.total == 1
        assert len(result.versions) == 1
        assert result.versions[0].state == "ready"


@pytest.mark.asyncio
async def test_create_version(specs_client: SpecsClient, mock_config):
    """Test create_version API call."""
    mock_manager = AsyncMock()
    mock_manager.load.return_value = mock_config

    mock_response = MagicMock()
    mock_response.is_success = True
    mock_response.json.return_value = {
        "version": _version_data(
            version_id="version-456", version_number=2, state="uploading"
        ),
        "upload_url": "https://storage.example.com/upload",
    }

    mock_client = _create_mock_async_client(mock_response)

    with (
        patch(
            "shotgun.shotgun_web.specs_client.get_config_manager",
            return_value=mock_manager,
        ),
        patch(
            "httpx.AsyncClient",
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_client)),
        ),
    ):
        result = await specs_client.create_version(
            "workspace-123", "spec-123", label="v2.0", notes="Release notes"
        )

        assert result.version.id == "version-456"
        assert result.version.state == "uploading"


@pytest.mark.asyncio
async def test_close_version(specs_client: SpecsClient, mock_config):
    """Test close_version API call."""
    mock_manager = AsyncMock()
    mock_manager.load.return_value = mock_config

    mock_response = MagicMock()
    mock_response.is_success = True
    mock_response.json.return_value = {
        "version": _version_data(state="ready"),
        "web_url": "https://shotgun.sh/specs/spec-123/v/1",
    }

    mock_client = _create_mock_async_client(mock_response)

    with (
        patch(
            "shotgun.shotgun_web.specs_client.get_config_manager",
            return_value=mock_manager,
        ),
        patch(
            "httpx.AsyncClient",
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_client)),
        ),
    ):
        result = await specs_client.close_version(
            "workspace-123", "spec-123", "version-123"
        )

        assert result.version.state == "ready"
        assert result.web_url == "https://shotgun.sh/specs/spec-123/v/1"


@pytest.mark.asyncio
async def test_set_latest_version(specs_client: SpecsClient, mock_config):
    """Test set_latest_version API call."""
    mock_manager = AsyncMock()
    mock_manager.load.return_value = mock_config

    mock_response = MagicMock()
    mock_response.is_success = True
    mock_response.json.return_value = _version_data(is_latest=True)

    mock_client = _create_mock_async_client(mock_response)

    with (
        patch(
            "shotgun.shotgun_web.specs_client.get_config_manager",
            return_value=mock_manager,
        ),
        patch(
            "httpx.AsyncClient",
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_client)),
        ),
    ):
        result = await specs_client.set_latest_version(
            "workspace-123", "spec-123", "version-123"
        )

        assert result.is_latest is True


@pytest.mark.asyncio
async def test_list_files(specs_client: SpecsClient, mock_config):
    """Test list_files API call."""
    mock_manager = AsyncMock()
    mock_manager.load.return_value = mock_config

    mock_response = MagicMock()
    mock_response.is_success = True
    mock_response.json.return_value = {
        "files": [_file_data()],
        "version_id": "version-123",
        "total": 1,
    }

    mock_client = _create_mock_async_client(mock_response)

    with (
        patch(
            "shotgun.shotgun_web.specs_client.get_config_manager",
            return_value=mock_manager,
        ),
        patch(
            "httpx.AsyncClient",
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_client)),
        ),
    ):
        result = await specs_client.list_files(
            "workspace-123", "spec-123", "version-123"
        )

        assert result.total == 1
        assert len(result.files) == 1
        assert result.files[0].relative_path == "research.md"


@pytest.mark.asyncio
async def test_initiate_file_upload(specs_client: SpecsClient, mock_config):
    """Test initiate_file_upload API call."""
    mock_manager = AsyncMock()
    mock_manager.load.return_value = mock_config

    mock_response = MagicMock()
    mock_response.is_success = True
    mock_response.json.return_value = {
        "file": _file_data(file_id="file-456", relative_path="specification.md"),
        "upload_url": "https://storage.example.com/upload/file-456",
    }

    mock_client = _create_mock_async_client(mock_response)

    with (
        patch(
            "shotgun.shotgun_web.specs_client.get_config_manager",
            return_value=mock_manager,
        ),
        patch(
            "httpx.AsyncClient",
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_client)),
        ),
    ):
        result = await specs_client.initiate_file_upload(
            "workspace-123",
            "spec-123",
            "version-123",
            "specification.md",
            2048,
            "d" * 64,
        )

        assert result.file.relative_path == "specification.md"
        assert result.upload_url == "https://storage.example.com/upload/file-456"


@pytest.mark.asyncio
async def test_upload_file_to_presigned_url(specs_client: SpecsClient, tmp_path: Path):
    """Test upload_file_to_presigned_url uploads file content."""
    # Create a test file
    test_file = tmp_path / "test.txt"
    test_file.write_text("Test content")

    mock_response = MagicMock()
    mock_response.is_success = True

    mock_client = _create_mock_async_client(mock_response)

    with patch(
        "httpx.AsyncClient",
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_client)),
    ):
        await specs_client.upload_file_to_presigned_url(
            "https://storage.example.com/upload", test_file
        )

        mock_client.put.assert_called_once()


@pytest.mark.asyncio
async def test_upload_file_to_presigned_url_failure(
    specs_client: SpecsClient, tmp_path: Path
):
    """Test upload_file_to_presigned_url raises error on failure."""
    # Create a test file
    test_file = tmp_path / "test.txt"
    test_file.write_text("Test content")

    mock_response = MagicMock()
    mock_response.is_success = False
    mock_response.status_code = 500

    mock_client = _create_mock_async_client(mock_response)

    with (
        patch(
            "httpx.AsyncClient",
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_client)),
        ),
        patch(
            "shotgun.shotgun_web.specs_client.retry",
            side_effect=lambda **kwargs: lambda f: f,
        ),
    ):
        # Recreate client to apply patched decorator
        client = SpecsClient(base_url="https://test.example.com")

        with pytest.raises(ShotgunWebError, match="Failed to upload file"):
            await client.upload_file_to_presigned_url(
                "https://storage.example.com/upload", test_file
            )


@pytest.mark.asyncio
async def test_get_public_spec(specs_client: SpecsClient):
    """Test get_public_spec API call (no auth required)."""
    mock_response = MagicMock()
    mock_response.is_success = True
    mock_response.json.return_value = {
        "id": "spec-123",
        "name": "Public Spec",
        "description": "A public spec",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
        "latest_version": _version_data(),
    }

    mock_client = _create_mock_async_client(mock_response)

    with patch(
        "httpx.AsyncClient",
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_client)),
    ):
        result = await specs_client.get_public_spec("spec-123")

        assert result.name == "Public Spec"


@pytest.mark.asyncio
async def test_get_public_spec_files(specs_client: SpecsClient):
    """Test get_public_spec_files API call (no auth required)."""
    mock_response = MagicMock()
    mock_response.is_success = True
    mock_response.json.return_value = {
        "files": [_file_data()],
        "version_id": "version-123",
        "total": 1,
    }

    mock_client = _create_mock_async_client(mock_response)

    with patch(
        "httpx.AsyncClient",
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_client)),
    ):
        result = await specs_client.get_public_spec_files("spec-123")

        assert result.total == 1
        assert result.files[0].download_url is not None


@pytest.mark.asyncio
async def test_get_public_file(specs_client: SpecsClient):
    """Test get_public_file API call (no auth required)."""
    mock_response = MagicMock()
    mock_response.is_success = True
    mock_response.json.return_value = _file_data()

    mock_client = _create_mock_async_client(mock_response)

    with patch(
        "httpx.AsyncClient",
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_client)),
    ):
        result = await specs_client.get_public_file("spec-123", "file-123")

        assert result.relative_path == "research.md"
        assert result.download_url is not None
