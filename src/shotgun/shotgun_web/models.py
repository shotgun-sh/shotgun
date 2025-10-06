"""Pydantic models for Shotgun Web API."""

from enum import StrEnum

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
