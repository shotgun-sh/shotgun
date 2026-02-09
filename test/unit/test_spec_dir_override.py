"""Unit tests for --spec-dir override functionality."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from shotgun.utils.file_system_utils import (
    ensure_shotgun_directory_exists,
    get_shotgun_base_path,
    set_spec_dir,
)


@pytest.fixture(autouse=True)
def _reset_spec_dir_override():
    """Reset the spec dir override after each test."""
    yield
    set_spec_dir(None)


def test_default_returns_cwd_shotgun():
    """Without override, get_shotgun_base_path returns .shotgun in CWD."""
    with patch("shotgun.utils.file_system_utils.Path.cwd") as mock_cwd:
        mock_cwd.return_value = Path("/fake/project")
        result = get_shotgun_base_path()
        assert result == Path("/fake/project/.shotgun")


def test_override_returns_custom_path():
    """When override is set, get_shotgun_base_path returns the custom path."""
    with tempfile.TemporaryDirectory() as temp_dir:
        custom_path = Path(temp_dir) / "my_specs"
        custom_path.mkdir()
        set_spec_dir(str(custom_path))

        result = get_shotgun_base_path()
        assert result == custom_path.resolve()


def test_override_resolves_relative_path():
    """Relative paths are resolved to absolute paths."""
    set_spec_dir("tmp/example_docs")
    result = get_shotgun_base_path()
    assert result.is_absolute()
    assert result == Path("tmp/example_docs").resolve()


def test_clear_override():
    """Setting None clears the override back to default behavior."""
    set_spec_dir("/some/custom/path")
    assert get_shotgun_base_path() == Path("/some/custom/path")

    set_spec_dir(None)
    with patch("shotgun.utils.file_system_utils.Path.cwd") as mock_cwd:
        mock_cwd.return_value = Path("/fake/project")
        result = get_shotgun_base_path()
        assert result == Path("/fake/project/.shotgun")


def test_ensure_directory_creates_custom_dir():
    """ensure_shotgun_directory_exists() works with the override."""
    with tempfile.TemporaryDirectory() as temp_dir:
        custom_path = Path(temp_dir) / "custom_specs"
        set_spec_dir(str(custom_path))

        result = ensure_shotgun_directory_exists()
        assert result == custom_path.resolve()
        assert result.exists()
        assert result.is_dir()
