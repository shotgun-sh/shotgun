"""Unit tests for agents.tools.file_management module."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from shotgun.agents.tools.file_management import (
    _validate_shotgun_path,
    append_file,
    read_file,
    write_file,
)


class TestGetShotgunBasePath:
    """Test suite for get_shotgun_base_path function."""

    def test_returns_shotgun_directory_in_cwd(self):
        """Test that it returns .shotgun directory in current working directory."""
        with patch("shotgun.utils.file_system_utils.Path") as mock_path:
            mock_cwd = MagicMock()
            mock_path.cwd.return_value = mock_cwd

            # Import from the new location
            from shotgun.utils.file_system_utils import get_shotgun_base_path

            result = get_shotgun_base_path()

            mock_path.cwd.assert_called_once()
            mock_cwd.__truediv__.assert_called_once_with(".shotgun")
            assert result == mock_cwd.__truediv__.return_value


class TestValidateShotgunPath:
    """Test suite for _validate_shotgun_path function."""

    def test_valid_relative_path(self):
        """Test validation of valid relative path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "shotgun.agents.tools.file_management.get_shotgun_base_path"
            ) as mock_base:
                shotgun_dir = Path(temp_dir) / ".shotgun"
                shotgun_dir.mkdir()
                mock_base.return_value = shotgun_dir

                result = _validate_shotgun_path("test.md")

                expected = (shotgun_dir / "test.md").resolve()
                assert result == expected

    def test_valid_nested_path(self):
        """Test validation of valid nested path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "shotgun.agents.tools.file_management.get_shotgun_base_path"
            ) as mock_base:
                shotgun_dir = Path(temp_dir) / ".shotgun"
                shotgun_dir.mkdir()
                mock_base.return_value = shotgun_dir

                result = _validate_shotgun_path("subdir/test.md")

                expected = (shotgun_dir / "subdir" / "test.md").resolve()
                assert result == expected

    def test_path_traversal_attack_blocked(self):
        """Test that path traversal attacks are blocked."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "shotgun.agents.tools.file_management.get_shotgun_base_path"
            ) as mock_base:
                shotgun_dir = Path(temp_dir) / ".shotgun"
                shotgun_dir.mkdir()
                mock_base.return_value = shotgun_dir

                with pytest.raises(
                    ValueError, match="Access denied.*outside .shotgun directory"
                ):
                    _validate_shotgun_path("../../../etc/passwd")

    def test_absolute_path_blocked(self):
        """Test that absolute paths are blocked."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "shotgun.agents.tools.file_management.get_shotgun_base_path"
            ) as mock_base:
                shotgun_dir = Path(temp_dir) / ".shotgun"
                shotgun_dir.mkdir()
                mock_base.return_value = shotgun_dir

                with pytest.raises(
                    ValueError, match="Access denied.*outside .shotgun directory"
                ):
                    _validate_shotgun_path("/etc/passwd")

    def test_symlink_escape_blocked(self):
        """Test that symlink escapes are blocked."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "shotgun.agents.tools.file_management.get_shotgun_base_path"
            ) as mock_base:
                shotgun_dir = Path(temp_dir) / ".shotgun"
                shotgun_dir.mkdir()
                mock_base.return_value = shotgun_dir

                # Create a symlink that tries to escape
                escape_link = shotgun_dir / "escape"
                try:
                    escape_link.symlink_to(Path(temp_dir).parent)
                    with pytest.raises(
                        ValueError, match="Access denied.*outside .shotgun directory"
                    ):
                        _validate_shotgun_path("escape/sensitive.txt")
                except OSError:
                    # Symlink creation failed (Windows/permissions), skip this test
                    pytest.skip("Symlink creation not supported on this system")


