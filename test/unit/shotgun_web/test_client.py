"""Tests for Shotgun Web API client."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from shotgun.shotgun_web.client import (
    ShotgunWebClient,
    check_token_status,
    create_unification_token,
)
from shotgun.shotgun_web.constants import SHOTGUN_WEB_BASE_URL
from shotgun.shotgun_web.models import (
    TokenStatus,
)


@pytest.fixture
def mock_httpx_post():
    """Mock httpx.post."""
    with patch("httpx.post") as mock:
        yield mock


@pytest.fixture
def mock_httpx_get():
    """Mock httpx.get."""
    with patch("httpx.get") as mock:
        yield mock


def test_shotgun_web_client_init():
    """Test ShotgunWebClient initialization."""
    # Default initialization
    client = ShotgunWebClient()
    assert client.base_url == SHOTGUN_WEB_BASE_URL
    assert client.timeout == 10.0

    # Custom initialization
    custom_client = ShotgunWebClient(base_url="https://custom.url", timeout=30.0)
    assert custom_client.base_url == "https://custom.url"
    assert custom_client.timeout == 30.0


def test_create_unification_token_success(mock_httpx_post):
    """Test successful token creation."""
    # Setup mock response
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "token": "test-token-123",
        "auth_url": "https://example.com/auth?token=test-token-123",
        "expires_in_seconds": 1800,
    }
    mock_response.raise_for_status = MagicMock()
    mock_httpx_post.return_value = mock_response

    # Create client and call method
    client = ShotgunWebClient()
    result = client.create_unification_token("instance-uuid-123")

    # Assertions
    assert result.token == "test-token-123"  # noqa: S105
    assert result.auth_url == "https://example.com/auth?token=test-token-123"
    assert result.expires_in_seconds == 1800

    # Verify HTTP call
    mock_httpx_post.assert_called_once()
    call_args = mock_httpx_post.call_args
    assert call_args[1]["json"] == {"shotgun_instance_id": "instance-uuid-123"}
    assert call_args[1]["timeout"] == 10.0


def test_create_unification_token_http_error(mock_httpx_post):
    """Test token creation with HTTP error."""
    # Setup mock to raise HTTP error
    mock_httpx_post.side_effect = httpx.HTTPStatusError(
        "Bad Request", request=MagicMock(), response=MagicMock()
    )

    # Create client and expect exception
    client = ShotgunWebClient()
    with pytest.raises(httpx.HTTPStatusError):
        client.create_unification_token("instance-uuid-123")


def test_check_token_status_pending(mock_httpx_get):
    """Test checking token status - pending."""
    # Setup mock response
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "status": "pending",
        "message": "Waiting for authentication",
    }
    mock_response.raise_for_status = MagicMock()
    mock_httpx_get.return_value = mock_response

    # Create client and call method
    client = ShotgunWebClient()
    result = client.check_token_status("test-token")

    # Assertions
    assert result.status == TokenStatus.PENDING
    assert result.message == "Waiting for authentication"
    assert result.supabase_key is None
    assert result.litellm_key is None

    # Verify HTTP call
    mock_httpx_get.assert_called_once()


def test_check_token_status_completed(mock_httpx_get):
    """Test checking token status - completed."""
    # Setup mock response
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "status": "completed",
        "supabase_key": "supabase-jwt-token",
        "litellm_key": "litellm-api-key",
        "message": "Authentication successful",
    }
    mock_response.raise_for_status = MagicMock()
    mock_httpx_get.return_value = mock_response

    # Create client and call method
    client = ShotgunWebClient()
    result = client.check_token_status("test-token")

    # Assertions
    assert result.status == TokenStatus.COMPLETED
    assert result.supabase_key == "supabase-jwt-token"
    assert result.litellm_key == "litellm-api-key"
    assert result.message == "Authentication successful"


def test_check_token_status_awaiting_payment(mock_httpx_get):
    """Test checking token status - awaiting payment."""
    # Setup mock response
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "status": "awaiting_payment",
        "message": "Waiting for payment",
    }
    mock_response.raise_for_status = MagicMock()
    mock_httpx_get.return_value = mock_response

    # Create client and call method
    client = ShotgunWebClient()
    result = client.check_token_status("test-token")

    # Assertions
    assert result.status == TokenStatus.AWAITING_PAYMENT
    assert result.message == "Waiting for payment"


def test_check_token_status_expired(mock_httpx_get):
    """Test checking token status - expired."""
    # Setup mock response
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "status": "expired",
        "message": "Token has expired",
    }
    mock_response.raise_for_status = MagicMock()
    mock_httpx_get.return_value = mock_response

    # Create client and call method
    client = ShotgunWebClient()
    result = client.check_token_status("test-token")

    # Assertions
    assert result.status == TokenStatus.EXPIRED
    assert result.message == "Token has expired"


def test_check_token_status_404_error(mock_httpx_get):
    """Test checking token status - 404 not found."""
    # Setup mock to raise 404 error
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_httpx_get.side_effect = httpx.HTTPStatusError(
        "Not Found", request=MagicMock(), response=mock_response
    )

    # Create client and expect exception
    client = ShotgunWebClient()
    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        client.check_token_status("test-token")

    assert exc_info.value.response.status_code == 404


def test_check_token_status_410_error(mock_httpx_get):
    """Test checking token status - 410 gone (expired)."""
    # Setup mock to raise 410 error
    mock_response = MagicMock()
    mock_response.status_code = 410
    mock_httpx_get.side_effect = httpx.HTTPStatusError(
        "Gone", request=MagicMock(), response=mock_response
    )

    # Create client and expect exception
    client = ShotgunWebClient()
    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        client.check_token_status("test-token")

    assert exc_info.value.response.status_code == 410


def test_create_unification_token_convenience_function(mock_httpx_post):
    """Test create_unification_token convenience function."""
    # Setup mock response
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "token": "test-token",
        "auth_url": "https://example.com/auth",
        "expires_in_seconds": 1800,
    }
    mock_response.raise_for_status = MagicMock()
    mock_httpx_post.return_value = mock_response

    # Call convenience function
    result = create_unification_token("instance-uuid")

    # Assertions
    assert result.token == "test-token"  # noqa: S105
    mock_httpx_post.assert_called_once()


def test_check_token_status_convenience_function(mock_httpx_get):
    """Test check_token_status convenience function."""
    # Setup mock response
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "status": "pending",
        "message": "Waiting",
    }
    mock_response.raise_for_status = MagicMock()
    mock_httpx_get.return_value = mock_response

    # Call convenience function
    result = check_token_status("test-token")

    # Assertions
    assert result.status == TokenStatus.PENDING
    mock_httpx_get.assert_called_once()


def test_get_me_success(mock_httpx_get):
    """Test successful get_me call."""
    # Setup mock response
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "id": "user-uuid-123",
        "email": "test@example.com",
        "first_name": "Test",
        "last_name": "User",
        "workspace": {
            "id": "workspace-uuid-456",
            "name": "Test Workspace",
            "role": "owner",
        },
        "has_completed_unification": True,
        "last_unification_at": "2025-01-15T10:30:00Z",
    }
    mock_response.raise_for_status = MagicMock()
    mock_httpx_get.return_value = mock_response

    # Create client and call method
    client = ShotgunWebClient()
    result = client.get_me("test-jwt-token")

    # Assertions
    assert result.id == "user-uuid-123"
    assert result.email == "test@example.com"
    assert result.first_name == "Test"
    assert result.last_name == "User"
    assert result.workspace.id == "workspace-uuid-456"
    assert result.workspace.name == "Test Workspace"
    assert result.workspace.role == "owner"
    assert result.has_completed_unification is True

    # Verify HTTP call with auth header
    mock_httpx_get.assert_called_once()
    call_args = mock_httpx_get.call_args
    assert call_args[1]["headers"] == {"Authorization": "Bearer test-jwt-token"}
    assert call_args[1]["timeout"] == 10.0


def test_get_me_success_with_null_names(mock_httpx_get):
    """Test successful get_me call with null first_name and last_name."""
    # Setup mock response with null names (as returned by real API)
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "id": "user-uuid-123",
        "email": "test@example.com",
        "first_name": None,
        "last_name": None,
        "workspace": {
            "id": "workspace-uuid-456",
            "name": "Test Workspace",
            "role": "owner",
        },
        "has_completed_unification": True,
        "last_unification_at": "2025-01-15T10:30:00Z",
    }
    mock_response.raise_for_status = MagicMock()
    mock_httpx_get.return_value = mock_response

    # Create client and call method
    client = ShotgunWebClient()
    result = client.get_me("test-jwt-token")

    # Assertions
    assert result.id == "user-uuid-123"
    assert result.email == "test@example.com"
    assert result.first_name is None
    assert result.last_name is None
    assert result.workspace.id == "workspace-uuid-456"


def test_get_me_401_error(mock_httpx_get):
    """Test get_me with 401 unauthorized error."""
    # Setup mock to raise 401 error
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_httpx_get.side_effect = httpx.HTTPStatusError(
        "Unauthorized", request=MagicMock(), response=mock_response
    )

    # Create client and expect exception
    client = ShotgunWebClient()
    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        client.get_me("invalid-jwt-token")

    assert exc_info.value.response.status_code == 401


def test_get_me_http_error(mock_httpx_get):
    """Test get_me with generic HTTP error."""
    # Setup mock to raise HTTP error
    mock_httpx_get.side_effect = httpx.HTTPError("Connection error")

    # Create client and expect exception
    client = ShotgunWebClient()
    with pytest.raises(httpx.HTTPError):
        client.get_me("test-jwt-token")
