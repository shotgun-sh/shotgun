"""Tests for shared_specs.upload_pipeline module."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from shotgun.shotgun_web.models import (
    FileUploadResponse,
    SpecFileResponse,
    SpecVersionResponse,
    SpecVersionState,
    VersionCloseResponse,
)
from shotgun.shotgun_web.shared_specs.models import UploadProgress, UploadResult
from shotgun.shotgun_web.shared_specs.upload_pipeline import run_upload_pipeline
from shotgun.shotgun_web.shared_specs.utils import format_bytes


def test_format_bytes_bytes():
    """Test formatting bytes."""
    assert format_bytes(500) == "500 B"


def test_format_bytes_kilobytes():
    """Test formatting kilobytes."""
    assert format_bytes(1024) == "1.0 KB"
    assert format_bytes(2048) == "2.0 KB"


def test_format_bytes_megabytes():
    """Test formatting megabytes."""
    assert format_bytes(1024 * 1024) == "1.0 MB"
    assert format_bytes(5 * 1024 * 1024) == "5.0 MB"


def test_format_bytes_gigabytes():
    """Test formatting gigabytes."""
    assert format_bytes(1024 * 1024 * 1024) == "1.0 GB"


def test_upload_progress_dataclass():
    """Test UploadProgress dataclass."""
    progress = UploadProgress(
        phase="uploading",
        current=5,
        total=10,
        current_file="test.md",
        bytes_uploaded=5000,
        total_bytes=10000,
        message="Uploading test.md",
    )
    assert progress.phase == "uploading"
    assert progress.current == 5
    assert progress.total == 10
    assert progress.current_file == "test.md"


def test_upload_result_success():
    """Test UploadResult for successful upload."""
    result = UploadResult(
        success=True,
        web_url="https://shotgun.sh/specs/123",
        files_uploaded=5,
        total_bytes=10000,
    )
    assert result.success is True
    assert result.web_url == "https://shotgun.sh/specs/123"
    assert result.error is None


def test_upload_result_failure():
    """Test UploadResult for failed upload."""
    result = UploadResult(
        success=False,
        error="Network error",
        files_uploaded=2,
        total_bytes=5000,
    )
    assert result.success is False
    assert result.error == "Network error"


@pytest.fixture
def temp_shotgun_dir(tmp_path: Path) -> Path:
    """Create a temporary .shotgun directory with test files."""
    shotgun_dir = tmp_path / ".shotgun"
    shotgun_dir.mkdir()

    # Create test files
    (shotgun_dir / "research.md").write_text("# Research\n\nSome content.")
    (shotgun_dir / "specification.md").write_text("# Spec\n\nSpec content.")

    # Create a subdirectory with files
    contracts_dir = shotgun_dir / "contracts"
    contracts_dir.mkdir()
    (contracts_dir / "api.yaml").write_text("openapi: 3.0.0")

    return tmp_path


def _mock_file_upload_response(relative_path: str) -> FileUploadResponse:
    """Create a mock FileUploadResponse."""
    from datetime import datetime, timezone

    return FileUploadResponse(
        file=SpecFileResponse(
            id="file-123",
            relative_path=relative_path,
            bucket_key=f"specs/123/{relative_path}",
            size_bytes=100,
            content_hash="abc123",
            created_on=datetime.now(timezone.utc),
        ),
        upload_url="https://storage.example.com/upload",
    )


def _mock_version_close_response() -> VersionCloseResponse:
    """Create a mock VersionCloseResponse."""
    from datetime import datetime, timezone

    return VersionCloseResponse(
        version=SpecVersionResponse(
            id="version-123",
            spec_id="spec-123",
            workspace_id="ws-123",
            state=SpecVersionState.READY,
            is_latest=True,
            created_by="user-123",
            created_on=datetime.now(timezone.utc),
        ),
        web_url="https://shotgun.sh/specs/123/versions/123",
    )


@pytest.mark.asyncio
async def test_run_upload_pipeline_success(temp_shotgun_dir: Path):
    """Test successful upload pipeline run."""
    progress_events: list[UploadProgress] = []

    def on_progress(progress: UploadProgress) -> None:
        progress_events.append(progress)

    mock_client = AsyncMock()
    mock_client.initiate_file_upload = AsyncMock(
        side_effect=lambda *args, **kwargs: _mock_file_upload_response(args[3])
    )
    mock_client.upload_file_to_presigned_url = AsyncMock()
    mock_client.close_version = AsyncMock(return_value=_mock_version_close_response())

    with patch(
        "shotgun.shotgun_web.shared_specs.upload_pipeline.SpecsClient",
        return_value=mock_client,
    ):
        result = await run_upload_pipeline(
            workspace_id="ws-123",
            spec_id="spec-123",
            version_id="version-123",
            project_root=temp_shotgun_dir,
            on_progress=on_progress,
        )

    assert result.success is True
    assert result.web_url == "https://shotgun.sh/specs/123/versions/123"
    assert (
        result.files_uploaded == 3
    )  # research.md, specification.md, contracts/api.yaml
    assert result.error is None

    # Verify progress events
    phases = [p.phase for p in progress_events]
    assert "scanning" in phases
    assert "hashing" in phases
    assert "uploading" in phases
    assert "closing" in phases
    assert "complete" in phases

    # Verify client calls
    assert mock_client.initiate_file_upload.call_count == 3
    assert mock_client.upload_file_to_presigned_url.call_count == 3
    mock_client.close_version.assert_called_once_with(
        "ws-123", "spec-123", "version-123"
    )


@pytest.mark.asyncio
async def test_run_upload_pipeline_no_files(tmp_path: Path):
    """Test pipeline fails with empty .shotgun directory."""
    shotgun_dir = tmp_path / ".shotgun"
    shotgun_dir.mkdir()

    progress_events: list[UploadProgress] = []

    def on_progress(progress: UploadProgress) -> None:
        progress_events.append(progress)

    result = await run_upload_pipeline(
        workspace_id="ws-123",
        spec_id="spec-123",
        version_id="version-123",
        project_root=tmp_path,
        on_progress=on_progress,
    )

    assert result.success is False
    assert result.files_uploaded == 0
    assert "No files to share" in result.error

    # Should have error phase
    error_events = [p for p in progress_events if p.phase == "error"]
    assert len(error_events) == 1


@pytest.mark.asyncio
async def test_run_upload_pipeline_missing_directory(tmp_path: Path):
    """Test pipeline with missing .shotgun directory."""
    progress_events: list[UploadProgress] = []

    def on_progress(progress: UploadProgress) -> None:
        progress_events.append(progress)

    result = await run_upload_pipeline(
        workspace_id="ws-123",
        spec_id="spec-123",
        version_id="version-123",
        project_root=tmp_path,
        on_progress=on_progress,
    )

    assert result.success is False
    assert "not found" in result.error.lower()

    # Should have error phase
    error_events = [p for p in progress_events if p.phase == "error"]
    assert len(error_events) == 1


@pytest.mark.asyncio
async def test_run_upload_pipeline_upload_error(temp_shotgun_dir: Path):
    """Test pipeline handles upload errors gracefully."""
    mock_client = AsyncMock()
    mock_client.initiate_file_upload = AsyncMock(side_effect=Exception("Upload failed"))

    with patch(
        "shotgun.shotgun_web.shared_specs.upload_pipeline.SpecsClient",
        return_value=mock_client,
    ):
        result = await run_upload_pipeline(
            workspace_id="ws-123",
            spec_id="spec-123",
            version_id="version-123",
            project_root=temp_shotgun_dir,
        )

    assert result.success is False
    assert "Upload failed" in str(result.error)


@pytest.mark.asyncio
async def test_run_upload_pipeline_no_progress_callback(temp_shotgun_dir: Path):
    """Test pipeline works without progress callback."""
    mock_client = AsyncMock()
    mock_client.initiate_file_upload = AsyncMock(
        side_effect=lambda *args, **kwargs: _mock_file_upload_response(args[3])
    )
    mock_client.upload_file_to_presigned_url = AsyncMock()
    mock_client.close_version = AsyncMock(return_value=_mock_version_close_response())

    with patch(
        "shotgun.shotgun_web.shared_specs.upload_pipeline.SpecsClient",
        return_value=mock_client,
    ):
        # Should not raise even without callback
        result = await run_upload_pipeline(
            workspace_id="ws-123",
            spec_id="spec-123",
            version_id="version-123",
            project_root=temp_shotgun_dir,
            on_progress=None,  # No callback
        )

    assert result.success is True


@pytest.mark.asyncio
async def test_run_upload_pipeline_all_files_filtered(tmp_path: Path):
    """Test pipeline fails when all files match ignore patterns."""
    shotgun_dir = tmp_path / ".shotgun"
    shotgun_dir.mkdir()

    # Create only ignored files
    (shotgun_dir / ".DS_Store").write_text("ignored")
    pycache_dir = shotgun_dir / "__pycache__"
    pycache_dir.mkdir()
    (pycache_dir / "test.pyc").write_bytes(b"compiled")
    (shotgun_dir / "backup.bak").write_text("backup file")

    progress_events: list[UploadProgress] = []

    def on_progress(progress: UploadProgress) -> None:
        progress_events.append(progress)

    result = await run_upload_pipeline(
        workspace_id="ws-123",
        spec_id="spec-123",
        version_id="version-123",
        project_root=tmp_path,
        on_progress=on_progress,
    )

    assert result.success is False
    assert result.files_uploaded == 0
    assert "ignore patterns" in result.error

    # Should have error phase
    error_events = [p for p in progress_events if p.phase == "error"]
    assert len(error_events) == 1


@pytest.mark.asyncio
async def test_run_upload_pipeline_large_file(tmp_path: Path):
    """Test pipeline handles large files without memory exhaustion."""
    shotgun_dir = tmp_path / ".shotgun"
    shotgun_dir.mkdir()

    # Create a 50MB file (writes in chunks to avoid memory issues during test)
    large_file = shotgun_dir / "large.bin"
    chunk = b"x" * (1024 * 1024)  # 1MB chunk
    with open(large_file, "wb") as f:
        for _ in range(50):
            f.write(chunk)

    mock_client = AsyncMock()
    mock_client.initiate_file_upload = AsyncMock(
        side_effect=lambda *args, **kwargs: _mock_file_upload_response(args[3])
    )
    mock_client.upload_file_to_presigned_url = AsyncMock()
    mock_client.close_version = AsyncMock(return_value=_mock_version_close_response())

    with patch(
        "shotgun.shotgun_web.shared_specs.upload_pipeline.SpecsClient",
        return_value=mock_client,
    ):
        result = await run_upload_pipeline(
            workspace_id="ws-123",
            spec_id="spec-123",
            version_id="version-123",
            project_root=tmp_path,
        )

    assert result.success is True
    assert result.files_uploaded == 1
    # 50MB = 50 * 1024 * 1024 bytes
    assert result.total_bytes == 50 * 1024 * 1024


@pytest.mark.asyncio
async def test_run_upload_pipeline_tracks_posthog_events(temp_shotgun_dir: Path):
    """Test PostHog events are tracked during successful upload."""
    mock_client = AsyncMock()
    mock_client.initiate_file_upload = AsyncMock(
        side_effect=lambda *args, **kwargs: _mock_file_upload_response(args[3])
    )
    mock_client.upload_file_to_presigned_url = AsyncMock()
    mock_client.close_version = AsyncMock(return_value=_mock_version_close_response())

    with (
        patch(
            "shotgun.shotgun_web.shared_specs.upload_pipeline.SpecsClient",
            return_value=mock_client,
        ),
        patch(
            "shotgun.shotgun_web.shared_specs.upload_pipeline.track_event"
        ) as mock_track,
    ):
        result = await run_upload_pipeline(
            workspace_id="ws-123",
            spec_id="spec-123",
            version_id="version-123",
            project_root=temp_shotgun_dir,
        )

    assert result.success is True

    # Verify started event was tracked
    mock_track.assert_any_call("spec_upload_started")

    # Verify completed event was tracked with correct properties
    completed_calls = [
        c for c in mock_track.call_args_list if c[0][0] == "spec_upload_completed"
    ]
    assert len(completed_calls) == 1
    props = completed_calls[0][0][1]
    assert props["file_count"] == 3
    assert "total_bytes" in props
    assert "duration_seconds" in props


@pytest.mark.asyncio
async def test_run_upload_pipeline_tracks_failure_event_empty_dir(tmp_path: Path):
    """Test PostHog failure event is tracked for empty directory."""
    shotgun_dir = tmp_path / ".shotgun"
    shotgun_dir.mkdir()

    with patch(
        "shotgun.shotgun_web.shared_specs.upload_pipeline.track_event"
    ) as mock_track:
        result = await run_upload_pipeline(
            workspace_id="ws-123",
            spec_id="spec-123",
            version_id="version-123",
            project_root=tmp_path,
        )

    assert result.success is False

    # Verify started event was tracked
    mock_track.assert_any_call("spec_upload_started")

    # Verify failed event was tracked
    failed_calls = [
        c for c in mock_track.call_args_list if c[0][0] == "spec_upload_failed"
    ]
    assert len(failed_calls) == 1
    props = failed_calls[0][0][1]
    assert props["error_type"] == "EmptyDirectory"
    assert props["phase"] == "scanning"


@pytest.mark.asyncio
async def test_run_upload_pipeline_tracks_failure_event_upload_error(
    temp_shotgun_dir: Path,
):
    """Test PostHog failure event is tracked for upload errors."""
    mock_client = AsyncMock()
    mock_client.initiate_file_upload = AsyncMock(
        side_effect=RuntimeError("Network error")
    )

    with (
        patch(
            "shotgun.shotgun_web.shared_specs.upload_pipeline.SpecsClient",
            return_value=mock_client,
        ),
        patch(
            "shotgun.shotgun_web.shared_specs.upload_pipeline.track_event"
        ) as mock_track,
    ):
        result = await run_upload_pipeline(
            workspace_id="ws-123",
            spec_id="spec-123",
            version_id="version-123",
            project_root=temp_shotgun_dir,
        )

    assert result.success is False

    # Verify started event was tracked
    mock_track.assert_any_call("spec_upload_started")

    # Verify failed event was tracked
    failed_calls = [
        c for c in mock_track.call_args_list if c[0][0] == "spec_upload_failed"
    ]
    assert len(failed_calls) == 1
    props = failed_calls[0][0][1]
    assert props["error_type"] == "RuntimeError"
    assert props["phase"] == "uploading"