class TestReadFile:
    """Test suite for read_file function."""

    @pytest.mark.asyncio
    async def test_successful_read(self):
        """Test successful file reading."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "shotgun.agents.tools.file_management.get_shotgun_base_path"
            ) as mock_base:
                shotgun_dir = Path(temp_dir) / ".shotgun"
                shotgun_dir.mkdir()
                mock_base.return_value = shotgun_dir

                # Create test file
                test_file = shotgun_dir / "test.md"
                test_content = "# Test Content\n\nThis is a test."
                test_file.write_text(test_content, encoding="utf-8")

                # Create mock context
                mock_ctx = MagicMock()
                mock_ctx.deps = MagicMock()

                result = await read_file(mock_ctx, "test.md")

                assert result == test_content

    @pytest.mark.asyncio
    async def test_file_not_found(self):
        """Test handling of non-existent file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "shotgun.agents.tools.file_management.get_shotgun_base_path"
            ) as mock_base:
                shotgun_dir = Path(temp_dir) / ".shotgun"
                shotgun_dir.mkdir()
                mock_base.return_value = shotgun_dir

                # Create mock context
                mock_ctx = MagicMock()
                mock_ctx.deps = MagicMock()

                result = await read_file(mock_ctx, "nonexistent.md")

                assert "File not found: nonexistent.md" in result

    @pytest.mark.asyncio
    async def test_path_validation_error(self):
        """Test handling of path validation errors."""
        with patch(
            "shotgun.agents.tools.file_management._validate_shotgun_path"
        ) as mock_validate:
            mock_validate.side_effect = ValueError("Access denied")

            # Create mock context
            mock_ctx = MagicMock()
            mock_ctx.deps = MagicMock()

            result = await read_file(mock_ctx, "../bad/path.md")

            assert "Error reading file" in result
            assert "Access denied" in result

    @pytest.mark.asyncio
    async def test_permission_error_handling(self):
        """Test handling of permission errors."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "shotgun.agents.tools.file_management.get_shotgun_base_path"
            ) as mock_base:
                shotgun_dir = Path(temp_dir) / ".shotgun"
                shotgun_dir.mkdir()
                mock_base.return_value = shotgun_dir

                # Create file and make it unreadable
                test_file = shotgun_dir / "protected.md"
                test_file.write_text("secret", encoding="utf-8")

                # Mock read_text to raise PermissionError
                with patch.object(
                    Path, "read_text", side_effect=PermissionError("Permission denied")
                ):
                    # Create mock context
                    mock_ctx = MagicMock()
                    mock_ctx.deps = MagicMock()

                    result = await read_file(mock_ctx, "protected.md")

                    assert "Error reading file" in result
                    assert "Permission denied" in result


class TestWriteFile:
    """Test suite for write_file function."""

    @pytest.mark.asyncio
    async def test_successful_write_mode_w(self):
        """Test successful file writing in write mode."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "shotgun.agents.tools.file_management.get_shotgun_base_path"
            ) as mock_base:
                shotgun_dir = Path(temp_dir) / ".shotgun"
                shotgun_dir.mkdir()
                mock_base.return_value = shotgun_dir

                # Create mock context with file tracker
                mock_ctx = MagicMock()
                mock_tracker = MagicMock()
                mock_ctx.deps.file_tracker = mock_tracker

                test_content = "# New Content\n\nThis is new."
                result = await write_file(mock_ctx, "new.md", test_content, mode="w")

                assert "Successfully wrote 27 characters to new.md" in result

                # Verify file was created
                test_file = shotgun_dir / "new.md"
                assert test_file.exists()
                assert test_file.read_text(encoding="utf-8") == test_content

                # Verify tracker was called
                mock_tracker.add_operation.assert_called_once()

    @pytest.mark.asyncio
    async def test_successful_write_mode_a(self):
        """Test successful file writing in append mode."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "shotgun.agents.tools.file_management.get_shotgun_base_path"
            ) as mock_base:
                shotgun_dir = Path(temp_dir) / ".shotgun"
                shotgun_dir.mkdir()
                mock_base.return_value = shotgun_dir

                # Create initial file
                test_file = shotgun_dir / "append.md"
                initial_content = "Initial content\n"
                test_file.write_text(initial_content, encoding="utf-8")

                # Create mock context with file tracker
                mock_ctx = MagicMock()
                mock_tracker = MagicMock()
                mock_ctx.deps.file_tracker = mock_tracker

                # Append content
                append_content = "Appended content"
                result = await write_file(
                    mock_ctx, "append.md", append_content, mode="a"
                )

                assert "Successfully appended 16 characters to append.md" in result

                # Verify content was appended
                final_content = test_file.read_text(encoding="utf-8")
                assert final_content == initial_content + append_content

                # Verify tracker was called for update
                mock_tracker.add_operation.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalid_mode(self):
        """Test handling of invalid write mode."""
        # Create mock context
        mock_ctx = MagicMock()
        mock_ctx.deps.file_tracker = MagicMock()

        with pytest.raises(
            ValueError, match="Invalid mode 'x'. Use 'w' for write or 'a' for append"
        ):
            await write_file(mock_ctx, "test.md", "content", mode="x")

    @pytest.mark.asyncio
    async def test_creates_parent_directories(self):
        """Test that parent directories are created."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "shotgun.agents.tools.file_management.get_shotgun_base_path"
            ) as mock_base:
                shotgun_dir = Path(temp_dir) / ".shotgun"
                shotgun_dir.mkdir()
                mock_base.return_value = shotgun_dir

                # Create mock context
                mock_ctx = MagicMock()
                mock_ctx.deps.file_tracker = MagicMock()

                result = await write_file(mock_ctx, "subdir/nested/test.md", "content")

                assert "Successfully wrote" in result

                # Verify nested directories were created
                nested_file = shotgun_dir / "subdir" / "nested" / "test.md"
                assert nested_file.exists()
                assert nested_file.read_text(encoding="utf-8") == "content"

    @pytest.mark.asyncio
    async def test_path_validation_error_in_write(self):
        """Test handling of path validation errors in write."""
        with patch(
            "shotgun.agents.tools.file_management._validate_shotgun_path"
        ) as mock_validate:
            mock_validate.side_effect = ValueError("Access denied")

            # Create mock context
            mock_ctx = MagicMock()
            mock_ctx.deps.file_tracker = MagicMock()

            result = await write_file(mock_ctx, "../bad/path.md", "content")

            assert "Error writing file" in result
            assert "Access denied" in result

    @pytest.mark.asyncio
    async def test_write_permission_error(self):
        """Test handling of write permission errors."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "shotgun.agents.tools.file_management.get_shotgun_base_path"
            ) as mock_base:
                shotgun_dir = Path(temp_dir) / ".shotgun"
                shotgun_dir.mkdir()
                mock_base.return_value = shotgun_dir

                # Mock write_text to raise PermissionError
                with patch.object(
                    Path, "write_text", side_effect=PermissionError("Permission denied")
                ):
                    # Create mock context
                    mock_ctx = MagicMock()
                    mock_ctx.deps.file_tracker = MagicMock()

                    result = await write_file(mock_ctx, "protected.md", "content")

                    assert "Error writing file" in result
                    assert "Permission denied" in result

    @pytest.mark.asyncio
    async def test_overwrite_existing_file(self):
        """Test overwriting an existing file in write mode."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "shotgun.agents.tools.file_management.get_shotgun_base_path"
            ) as mock_base:
                shotgun_dir = Path(temp_dir) / ".shotgun"
                shotgun_dir.mkdir()
                mock_base.return_value = shotgun_dir

                # Create initial file
                test_file = shotgun_dir / "overwrite.md"
                test_file.write_text("original content", encoding="utf-8")

                # Create mock context
                mock_ctx = MagicMock()
                mock_ctx.deps.file_tracker = MagicMock()

                # Overwrite with new content
                new_content = "new content"
                result = await write_file(
                    mock_ctx, "overwrite.md", new_content, mode="w"
                )

                assert "Successfully wrote" in result
                assert test_file.read_text(encoding="utf-8") == new_content


