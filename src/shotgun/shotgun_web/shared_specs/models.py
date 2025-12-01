"""Pydantic models for the shared specs upload pipeline."""

from pydantic import BaseModel

from shotgun.shotgun_web.models import FileMetadata
from shotgun.shotgun_web.shared_specs.utils import UploadPhase


class UploadProgress(BaseModel):
    """Progress information for the upload pipeline.

    Attributes:
        phase: Current phase of the pipeline
        current: Current item number in the phase
        total: Total items in the phase
        current_file: Name of the file currently being processed
        bytes_uploaded: Total bytes uploaded so far
        total_bytes: Total bytes to upload
        message: Human-readable status message
    """

    phase: UploadPhase
    current: int = 0
    total: int = 0
    current_file: str | None = None
    bytes_uploaded: int = 0
    total_bytes: int = 0
    message: str = ""


class UploadResult(BaseModel):
    """Result of the upload pipeline.

    Attributes:
        success: Whether the upload completed successfully
        web_url: URL to view the spec version (on success)
        error: Error message (on failure)
        files_uploaded: Number of files uploaded
        total_bytes: Total bytes uploaded
    """

    success: bool
    web_url: str | None = None
    error: str | None = None
    files_uploaded: int = 0
    total_bytes: int = 0


class FileWithHash(BaseModel):
    """File metadata with computed hash."""

    metadata: FileMetadata
    content_hash: str = ""


class UploadState(BaseModel):
    """Internal state for upload progress tracking."""

    files_uploaded: int = 0
    bytes_uploaded: int = 0
    total_bytes: int = 0
    current_file: str | None = None
    hashes_completed: int = 0
    total_files: int = 0


class ScanResult(BaseModel):
    """Result of scanning .shotgun/ directory."""

    files: list[FileMetadata]
    total_files_before_filter: int
