"""SDK-specific exceptions."""


class ShotgunSDKError(Exception):
    """Base exception for all SDK operations."""


class CodebaseNotFoundError(ShotgunSDKError):
    """Raised when a codebase or graph is not found."""


class CodebaseOperationError(ShotgunSDKError):
    """Raised when a codebase operation fails."""


class InvalidPathError(ShotgunSDKError):
    """Raised when a provided path is invalid."""
