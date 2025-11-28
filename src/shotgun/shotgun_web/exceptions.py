"""Typed exceptions for Shotgun Web API operations."""


class ShotgunWebError(Exception):
    """Base exception for Shotgun Web API operations."""


class UnauthorizedError(ShotgunWebError):
    """401 - Missing or invalid authentication token."""


class ForbiddenError(ShotgunWebError):
    """403 - Insufficient permissions for the requested operation."""


class NotFoundError(ShotgunWebError):
    """404 - Resource not found."""


class ConflictError(ShotgunWebError):
    """409 - Name conflict or duplicate path."""


class PayloadTooLargeError(ShotgunWebError):
    """413 - File exceeds maximum size limit."""


class RateLimitExceededError(ShotgunWebError):
    """429 - Rate limit exceeded."""
