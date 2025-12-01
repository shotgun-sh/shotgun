"""Tests for CLI spec backup module."""

import zipfile
from pathlib import Path

import pytest

from shotgun.cli.spec.backup import BACKUP_DIR, clear_shotgun_dir, create_backup


@pytest.fixture
def temp_shotgun_dir(tmp_path: Path) -> Path:
    """Create a temporary .shotgun directory with test files."""
    shotgun_dir = tmp_path / ".shotgun"
    shotgun_dir.mkdir()

    # Create some test files
    (shotgun_dir / "spec.md").write_text("# Test Spec")
    (shotgun_dir / "plan.md").write_text("# Test Plan")

    # Create a subdirectory with files
    context_dir = shotgun_dir / "context"
    context_dir.mkdir()
    (context_dir / "readme.md").write_text("# Context")

    return shotgun_dir


@pytest.fixture
def temp_backup_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a temporary backup directory and patch BACKUP_DIR."""
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr("shotgun.cli.spec.backup.BACKUP_DIR", backup_dir)
    return backup_dir


@pytest.mark.asyncio
async def test_create_backup_creates_zip(
    temp_shotgun_dir: Path, temp_backup_dir: Path
) -> None:
    """Test that create_backup creates a valid zip file."""
    backup_path = await create_backup(temp_shotgun_dir)

    assert backup_path is not None
    assert Path(backup_path).exists()
    assert backup_path.endswith(".zip")


@pytest.mark.asyncio
async def test_create_backup_includes_all_files(
    temp_shotgun_dir: Path, temp_backup_dir: Path
) -> None:
    """Test that all .shotgun/ files are included in backup."""
    backup_path = await create_backup(temp_shotgun_dir)

    assert backup_path is not None

    with zipfile.ZipFile(backup_path, "r") as zipf:
        names = zipf.namelist()
        assert "spec.md" in names
        assert "plan.md" in names
        assert "context/readme.md" in names


@pytest.mark.asyncio
async def test_create_backup_returns_none_when_dir_not_exists(
    tmp_path: Path, temp_backup_dir: Path
) -> None:
    """Test that backup returns None when .shotgun/ doesn't exist."""
    nonexistent = tmp_path / "nonexistent"
    backup_path = await create_backup(nonexistent)
    assert backup_path is None


@pytest.mark.asyncio
async def test_create_backup_returns_none_when_dir_empty(
    tmp_path: Path, temp_backup_dir: Path
) -> None:
    """Test that backup returns None when .shotgun/ is empty."""
    empty_dir = tmp_path / ".shotgun"
    empty_dir.mkdir()
    backup_path = await create_backup(empty_dir)
    assert backup_path is None


@pytest.mark.asyncio
async def test_create_backup_creates_backup_dir(
    temp_shotgun_dir: Path, temp_backup_dir: Path
) -> None:
    """Test that backup creates the backup directory if needed."""
    assert not temp_backup_dir.exists()
    await create_backup(temp_shotgun_dir)
    assert temp_backup_dir.exists()


def test_clear_shotgun_dir_removes_contents(temp_shotgun_dir: Path) -> None:
    """Test that clear_shotgun_dir removes all contents."""
    # Verify content exists
    assert (temp_shotgun_dir / "spec.md").exists()
    assert (temp_shotgun_dir / "context").exists()

    clear_shotgun_dir(temp_shotgun_dir)

    # Directory should exist but be empty
    assert temp_shotgun_dir.exists()
    assert list(temp_shotgun_dir.iterdir()) == []


def test_clear_shotgun_dir_handles_nonexistent(tmp_path: Path) -> None:
    """Test that clear_shotgun_dir handles nonexistent directory."""
    nonexistent = tmp_path / "nonexistent"
    # Should not raise
    clear_shotgun_dir(nonexistent)
