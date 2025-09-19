"""Exception classes for the artifact system."""


class ArtifactError(Exception):
    """Base exception for all artifact-related errors."""


class ArtifactNotFoundError(ArtifactError):
    """Raised when an artifact is not found."""

    def __init__(self, artifact_id: str, agent_mode: str | None = None) -> None:
        if agent_mode:
            message = f"Artifact '{artifact_id}' not found in agent mode '{agent_mode}'"
        else:
            message = f"Artifact '{artifact_id}' not found"
        super().__init__(message)
        self.artifact_id = artifact_id
        self.agent_mode = agent_mode


class SectionNotFoundError(ArtifactError):
    """Raised when a section is not found within an artifact."""

    def __init__(self, section_identifier: str | int, artifact_id: str) -> None:
        message = (
            f"Section '{section_identifier}' not found in artifact '{artifact_id}'"
        )
        super().__init__(message)
        self.section_identifier = section_identifier
        self.artifact_id = artifact_id


class SectionAlreadyExistsError(ArtifactError):
    """Raised when trying to create a section that already exists."""

    def __init__(self, section_identifier: str | int, artifact_id: str) -> None:
        message = (
            f"Section '{section_identifier}' already exists in artifact '{artifact_id}'"
        )
        super().__init__(message)
        self.section_identifier = section_identifier
        self.artifact_id = artifact_id


class ArtifactAlreadyExistsError(ArtifactError):
    """Raised when trying to create an artifact that already exists."""

    def __init__(self, artifact_id: str, agent_mode: str) -> None:
        message = (
            f"Artifact '{artifact_id}' already exists in agent mode '{agent_mode}'"
        )
        super().__init__(message)
        self.artifact_id = artifact_id
        self.agent_mode = agent_mode


class InvalidArtifactPathError(ArtifactError):
    """Raised when an artifact path is invalid or outside allowed directories."""

    def __init__(self, path: str, reason: str | None = None) -> None:
        message = f"Invalid artifact path: {path}"
        if reason:
            message += f" - {reason}"
        super().__init__(message)
        self.path = path
        self.reason = reason


class ArtifactFileSystemError(ArtifactError):
    """Raised when file system operations fail."""

    def __init__(self, operation: str, path: str, reason: str) -> None:
        message = f"File system error during {operation} on '{path}': {reason}"
        super().__init__(message)
        self.operation = operation
        self.path = path
        self.reason = reason


class ArtifactValidationError(ArtifactError):
    """Raised when artifact data validation fails."""

    def __init__(self, message: str, field: str | None = None) -> None:
        if field:
            message = f"Validation error for field '{field}': {message}"
        else:
            message = f"Validation error: {message}"
        super().__init__(message)
        self.field = field
