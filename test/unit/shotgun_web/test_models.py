"""Tests for Shotgun Web API models."""

import pytest
from pydantic import ValidationError

from shotgun.shotgun_web.models import (
    TokenCreateRequest,
    TokenCreateResponse,
    TokenStatus,
    TokenStatusResponse,
)


def test_token_status_enum():
    """Test TokenStatus enum values."""
    assert TokenStatus.PENDING == "pending"
    assert TokenStatus.COMPLETED == "completed"
    assert TokenStatus.AWAITING_PAYMENT == "awaiting_payment"
    assert TokenStatus.EXPIRED == "expired"


def test_token_create_request():
    """Test TokenCreateRequest model."""
    request = TokenCreateRequest(shotgun_instance_id="test-uuid-123")
    assert request.shotgun_instance_id == "test-uuid-123"

    # Test dict conversion
    data = request.model_dump()
    assert data == {"shotgun_instance_id": "test-uuid-123"}


def test_token_create_response():
    """Test TokenCreateResponse model."""
    response = TokenCreateResponse(
        token="test-token",  # noqa: S106
        auth_url="https://example.com/auth",
        expires_in_seconds=1800,
    )
    assert response.token == "test-token"  # noqa: S105
    assert response.auth_url == "https://example.com/auth"
    assert response.expires_in_seconds == 1800


def test_token_create_response_validation():
    """Test TokenCreateResponse validation."""
    # Missing required fields should raise ValidationError
    with pytest.raises(ValidationError):
        TokenCreateResponse()  # type: ignore

    # Invalid expires_in_seconds type
    with pytest.raises(ValidationError):
        TokenCreateResponse(
            token="test",  # noqa: S106
            auth_url="https://example.com",
            expires_in_seconds="invalid",  # type: ignore
        )


def test_token_status_response_pending():
    """Test TokenStatusResponse with pending status."""
    response = TokenStatusResponse(
        status=TokenStatus.PENDING,
        message="Waiting for authentication",
    )
    assert response.status == TokenStatus.PENDING
    assert response.message == "Waiting for authentication"
    assert response.supabase_key is None
    assert response.litellm_key is None


def test_token_status_response_completed():
    """Test TokenStatusResponse with completed status."""
    response = TokenStatusResponse(
        status=TokenStatus.COMPLETED,
        supabase_key="supabase-jwt-token",
        litellm_key="litellm-api-key",
        message="Authentication successful",
    )
    assert response.status == TokenStatus.COMPLETED
    assert response.supabase_key == "supabase-jwt-token"
    assert response.litellm_key == "litellm-api-key"
    assert response.message == "Authentication successful"


def test_token_status_response_from_dict():
    """Test TokenStatusResponse from API response dict."""
    # Simulate API response
    api_data = {
        "status": "completed",
        "supabase_key": "jwt-token",
        "litellm_key": "api-key",
        "message": "Success",
    }

    response = TokenStatusResponse.model_validate(api_data)
    assert response.status == TokenStatus.COMPLETED
    assert response.supabase_key == "jwt-token"
    assert response.litellm_key == "api-key"
    assert response.message == "Success"


def test_token_status_response_optional_fields():
    """Test TokenStatusResponse with optional fields."""
    # Only status is required
    response = TokenStatusResponse(status=TokenStatus.PENDING)
    assert response.status == TokenStatus.PENDING
    assert response.supabase_key is None
    assert response.litellm_key is None
    assert response.message is None
