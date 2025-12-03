"""Upload pipeline for .shotgun/ directory to Specs API."""

import asyncio
import time
from collections.abc import Callable
from pathlib import Path

from shotgun.logging_config import get_logger
from shotgun.posthog_telemetry import track_event
from shotgun.shotgun_web.models import FileMetadata
from shotgun.shotgun_web.shared_specs.file_scanner import (
    scan_shotgun_directory_with_counts,
)
from shotgun.shotgun_web.shared_specs.hasher import calculate_sha256
from shotgun.shotgun_web.shared_specs.models import (
    FileWithHash,
    UploadProgress,
    UploadResult,
    UploadState,
)
from shotgun.shotgun_web.shared_specs.utils import UploadPhase, format_bytes
from shotgun.shotgun_web.specs_client import SpecsClient

logger = get_logger(__name__)

# Maximum concurrent hash calculations
MAX_CONCURRENT_HASHES = 10

# Maximum concurrent file uploads
MAX_CONCURRENT_UPLOADS = 3


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

    state = UploadState()
    start_time = time.time()
    current_phase: UploadPhase = UploadPhase.CREATING
    track_event("spec_upload_started")

    def report_progress(progress: UploadProgress) -> None:
        """Report progress to callback if provided."""
        if on_progress:
            on_progress(progress)

    try:
        # Phase 1: Scan files
        current_phase = UploadPhase.SCANNING
        report_progress(
            UploadProgress(
                phase=UploadPhase.SCANNING,
                message="Scanning .shotgun/ directory...",
            )
        )

        scan_result = await scan_shotgun_directory_with_counts(project_root)
        files = scan_result.files
        state.total_files = len(files)

        if not files:
            # Distinguish between empty directory and all files filtered
            if scan_result.total_files_before_filter > 0:
                error_message = (
                    "No shareable files found. All files matched ignore patterns."
                )
            else:
                error_message = (
                    "No files to share. Add specifications to .shotgun/ first."
                )

            track_event(
                "spec_upload_failed",
                {
                    "error_type": "EmptyDirectory",
                    "phase": current_phase.value,
                    "files_uploaded": 0,
                    "bytes_uploaded": 0,
                },
            )
            report_progress(
                UploadProgress(
                    phase=UploadPhase.ERROR,
                    message=error_message,
                )
            )
            return UploadResult(
                success=False,
                files_uploaded=0,
                total_bytes=0,
                error=error_message,
            )

        # Calculate total size
        state.total_bytes = sum(f.size_bytes for f in files)

        report_progress(
            UploadProgress(
                phase=UploadPhase.SCANNING,
                total=state.total_files,
                total_bytes=state.total_bytes,
                message=f"Found {state.total_files} files ({format_bytes(state.total_bytes)})",
            )
        )

        # Phase 2: Calculate hashes
        current_phase = UploadPhase.HASHING
        report_progress(
            UploadProgress(
                phase=UploadPhase.HASHING,
                current=0,
                total=state.total_files,
                message="Calculating file hashes...",
            )
        )

        files_with_hashes = await _calculate_hashes(files, state, report_progress)

        # Phase 3: Upload files
        current_phase = UploadPhase.UPLOADING
        report_progress(
            UploadProgress(
                phase=UploadPhase.UPLOADING,
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
        current_phase = UploadPhase.CLOSING
        report_progress(
            UploadProgress(
                phase=UploadPhase.CLOSING,
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
                phase=UploadPhase.COMPLETE,
                current=state.files_uploaded,
                total=state.total_files,
                bytes_uploaded=state.bytes_uploaded,
                total_bytes=state.total_bytes,
                message="Upload complete!",
            )
        )

        # Track successful completion
        duration = time.time() - start_time
        track_event(
            "spec_upload_completed",
            {
                "file_count": state.files_uploaded,
                "total_bytes": state.bytes_uploaded,
                "duration_seconds": round(duration, 2),
            },
        )

        return UploadResult(
            success=True,
            web_url=close_response.web_url,
            files_uploaded=state.files_uploaded,
            total_bytes=state.bytes_uploaded,
        )

    except Exception as e:
        logger.error(f"Upload pipeline failed: {e}", exc_info=True)
        track_event(
            "spec_upload_failed",
            {
                "error_type": type(e).__name__,
                "phase": current_phase.value,
                "files_uploaded": state.files_uploaded,
                "bytes_uploaded": state.bytes_uploaded,
            },
        )
        report_progress(
            UploadProgress(
                phase=UploadPhase.ERROR,
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
    state: UploadState,
    report_progress: Callable[[UploadProgress], None],
) -> list[FileWithHash]:
    """Calculate hashes for all files with progress reporting.

    Uses semaphore to limit concurrent hash operations.
    """
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_HASHES)
    files_with_hashes: list[FileWithHash] = []
    lock = asyncio.Lock()

    async def hash_file(file_meta: FileMetadata) -> FileWithHash:
        async with semaphore:
            content_hash = await calculate_sha256(file_meta.absolute_path)

            # Update progress
            async with lock:
                state.hashes_completed += 1
                report_progress(
                    UploadProgress(
                        phase=UploadPhase.HASHING,
                        current=state.hashes_completed,
                        total=state.total_files,
                        current_file=file_meta.relative_path,
                        message=f"Hashing {file_meta.relative_path}",
                    )
                )

            return FileWithHash(metadata=file_meta, content_hash=content_hash)

    # Run hash calculations concurrently
    results = await asyncio.gather(*[hash_file(f) for f in files])
    files_with_hashes = list(results)

    return files_with_hashes


async def _upload_files(
    client: SpecsClient,
    workspace_id: str,
    spec_id: str,
    version_id: str,
    files: list[FileWithHash],
    state: UploadState,
    report_progress: Callable[[UploadProgress], None],
) -> None:
    """Upload all files with progress reporting.

    Uses semaphore to limit concurrent uploads.
    """
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_UPLOADS)
    lock = asyncio.Lock()

    async def upload_file(file: FileWithHash) -> None:
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
                        phase=UploadPhase.UPLOADING,
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