class TestAppendFile:
    """Test suite for append_file function."""

    @pytest.mark.asyncio
    async def test_append_file_delegates_to_write_file(self):
        """Test that append_file delegates to write_file with mode='a'."""
        with patch("shotgun.agents.tools.file_management.write_file") as mock_write:
            # Create async mock return value
            async def mock_write_async(*args, **kwargs):
                return "Success message"

            mock_write.side_effect = mock_write_async

            # Create mock context
            mock_ctx = MagicMock()
            mock_ctx.deps.file_tracker = MagicMock()

            result = await append_file(mock_ctx, "test.md", "content")

            mock_write.assert_called_once_with(mock_ctx, "test.md", "content", mode="a")
            assert result == "Success message"

    @pytest.mark.asyncio
    async def test_append_to_existing_file(self):
        """Test appending to an existing file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "shotgun.agents.tools.file_management.get_shotgun_base_path"
            ) as mock_base:
                shotgun_dir = Path(temp_dir) / ".shotgun"
                shotgun_dir.mkdir()
                mock_base.return_value = shotgun_dir

                # Create initial file
                test_file = shotgun_dir / "append_test.md"
                initial_content = "Line 1\n"
                test_file.write_text(initial_content, encoding="utf-8")

                # Create mock context
                mock_ctx = MagicMock()
                mock_ctx.deps.file_tracker = MagicMock()

                # Append new content
                append_content = "Line 2\n"
                result = await append_file(mock_ctx, "append_test.md", append_content)

                assert "Successfully appended" in result
                assert (
                    test_file.read_text(encoding="utf-8")
                    == initial_content + append_content
                )

    @pytest.mark.asyncio
    async def test_append_creates_new_file(self):
        """Test that append creates new file if it doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "shotgun.agents.tools.file_management.get_shotgun_base_path"
            ) as mock_base:
                shotgun_dir = Path(temp_dir) / ".shotgun"
                shotgun_dir.mkdir()
                mock_base.return_value = shotgun_dir

                # Create mock context
                mock_ctx = MagicMock()
                mock_ctx.deps.file_tracker = MagicMock()

                content = "New file content\n"
                result = await append_file(mock_ctx, "new_append.md", content)

                assert "Successfully appended" in result

                # Verify file was created
                test_file = shotgun_dir / "new_append.md"
                assert test_file.exists()
                assert test_file.read_text(encoding="utf-8") == content


