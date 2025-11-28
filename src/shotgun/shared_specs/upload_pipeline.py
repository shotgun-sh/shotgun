"""Upload pipeline for .shotgun/ directory to Specs API."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from shotgun.logging_config import get_logger
from shotgun.shared_specs.file_scanner import scan_shotgun_directory
from shotgun.shared_specs.hasher import calculate_sha256
from shotgun.shotgun_web.models import FileMetadata
from shotgun.shotgun_web.specs_client import SpecsClient

logger = get_logger(__name__)

# Maximum concurrent hash calculations
MAX_CONCURRENT_HASHES = 10

# Maximum concurrent file uploads
MAX_CONCURRENT_UPLOADS = 5


@dataclass
class UploadProgress:
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

    phase: Literal["scanning", "hashing", "uploading", "closing", "complete", "error"]
    current: int = 0
    total: int = 0
    current_file: str | None = None
    bytes_uploaded: int = 0
    total_bytes: int = 0
    message: str = ""


@dataclass
class UploadResult:
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


@dataclass
class _FileWithHash:
    """File metadata with computed hash."""

    metadata: FileMetadata
    content_hash: str = ""


@dataclass
class _UploadState:
    """Internal state for upload progress tracking."""

    files_uploaded: int = 0
    bytes_uploaded: int = 0
    total_bytes: int = 0
    current_file: str | None = None
    # Track completed hashes for progress
    hashes_completed: int = 0
    total_files: int = 0


async def run_upload_pipeline(
    workspace_id: str,
    spec_id: str,
    version_id: str,
    project_root: Path | None = None,
    on_progress: Callable[[UploadProgress], None] | None = None,
) -> UploadResult:
    """Run the complete upload pipeline for a spec version.

    Scans the .shotgun/ directory, calculates hashes for all files,
    uploads them to the API, and closes the version.

    Args:
        workspace_id: Workspace UUID
        spec_id: Spec UUID
        version_id: Version UUID
        project_root: Project root containing .shotgun/ directory (defaults to cwd)
        on_progress: Optional callback for progress updates

    Returns:
        UploadResult with success status and web URL or error message
    """
    if project_root is None:
        project_root = Path.cwd()

    state = _UploadState()

    def report_progress(progress: UploadProgress) -> None:
        """Report progress to callback if provided."""
        if on_progress:
            on_progress(progress)

    try:
        # Phase 1: Scan files
        report_progress(
            UploadProgress(
                phase="scanning",
                message="Scanning .shotgun/ directory...",
            )
        )

        files = await scan_shotgun_directory(project_root)
        state.total_files = len(files)

        if not files:
            report_progress(
                UploadProgress(
                    phase="complete",
                    message="No files found in .shotgun/ directory",
                )
            )
            return UploadResult(
                success=True,
                files_uploaded=0,
                total_bytes=0,
                error="No files found",
            )

        # Calculate total size
        state.total_bytes = sum(f.size_bytes for f in files)

        report_progress(
            UploadProgress(
                phase="scanning",
                total=state.total_files,
                total_bytes=state.total_bytes,
                message=f"Found {state.total_files} files ({_format_bytes(state.total_bytes)})",
            )
        )

        # Phase 2: Calculate hashes
        report_progress(
            UploadProgress(
                phase="hashing",
                current=0,
                total=state.total_files,
                message="Calculating file hashes...",
            )
        )

        files_with_hashes = await _calculate_hashes(files, state, report_progress)

        # Phase 3: Upload files
        report_progress(
            UploadProgress(
                phase="uploading",
                current=0,
                total=state.total_files,
                total_bytes=state.total_bytes,
                message="Uploading files...",
            )
        )

        client = SpecsClient()
        await _upload_files(
            client,
            workspace_id,
            spec_id,
            version_id,
            files_with_hashes,
            state,
            report_progress,
        )

        # Phase 4: Close version
        report_progress(
            UploadProgress(
                phase="closing",
                current=state.files_uploaded,
                total=state.total_files,
                bytes_uploaded=state.bytes_uploaded,
                total_bytes=state.total_bytes,
                message="Finalizing version...",
            )
        )

        close_response = await client.close_version(workspace_id, spec_id, version_id)

        # Complete
        report_progress(
            UploadProgress(
                phase="complete",
                current=state.files_uploaded,
                total=state.total_files,
                bytes_uploaded=state.bytes_uploaded,
                total_bytes=state.total_bytes,
                message="Upload complete!",
            )
        )

        return UploadResult(
            success=True,
            web_url=close_response.web_url,
            files_uploaded=state.files_uploaded,
            total_bytes=state.bytes_uploaded,
        )

    except Exception as e:
        logger.error(f"Upload pipeline failed: {e}", exc_info=True)
        report_progress(
            UploadProgress(
                phase="error",
                current=state.files_uploaded,
                total=state.total_files,
                bytes_uploaded=state.bytes_uploaded,
                total_bytes=state.total_bytes,
                message=f"Upload failed: {e}",
            )
        )
        return UploadResult(
            success=False,
            error=str(e),
            files_uploaded=state.files_uploaded,
            total_bytes=state.bytes_uploaded,
        )


async def _calculate_hashes(
    files: list[FileMetadata],
    state: _UploadState,
    report_progress: Callable[[UploadProgress], None],
) -> list[_FileWithHash]:
    """Calculate hashes for all files with progress reporting.

    Uses semaphore to limit concurrent hash operations.
    """
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_HASHES)
    files_with_hashes: list[_FileWithHash] = []
    lock = asyncio.Lock()

    async def hash_file(file_meta: FileMetadata) -> _FileWithHash:
        async with semaphore:
            content_hash = await calculate_sha256(file_meta.absolute_path)

            # Update progress
            async with lock:
                state.hashes_completed += 1
                report_progress(
                    UploadProgress(
                        phase="hashing",
                        current=state.hashes_completed,
                        total=state.total_files,
                        current_file=file_meta.relative_path,
                        message=f"Hashing {file_meta.relative_path}",
                    )
                )

            return _FileWithHash(metadata=file_meta, content_hash=content_hash)

    # Run hash calculations concurrently
    results = await asyncio.gather(*[hash_file(f) for f in files])
    files_with_hashes = list(results)

    return files_with_hashes


async def _upload_files(
    client: SpecsClient,
    workspace_id: str,
    spec_id: str,
    version_id: str,
    files: list[_FileWithHash],
    state: _UploadState,
    report_progress: Callable[[UploadProgress], None],
) -> None:
    """Upload all files with progress reporting.

    Uses semaphore to limit concurrent uploads.
    """
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_UPLOADS)
    lock = asyncio.Lock()

    async def upload_file(file: _FileWithHash) -> None:
        async with semaphore:
            # Initiate upload to get presigned URL
            response = await client.initiate_file_upload(
                workspace_id,
                spec_id,
                version_id,
                file.metadata.relative_path,
                file.metadata.size_bytes,
                file.content_hash,
            )

            # Upload to presigned URL
            await client.upload_file_to_presigned_url(
                response.upload_url,
                file.metadata.absolute_path,
            )

            # Update progress
            async with lock:
                state.files_uploaded += 1
                state.bytes_uploaded += file.metadata.size_bytes
                state.current_file = file.metadata.relative_path

                report_progress(
                    UploadProgress(
                        phase="uploading",
                        current=state.files_uploaded,
                        total=state.total_files,
                        current_file=file.metadata.relative_path,
                        bytes_uploaded=state.bytes_uploaded,
                        total_bytes=state.total_bytes,
                        message=f"Uploaded {file.metadata.relative_path}",
                    )
                )

    # Run uploads concurrently
    await asyncio.gather(*[upload_file(f) for f in files])


def _format_bytes(size: int) -> str:
    """Format bytes as human-readable string."""
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    else:
        return f"{size / (1024 * 1024 * 1024):.1f} GB"
