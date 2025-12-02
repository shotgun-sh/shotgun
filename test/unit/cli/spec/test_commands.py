"""Tests for CLI spec commands module."""

import re
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from shotgun.cli.spec.commands import _async_pull, app
from shotgun.shotgun_web.exceptions import (
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
)
from shotgun.shotgun_web.models import SpecFileResponse, SpecVersionResponse

# Pattern to strip ANSI escape codes from output
ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    return ANSI_ESCAPE.sub("", text)


@pytest.fixture
def runner():
    """Create a CLI runner for testing."""
    return CliRunner()


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
        web_url="https://app.shotgun.sh/workspaces/workspace-789/specs/spec-456/versions/version-123",
        download_urls_expire_at=datetime(2024, 1, 1, 0, 15, tzinfo=timezone.utc),
    )


@pytest.mark.asyncio
async def test_async_pull_success(tmp_path: Path, mock_version_response):
    """Test successful spec pull."""
    shotgun_dir = tmp_path / ".shotgun"

    mock_client = AsyncMock()
    mock_client.get_version_with_files.return_value = mock_version_response

    with (
        patch("shotgun.cli.spec.commands.SpecsClient", return_value=mock_client),
        patch(
            "shotgun.cli.spec.commands.get_shotgun_base_path", return_value=shotgun_dir
        ),
        patch(
            "shotgun.cli.spec.commands.download_file_from_url",
            return_value=b"# Test Content",
        ),
    ):
        result = await _async_pull("version-123")

        # Verify files were created
        assert (shotgun_dir / "spec.md").exists()
        assert (shotgun_dir / "context" / "readme.md").exists()
        assert (shotgun_dir / "meta.json").exists()

        # Verify meta.json content
        meta_content = (shotgun_dir / "meta.json").read_text()
        assert "version-123" in meta_content
        assert "spec-456" in meta_content
        assert "Test Spec" in meta_content

        # Verify function returned success
        assert result is True


@pytest.mark.asyncio
async def test_async_pull_returns_true_on_success(
    tmp_path: Path, mock_version_response
):
    """Test _async_pull returns True on success (TUI handled by sync pull())."""
    shotgun_dir = tmp_path / ".shotgun"

    mock_client = AsyncMock()
    mock_client.get_version_with_files.return_value = mock_version_response

    with (
        patch("shotgun.cli.spec.commands.SpecsClient", return_value=mock_client),
        patch(
            "shotgun.cli.spec.commands.get_shotgun_base_path", return_value=shotgun_dir
        ),
        patch(
            "shotgun.cli.spec.commands.download_file_from_url",
            return_value=b"# Test Content",
        ),
    ):
        result = await _async_pull("version-123")

        # Verify async function returned success (sync pull() handles TUI)
        assert result is True


@pytest.mark.asyncio
async def test_async_pull_backs_up_existing_content(
    tmp_path: Path, mock_version_response
):
    """Test spec pull backs up existing .shotgun/ content."""
    shotgun_dir = tmp_path / ".shotgun"
    shotgun_dir.mkdir()
    (shotgun_dir / "old_file.md").write_text("# Old Content")

    mock_client = AsyncMock()
    mock_client.get_version_with_files.return_value = mock_version_response

    mock_backup_path = str(tmp_path / "backup.zip")

    with (
        patch("shotgun.cli.spec.commands.SpecsClient", return_value=mock_client),
        patch(
            "shotgun.cli.spec.commands.get_shotgun_base_path", return_value=shotgun_dir
        ),
        patch(
            "shotgun.cli.spec.commands.download_file_from_url",
            return_value=b"# Test Content",
        ),
        patch(
            "shotgun.cli.spec.commands.create_backup",
            return_value=mock_backup_path,
        ) as mock_backup,
        patch("shotgun.cli.spec.commands.clear_shotgun_dir") as mock_clear,
    ):
        await _async_pull("version-123")

        # Verify backup was created and directory was cleared
        mock_backup.assert_called_once_with(shotgun_dir)
        mock_clear.assert_called_once_with(shotgun_dir)


