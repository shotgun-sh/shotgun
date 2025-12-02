"""Tests for SpecPullService."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shotgun.cli.spec.pull_service import (
    CancelledError,
    PullProgress,
    PullResult,
    SpecPullService,
)
from shotgun.shotgun_web.models import SpecFileResponse, SpecVersionResponse


@pytest.fixture
def mock_version_response():
    """Create a mock version response with files."""
    version = SpecVersionResponse(
        id="version-123",
        spec_id="spec-456",
        workspace_id="workspace-789",
        state="ready",
        is_latest=True,
        label="v1",
        notes=None,
        created_by="user-123",
        created_by_email="user@example.com",
        created_on=datetime(2024, 1, 1, tzinfo=timezone.utc),
        file_count=2,
        total_size_bytes=1024,
    )
    files = [
        SpecFileResponse(
            id="file-1",
            relative_path="spec.md",
            bucket_key="specs/spec-456/version-123/spec.md",
            size_bytes=512,
            content_hash="a" * 64,
            content_type="text/markdown",
            created_on=datetime(2024, 1, 1, tzinfo=timezone.utc),
            download_url="https://storage.example.com/file-1",
        ),
        SpecFileResponse(
            id="file-2",
            relative_path="context/readme.md",
            bucket_key="specs/spec-456/version-123/context/readme.md",
            size_bytes=512,
            content_hash="b" * 64,
            content_type="text/markdown",
            created_on=datetime(2024, 1, 1, tzinfo=timezone.utc),
            download_url="https://storage.example.com/file-2",
        ),
    ]
    return MagicMock(
        version=version,
        spec_name="Test Spec",
        spec_id="spec-456",
        workspace_id="workspace-789",
        files=files,
        web_url="https://app.example.com/specs/spec-456",
        download_urls_expire_at=datetime(2024, 1, 1, 0, 15, tzinfo=timezone.utc),
    )


@pytest.mark.asyncio
async def test_pull_version_success(tmp_path: Path, mock_version_response):
    """Test successful spec pull."""
    shotgun_dir = tmp_path / ".shotgun"

    mock_client = AsyncMock()
    mock_client.get_version_with_files.return_value = mock_version_response

    with (
        patch(
            "shotgun.cli.spec.pull_service.SpecsClient", return_value=mock_client
        ),
        patch(
            "shotgun.cli.spec.pull_service.download_file_from_url",
            return_value=b"# Test Content",
        ),
    ):
        service = SpecPullService()
        result = await service.pull_version(
            version_id="version-123",
            shotgun_dir=shotgun_dir,
        )

    assert result.success is True
    assert result.spec_name == "Test Spec"
    assert result.file_count == 2
    assert result.web_url == "https://app.example.com/specs/spec-456"
    assert result.error is None

    # Verify files were created
    assert (shotgun_dir / "spec.md").exists()
    assert (shotgun_dir / "context" / "readme.md").exists()
    assert (shotgun_dir / "meta.json").exists()


@pytest.mark.asyncio
async def test_pull_version_with_progress_callback(
    tmp_path: Path, mock_version_response
):
    """Test progress callback is called during pull."""
    shotgun_dir = tmp_path / ".shotgun"
    progress_updates: list[PullProgress] = []

    mock_client = AsyncMock()
    mock_client.get_version_with_files.return_value = mock_version_response

    with (
        patch(
            "shotgun.cli.spec.pull_service.SpecsClient", return_value=mock_client
        ),
        patch(
            "shotgun.cli.spec.pull_service.download_file_from_url",
            return_value=b"# Test Content",
        ),
    ):
        service = SpecPullService()
        result = await service.pull_version(
            version_id="version-123",
            shotgun_dir=shotgun_dir,
            on_progress=progress_updates.append,
        )

    assert result.success is True

    # Verify progress was reported
    assert len(progress_updates) > 0

    # Check that we got expected phases
    phases = [p.phase for p in progress_updates]
    assert any("Fetching" in phase for phase in phases)
    assert any("Downloading" in phase for phase in phases)
    assert any("Finalizing" in phase for phase in phases)


@pytest.mark.asyncio
async def test_pull_version_cancellation(tmp_path: Path, mock_version_response):
    """Test pull can be cancelled."""
    shotgun_dir = tmp_path / ".shotgun"
    cancel_after = 1
    progress_count = 0

    def is_cancelled() -> bool:
        nonlocal progress_count
        progress_count += 1
        return progress_count > cancel_after

    mock_client = AsyncMock()
    mock_client.get_version_with_files.return_value = mock_version_response

    with (
        patch(
            "shotgun.cli.spec.pull_service.SpecsClient", return_value=mock_client
        ),
        patch(
            "shotgun.cli.spec.pull_service.download_file_from_url",
            return_value=b"# Test Content",
        ),
        pytest.raises(CancelledError),
    ):
        service = SpecPullService()
        await service.pull_version(
            version_id="version-123",
            shotgun_dir=shotgun_dir,
            is_cancelled=is_cancelled,
        )


@pytest.mark.asyncio
async def test_pull_version_empty_files(tmp_path: Path):
    """Test pull handles version with no files."""
    shotgun_dir = tmp_path / ".shotgun"

    mock_response = MagicMock(
        version=MagicMock(id="version-123", is_latest=True),
        spec_name="Empty Spec",
        spec_id="spec-456",
        workspace_id="workspace-789",
        files=[],
    )

    mock_client = AsyncMock()
    mock_client.get_version_with_files.return_value = mock_response

    with patch(
        "shotgun.cli.spec.pull_service.SpecsClient", return_value=mock_client
    ):
        service = SpecPullService()
        result = await service.pull_version(
            version_id="version-123",
            shotgun_dir=shotgun_dir,
        )

    assert result.success is False
    assert result.error == "No files in this version."
    assert result.spec_name == "Empty Spec"


@pytest.mark.asyncio
async def test_pull_version_backs_up_existing(tmp_path: Path, mock_version_response):
    """Test pull backs up existing .shotgun/ content."""
    shotgun_dir = tmp_path / ".shotgun"
    shotgun_dir.mkdir()
    (shotgun_dir / "old_file.md").write_text("# Old Content")

    mock_client = AsyncMock()
    mock_client.get_version_with_files.return_value = mock_version_response

    mock_backup_path = str(tmp_path / "backup.zip")

    with (
        patch(
            "shotgun.cli.spec.pull_service.SpecsClient", return_value=mock_client
        ),
        patch(
            "shotgun.cli.spec.pull_service.download_file_from_url",
            return_value=b"# Test Content",
        ),
        patch(
            "shotgun.cli.spec.pull_service.create_backup",
            return_value=mock_backup_path,
        ) as mock_backup,
        patch("shotgun.cli.spec.pull_service.clear_shotgun_dir") as mock_clear,
    ):
        service = SpecPullService()
        result = await service.pull_version(
            version_id="version-123",
            shotgun_dir=shotgun_dir,
        )

    assert result.success is True
    assert result.backup_path == mock_backup_path
    mock_backup.assert_called_once_with(shotgun_dir)
    mock_clear.assert_called_once_with(shotgun_dir)


@pytest.mark.asyncio
async def test_pull_version_skips_file_without_url(tmp_path: Path):
    """Test pull skips files without download URLs."""
    shotgun_dir = tmp_path / ".shotgun"

    version = SpecVersionResponse(
        id="version-123",
        spec_id="spec-456",
        workspace_id="workspace-789",
        state="ready",
        is_latest=True,
        label="v1",
        notes=None,
        created_by="user-123",
        created_by_email="user@example.com",
        created_on=datetime(2024, 1, 1, tzinfo=timezone.utc),
        file_count=2,
        total_size_bytes=1024,
    )
    files = [
        SpecFileResponse(
            id="file-1",
            relative_path="spec.md",
            bucket_key="specs/spec-456/version-123/spec.md",
            size_bytes=512,
            content_hash="a" * 64,
            content_type="text/markdown",
            created_on=datetime(2024, 1, 1, tzinfo=timezone.utc),
            download_url="https://storage.example.com/file-1",
        ),
        SpecFileResponse(
            id="file-2",
            relative_path="missing.md",
            bucket_key="specs/spec-456/version-123/missing.md",
            size_bytes=512,
            content_hash="b" * 64,
            content_type="text/markdown",
            created_on=datetime(2024, 1, 1, tzinfo=timezone.utc),
            download_url=None,  # No URL
        ),
    ]
    mock_response = MagicMock(
        version=version,
        spec_name="Test Spec",
        spec_id="spec-456",
        workspace_id="workspace-789",
        files=files,
        web_url="https://app.example.com/specs/spec-456",
    )

    mock_client = AsyncMock()
    mock_client.get_version_with_files.return_value = mock_response

    with (
        patch(
            "shotgun.cli.spec.pull_service.SpecsClient", return_value=mock_client
        ),
        patch(
            "shotgun.cli.spec.pull_service.download_file_from_url",
            return_value=b"# Test Content",
        ) as mock_download,
    ):
        service = SpecPullService()
        result = await service.pull_version(
            version_id="version-123",
            shotgun_dir=shotgun_dir,
        )

    assert result.success is True
    # Only 1 file should be downloaded (the one with URL)
    mock_download.assert_called_once()
    assert (shotgun_dir / "spec.md").exists()
    assert not (shotgun_dir / "missing.md").exists()
