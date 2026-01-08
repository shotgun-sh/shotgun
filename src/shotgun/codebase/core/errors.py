"""Error classification for Kuzu database operations.

This module provides error classification for Kuzu database errors,
allowing the application to distinguish between different failure modes
(lock contention, corruption, permissions, etc.) and handle each appropriately.
"""

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel


class KuzuErrorType(StrEnum):
    """Classification of Kuzu database errors."""

    LOCKED = "locked"  # Another process has DB open
    CORRUPTION = "corruption"  # Database file is invalid/corrupted
    PERMISSION = "permission"  # Permission denied (transient)
    MISSING = "missing"  # File not found
    SCHEMA = "schema"  # Table doesn't exist (incomplete build)
    TIMEOUT = "timeout"  # Operation timed out
    UNKNOWN = "unknown"  # Unrecognized error


def classify_kuzu_error(exception: Exception) -> KuzuErrorType:
    """Classify a Kuzu RuntimeError by its message pattern.

    Note: Kuzu only throws generic RuntimeError exceptions with no error codes
    or custom exception types. String matching on the error message is the only
    way to distinguish between different failure modes.

    Args:
        exception: The exception to classify

    Returns:
        KuzuErrorType indicating the category of error
    """
    error_str = str(exception)

    # Lock contention - another process has the database open
    if "Could not set lock" in error_str:
        return KuzuErrorType.LOCKED

    # True corruption - database file is invalid
    if "Unable to open database" in error_str:
        return KuzuErrorType.CORRUPTION
    if "Reading past the end of the file" in error_str:
        return KuzuErrorType.CORRUPTION
    if "not a valid" in error_str.lower() and "database" in error_str.lower():
        return KuzuErrorType.CORRUPTION

    # C++ internal errors - likely corruption
    if "unordered_map" in error_str:
        return KuzuErrorType.CORRUPTION
    if "key not found" in error_str.lower():
        return KuzuErrorType.CORRUPTION
    if "std::exception" in error_str:
        return KuzuErrorType.CORRUPTION

    # Permission errors - transient, may resolve on retry
    if "Permission denied" in error_str:
        return KuzuErrorType.PERMISSION

    # Missing file - nothing to delete
    if "No such file or directory" in error_str:
        return KuzuErrorType.MISSING

    # Schema errors - incomplete build, table doesn't exist
    if "Table" in error_str and "does not exist" in error_str:
        return KuzuErrorType.SCHEMA
    if "Binder exception" in error_str and "does not exist" in error_str:
        return KuzuErrorType.SCHEMA

    return KuzuErrorType.UNKNOWN


class DatabaseIssue(BaseModel):
    """Structured information about a database issue.

    Attributes:
        graph_id: The ID of the affected graph
        graph_path: Path to the database file
        error_type: Classification of the error
        message: Human-readable error message
    """

    model_config = {"arbitrary_types_allowed": True}

    graph_id: str
    graph_path: Path
    error_type: KuzuErrorType
    message: str


class KuzuDatabaseError(Exception):
    """Base exception for Kuzu database errors with classification."""

    def __init__(
        self, message: str, graph_id: str, graph_path: str, error_type: KuzuErrorType
    ) -> None:
        super().__init__(message)
        self.graph_id = graph_id
        self.graph_path = graph_path
        self.error_type = error_type


class DatabaseLockedError(KuzuDatabaseError):
    """Raised when the database is locked by another process."""

    def __init__(self, graph_id: str, graph_path: str) -> None:
        super().__init__(
            f"Database '{graph_id}' is locked by another process. "
            "Only one shotgun instance can access a codebase at a time.",
            graph_id=graph_id,
            graph_path=graph_path,
            error_type=KuzuErrorType.LOCKED,
        )


class DatabaseCorruptedError(KuzuDatabaseError):
    """Raised when the database is corrupted."""

    def __init__(self, graph_id: str, graph_path: str, details: str = "") -> None:
        message = f"Database '{graph_id}' is corrupted"
        if details:
            message += f": {details}"
        super().__init__(
            message,
            graph_id=graph_id,
            graph_path=graph_path,
            error_type=KuzuErrorType.CORRUPTION,
        )


class DatabaseSchemaError(KuzuDatabaseError):
    """Raised when the database schema is incomplete (interrupted build)."""

    def __init__(self, graph_id: str, graph_path: str) -> None:
        super().__init__(
            f"Database '{graph_id}' has incomplete schema (build was interrupted)",
            graph_id=graph_id,
            graph_path=graph_path,
            error_type=KuzuErrorType.SCHEMA,
        )


class DatabaseTimeoutError(KuzuDatabaseError):
    """Raised when database operation times out."""

    def __init__(self, graph_id: str, graph_path: str, timeout_seconds: float) -> None:
        super().__init__(
            f"Database '{graph_id}' operation timed out after {timeout_seconds}s. "
            "This can happen with large codebases.",
            graph_id=graph_id,
            graph_path=graph_path,
            error_type=KuzuErrorType.TIMEOUT,
        )
        self.timeout_seconds = timeout_seconds