@pytest.mark.asyncio
async def test_async_pull_unauthorized_error(tmp_path: Path):
    """Test spec pull handles unauthorized error."""
    shotgun_dir = tmp_path / ".shotgun"

    mock_client = AsyncMock()
    mock_client.get_version_with_files.side_effect = UnauthorizedError(
        "Not authenticated"
    )

    with (
        patch("shotgun.cli.spec.commands.SpecsClient", return_value=mock_client),
        patch(
            "shotgun.cli.spec.commands.get_shotgun_base_path", return_value=shotgun_dir
        ),
        pytest.raises(typer.Exit) as exc_info,
    ):
        await _async_pull("version-123")

    assert exc_info.value.exit_code == 1


@pytest.mark.asyncio
async def test_async_pull_not_found_error(tmp_path: Path):
    """Test spec pull handles not found error."""
    shotgun_dir = tmp_path / ".shotgun"

    mock_client = AsyncMock()
    mock_client.get_version_with_files.side_effect = NotFoundError("Version not found")

    with (
        patch("shotgun.cli.spec.commands.SpecsClient", return_value=mock_client),
        patch(
            "shotgun.cli.spec.commands.get_shotgun_base_path", return_value=shotgun_dir
        ),
        pytest.raises(typer.Exit) as exc_info,
    ):
        await _async_pull("version-123")

    assert exc_info.value.exit_code == 1


@pytest.mark.asyncio
async def test_async_pull_forbidden_error(tmp_path: Path):
    """Test spec pull handles forbidden error."""
    shotgun_dir = tmp_path / ".shotgun"

    mock_client = AsyncMock()
    mock_client.get_version_with_files.side_effect = ForbiddenError("Access denied")

    with (
        patch("shotgun.cli.spec.commands.SpecsClient", return_value=mock_client),
        patch(
            "shotgun.cli.spec.commands.get_shotgun_base_path", return_value=shotgun_dir
        ),
        pytest.raises(typer.Exit) as exc_info,
    ):
        await _async_pull("version-123")

    assert exc_info.value.exit_code == 1


@pytest.mark.asyncio
async def test_async_pull_empty_version(tmp_path: Path):
    """Test spec pull handles version with no files."""
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

    with (
        patch("shotgun.cli.spec.commands.SpecsClient", return_value=mock_client),
        patch(
            "shotgun.cli.spec.commands.get_shotgun_base_path", return_value=shotgun_dir
        ),
        pytest.raises(typer.Exit) as exc_info,
    ):
        await _async_pull("version-123")

    assert exc_info.value.exit_code == 1


def test_pull_command_help(runner):
    """Test pull command displays help."""
    result = runner.invoke(app, ["pull", "--help"])
    output = strip_ansi(result.output)
    assert result.exit_code == 0
    assert "Pull a spec version" in output
    assert "--no-tui" in output


def test_spec_app_no_args_shows_help(runner):
    """Test spec app shows help when no args provided."""
    result = runner.invoke(app, [])
    output = strip_ansi(result.output)
    # The app is configured with no_args_is_help=True, which returns exit code 2
    assert result.exit_code == 2
    # The app shows commands when invoked with no args
    assert "pull" in output


def test_pull_command_launches_tui_by_default(runner):
    """Test pull command launches TUI by default (not --no-tui mode)."""
    with patch("shotgun.cli.spec.commands.tui_app.run") as mock_run:
        # Note: For single-command typer apps, don't include command name
        result = runner.invoke(app, ["version-123"])

    assert result.exit_code == 0
    mock_run.assert_called_once_with(pull_version_id="version-123")


def test_pull_command_no_tui_mode(runner, tmp_path, mock_version_response):
    """Test pull command with --no-tui flag runs CLI-only mode."""
    shotgun_dir = tmp_path / ".shotgun"

    mock_client = AsyncMock()
    mock_client.get_version_with_files.return_value = mock_version_response

    with (
        patch("shotgun.cli.spec.commands.SpecsClient", return_value=mock_client),
        patch(
            "shotgun.cli.spec.commands.get_shotgun_base_path", return_value=shotgun_dir
        ),
        patch(
            "shotgun.cli.spec.commands.download_file_from_url",
            return_value=b"# Test Content",
        ),
    ):
        # Note: For single-command typer apps, don't include command name
        result = runner.invoke(app, ["version-123", "--no-tui"])

    assert result.exit_code == 0
    # Verify files were created
    assert (shotgun_dir / "spec.md").exists()
    assert (shotgun_dir / "meta.json").exists()
