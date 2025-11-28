"""Tests for shared_specs.file_scanner module."""

from pathlib import Path

import pytest

from shotgun.shotgun_web.shared_specs.file_scanner import (
    IGNORE_PATTERNS,
    _is_in_ignored_directory,
    _should_ignore,
    get_shotgun_directory,
    scan_shotgun_directory,
)


def test_should_ignore_ds_store():
    """Test .DS_Store is ignored."""
    assert _should_ignore(Path(".DS_Store")) is True
    assert _should_ignore(Path("some/path/.DS_Store")) is True


def test_should_ignore_thumbs_db():
    """Test Thumbs.db is ignored."""
    assert _should_ignore(Path("Thumbs.db")) is True


def test_should_ignore_python_cache():
    """Test Python cache files are ignored."""
    assert _should_ignore(Path("__pycache__")) is True
    assert _should_ignore(Path("module.pyc")) is True
    assert _should_ignore(Path("module.pyo")) is True


def test_should_ignore_editor_files():
    """Test editor files are ignored."""
    assert _should_ignore(Path(".vscode")) is True
    assert _should_ignore(Path(".idea")) is True
    assert _should_ignore(Path("file.swp")) is True
    assert _should_ignore(Path("backup~")) is True
    assert _should_ignore(Path("file.bak")) is True


def test_should_not_ignore_valid_files():
    """Test valid files are not ignored."""
    assert _should_ignore(Path("research.md")) is False
    assert _should_ignore(Path("specification.md")) is False
    assert _should_ignore(Path("api.yaml")) is False
    assert _should_ignore(Path("models.py")) is False


def test_is_in_ignored_directory():
    """Test detection of files in ignored directories."""
    base = Path("/project/.shotgun")

    # Files in __pycache__ should be ignored
    assert (
        _is_in_ignored_directory(Path("/project/.shotgun/__pycache__/module.pyc"), base)
        is True
    )

    # Files in .vscode should be ignored
    assert (
        _is_in_ignored_directory(Path("/project/.shotgun/.vscode/settings.json"), base)
        is True
    )

    # Files in regular directories should not be ignored
    assert (
        _is_in_ignored_directory(Path("/project/.shotgun/contracts/api.yaml"), base)
        is False
    )


@pytest.mark.asyncio
async def test_scan_shotgun_directory_finds_files(temp_shotgun_dir: Path):
    """Test scanning finds all expected files."""
    files = await scan_shotgun_directory(temp_shotgun_dir)

    # Should find 4 files: research.md, specification.md, contracts/api.yaml, contracts/models.py
    assert len(files) == 4

    relative_paths = [f.relative_path for f in files]
    assert "research.md" in relative_paths
    assert "specification.md" in relative_paths
    assert "contracts/api.yaml" in relative_paths
    assert "contracts/models.py" in relative_paths


@pytest.mark.asyncio
async def test_scan_shotgun_directory_excludes_ignored(
    temp_shotgun_dir_with_ignored_files: Path,
):
    """Test scanning excludes ignored files and directories."""
    files = await scan_shotgun_directory(temp_shotgun_dir_with_ignored_files)

    relative_paths = [f.relative_path for f in files]

    # Should not contain any ignored files
    assert ".DS_Store" not in relative_paths
    assert "file.pyc" not in relative_paths
    assert "file.swp" not in relative_paths
    assert "backup.bak" not in relative_paths
    assert "temp~" not in relative_paths

    # Should not contain files from ignored directories
    for path in relative_paths:
        assert "__pycache__" not in path
        assert ".vscode" not in path

    # Should still contain valid files
    assert "research.md" in relative_paths
    assert "specification.md" in relative_paths


@pytest.mark.asyncio
async def test_scan_shotgun_directory_returns_sorted_paths(temp_shotgun_dir: Path):
    """Test scanning returns files sorted by relative path."""
    files = await scan_shotgun_directory(temp_shotgun_dir)

    relative_paths = [f.relative_path for f in files]

    # Paths should be sorted
    assert relative_paths == sorted(relative_paths)


@pytest.mark.asyncio
async def test_scan_shotgun_directory_includes_size(temp_shotgun_dir: Path):
    """Test scanning includes correct file sizes."""
    files = await scan_shotgun_directory(temp_shotgun_dir)

    for file in files:
        assert file.size_bytes > 0
        assert file.size_bytes == file.absolute_path.stat().st_size


@pytest.mark.asyncio
async def test_scan_shotgun_directory_includes_absolute_path(temp_shotgun_dir: Path):
    """Test scanning includes correct absolute paths."""
    files = await scan_shotgun_directory(temp_shotgun_dir)

    for file in files:
        assert file.absolute_path.is_absolute()
        assert file.absolute_path.exists()


@pytest.mark.asyncio
async def test_scan_shotgun_directory_not_found(tmp_path: Path):
    """Test scanning raises error when .shotgun/ doesn't exist."""
    with pytest.raises(FileNotFoundError, match=".shotgun/ directory not found"):
        await scan_shotgun_directory(tmp_path)


@pytest.mark.asyncio
async def test_scan_shotgun_directory_empty(tmp_path: Path):
    """Test scanning empty .shotgun/ directory returns empty list."""
    shotgun_dir = tmp_path / ".shotgun"
    shotgun_dir.mkdir()

    files = await scan_shotgun_directory(tmp_path)

    assert files == []


def test_get_shotgun_directory_with_path():
    """Test get_shotgun_directory with explicit path."""
    project_root = Path("/my/project")
    result = get_shotgun_directory(project_root)

    assert result == Path("/my/project/.shotgun")


def test_get_shotgun_directory_without_path(tmp_path: Path, monkeypatch):
    """Test get_shotgun_directory uses current directory when no path given."""
    monkeypatch.chdir(tmp_path)
    result = get_shotgun_directory()

    assert result == tmp_path / ".shotgun"


def test_ignore_patterns_list():
    """Test that IGNORE_PATTERNS contains expected patterns."""
    assert ".DS_Store" in IGNORE_PATTERNS
    assert "Thumbs.db" in IGNORE_PATTERNS
    assert "__pycache__" in IGNORE_PATTERNS
    assert "*.pyc" in IGNORE_PATTERNS
    assert ".vscode" in IGNORE_PATTERNS
    assert ".idea" in IGNORE_PATTERNS
