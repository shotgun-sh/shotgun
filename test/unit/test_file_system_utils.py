"""Unit tests for utils.file_system_utils module."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from shotgun.utils.file_system_utils import ensure_shotgun_directory_exists


class TestEnsureShotgunDirectoryExists:
    """Test suite for ensure_shotgun_directory_exists function."""

    def test_creates_directory_when_not_exists(self):
        """Test creating .shotgun directory when it doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("shotgun.utils.file_system_utils.Path.cwd") as mock_cwd:
                mock_cwd.return_value = Path(temp_dir)

                result = ensure_shotgun_directory_exists()

                expected_path = Path(temp_dir) / ".shotgun"
                assert result == expected_path
                assert expected_path.exists()
                assert expected_path.is_dir()

    def test_returns_existing_directory(self):
        """Test returning existing .shotgun directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Pre-create the .shotgun directory
            shotgun_dir = Path(temp_dir) / ".shotgun"
            shotgun_dir.mkdir()

            with patch("shotgun.utils.file_system_utils.Path.cwd") as mock_cwd:
                mock_cwd.return_value = Path(temp_dir)

                result = ensure_shotgun_directory_exists()

                assert result == shotgun_dir
                assert shotgun_dir.exists()
                assert shotgun_dir.is_dir()

    def test_handles_existing_file_with_same_name(self):
        """Test handling when .shotgun exists as a file (not directory)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a file named .shotgun instead of directory
            shotgun_file = Path(temp_dir) / ".shotgun"
            shotgun_file.write_text("not a directory")

            with patch("shotgun.utils.file_system_utils.Path.cwd") as mock_cwd:
                mock_cwd.return_value = Path(temp_dir)

                # This should raise an exception because mkdir can't create
                # a directory when a file with the same name exists
                with pytest.raises(FileExistsError):
                    ensure_shotgun_directory_exists()

    def test_creates_nested_in_different_working_directories(self):
        """Test creating .shotgun directory in different working directories."""
        test_dirs = []

        # Create multiple temporary directories
        for _ in range(3):
            temp_dir = tempfile.mkdtemp()
            test_dirs.append(temp_dir)

            with patch("shotgun.utils.file_system_utils.Path.cwd") as mock_cwd:
                mock_cwd.return_value = Path(temp_dir)

                result = ensure_shotgun_directory_exists()

                expected_path = Path(temp_dir) / ".shotgun"
                assert result == expected_path
                assert expected_path.exists()
                assert expected_path.is_dir()

        # Cleanup
        import shutil

        for temp_dir in test_dirs:
            shutil.rmtree(temp_dir)

    def test_logging_behavior(self):
        """Test that directory creation works properly (logging removed to avoid circular dependency)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("shotgun.utils.file_system_utils.Path.cwd") as mock_cwd:
                mock_cwd.return_value = Path(temp_dir)

                result = ensure_shotgun_directory_exists()

                expected_path = Path(temp_dir) / ".shotgun"
                assert result == expected_path
                # Note: Logger was removed from file_system_utils to avoid circular dependency
                # with logging_config, so we only test functionality, not logging

    def test_permission_error_handling(self):
        """Test handling of permission errors during directory creation."""
        with patch("shotgun.utils.file_system_utils.Path.cwd") as mock_cwd:
            mock_path = Path("/root/restricted")  # Typically restricted directory
            mock_cwd.return_value = mock_path

            # Mock mkdir to raise PermissionError
            with patch.object(
                Path, "mkdir", side_effect=PermissionError("Permission denied")
            ):
                with pytest.raises(PermissionError):
                    ensure_shotgun_directory_exists()

    def test_returns_path_object_type(self):
        """Test that function returns proper Path object."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("shotgun.utils.file_system_utils.Path.cwd") as mock_cwd:
                mock_cwd.return_value = Path(temp_dir)

                result = ensure_shotgun_directory_exists()

                assert isinstance(result, Path)
                assert result.name == ".shotgun"
                assert result.parent == Path(temp_dir)

    def test_directory_already_exists_with_content(self):
        """Test behavior when .shotgun directory already exists with content."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Pre-create .shotgun directory with some content
            shotgun_dir = Path(temp_dir) / ".shotgun"
            shotgun_dir.mkdir()

            # Add some files to the directory
            (shotgun_dir / "research.md").write_text("# Research\n\nSome content")
            (shotgun_dir / "plans.md").write_text("# Plans\n\nSome plans")

            with patch("shotgun.utils.file_system_utils.Path.cwd") as mock_cwd:
                mock_cwd.return_value = Path(temp_dir)

                result = ensure_shotgun_directory_exists()

                assert result == shotgun_dir
                # Verify existing content is preserved
                assert (shotgun_dir / "research.md").exists()
                assert (shotgun_dir / "plans.md").exists()
                assert (
                    shotgun_dir / "research.md"
                ).read_text() == "# Research\n\nSome content"

    def test_absolute_vs_relative_path_handling(self):
        """Test that function works correctly with different path types."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Test with absolute path
            with patch("shotgun.utils.file_system_utils.Path.cwd") as mock_cwd:
                mock_cwd.return_value = temp_path.resolve()  # Absolute path

                result = ensure_shotgun_directory_exists()

                expected = temp_path.resolve() / ".shotgun"
                assert result == expected
                assert result.is_absolute()
                assert result.exists()

    def test_mkdir_with_exist_ok_parameter(self):
        """Test that mkdir is called with exist_ok=True parameter."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("shotgun.utils.file_system_utils.Path.cwd") as mock_cwd:
                mock_cwd.return_value = Path(temp_dir)

                with patch.object(Path, "mkdir") as mock_mkdir:
                    result = ensure_shotgun_directory_exists()

                    expected_path = Path(temp_dir) / ".shotgun"
                    assert result == expected_path
                    # Verify mkdir was called with exist_ok=True
                    mock_mkdir.assert_called_once_with(exist_ok=True)


class TestIntegrationScenarios:
    """Integration test scenarios for file system utilities."""

    def test_multiple_calls_are_idempotent(self):
        """Test that multiple calls to ensure_shotgun_directory_exists are safe."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("shotgun.utils.file_system_utils.Path.cwd") as mock_cwd:
                mock_cwd.return_value = Path(temp_dir)

                # Call multiple times
                result1 = ensure_shotgun_directory_exists()
                result2 = ensure_shotgun_directory_exists()
                result3 = ensure_shotgun_directory_exists()

                # All calls should return the same path
                assert result1 == result2 == result3

                # Directory should exist and be the same
                expected_path = Path(temp_dir) / ".shotgun"
                assert result1 == expected_path
                assert expected_path.exists()
                assert expected_path.is_dir()

    def test_realistic_usage_scenario(self):
        """Test realistic usage scenario with file operations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("shotgun.utils.file_system_utils.Path.cwd") as mock_cwd:
                mock_cwd.return_value = Path(temp_dir)

                # Ensure directory exists
                shotgun_dir = ensure_shotgun_directory_exists()

                # Simulate typical operations that would follow
                research_file = shotgun_dir / "research.md"
                research_file.write_text("# Research Notes\n\nSome research content")

                plans_file = shotgun_dir / "plans.md"
                plans_file.write_text("# Project Plans\n\nSome planning content")

                # Verify files were created successfully
                assert research_file.exists()
                assert plans_file.exists()
                assert research_file.parent == shotgun_dir
                assert plans_file.parent == shotgun_dir

                # Call ensure_shotgun_directory_exists again - should not affect existing files
                result = ensure_shotgun_directory_exists()
                assert result == shotgun_dir
                assert research_file.exists()  # Files should still exist
                assert plans_file.exists()