class TestIntegrationScenarios:
    """Integration test scenarios for file management operations."""

    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """Test complete read-write-append workflow."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "shotgun.agents.tools.file_management.get_shotgun_base_path"
            ) as mock_base:
                shotgun_dir = Path(temp_dir) / ".shotgun"
                shotgun_dir.mkdir()
                mock_base.return_value = shotgun_dir

                # Create mock context
                mock_ctx = MagicMock()
                mock_ctx.deps.file_tracker = MagicMock()

                filename = "workflow.md"

                # 1. Write initial content
                initial_content = "# Workflow Test\n\nInitial content.\n"
                write_result = await write_file(mock_ctx, filename, initial_content)
                assert "Successfully wrote" in write_result

                # 2. Read the content
                read_result = await read_file(mock_ctx, filename)
                assert read_result == initial_content

                # 3. Append more content
                append_content = "\nAppended content.\n"
                append_result = await append_file(mock_ctx, filename, append_content)
                assert "Successfully appended" in append_result

                # 4. Read final content
                final_content = await read_file(mock_ctx, filename)
                assert final_content == initial_content + append_content

                # 5. Overwrite with new content
                new_content = "# New Content\n\nCompletely replaced.\n"
                overwrite_result = await write_file(
                    mock_ctx, filename, new_content, mode="w"
                )
                assert "Successfully wrote" in overwrite_result

                # 6. Verify overwrite
                final_read = await read_file(mock_ctx, filename)
                assert final_read == new_content

    @pytest.mark.asyncio
    async def test_security_boundary_enforcement(self):
        """Test that security boundaries are consistently enforced."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "shotgun.agents.tools.file_management.get_shotgun_base_path"
            ) as mock_base:
                shotgun_dir = Path(temp_dir) / ".shotgun"
                shotgun_dir.mkdir()
                mock_base.return_value = shotgun_dir

                # Create mock context
                mock_ctx = MagicMock()
                mock_ctx.deps.file_tracker = MagicMock()

                malicious_paths = [
                    "../../../etc/passwd",
                    "/etc/passwd",
                    "~/../../etc/passwd",
                ]

                for malicious_path in malicious_paths:
                    # All operations should fail with security error
                    read_result = await read_file(mock_ctx, malicious_path)
                    assert "Error reading file" in read_result

                    write_result = await write_file(
                        mock_ctx, malicious_path, "malicious"
                    )
                    assert "Error writing file" in write_result

                    append_result = await append_file(
                        mock_ctx, malicious_path, "malicious"
                    )
                    assert "Error writing file" in append_result
