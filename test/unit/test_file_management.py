"""Unit tests for agents.tools.file_management module."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from shotgun.agents.tools.file_management import (
    _validate_shotgun_path,
    append_file,
    delete_file,
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
    async def test_read_pdf_returns_file_request_instruction(self):
        """Test that reading a PDF returns instructions to use file_requests."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "shotgun.agents.tools.file_management.get_shotgun_base_path"
            ) as mock_base:
                shotgun_dir = Path(temp_dir) / ".shotgun"
                shotgun_dir.mkdir()
                mock_base.return_value = shotgun_dir

                # Create test PDF file (just binary content for testing)
                test_file = shotgun_dir / "document.pdf"
                test_file.write_bytes(b"%PDF-1.4 fake pdf content")

                # Create mock context
                mock_ctx = MagicMock()
                mock_ctx.deps = MagicMock()

                result = await read_file(mock_ctx, "document.pdf")

                assert "binary file" in result
                assert "file_requests" in result
                assert str(test_file) in result

    @pytest.mark.asyncio
    async def test_read_image_returns_file_request_instruction(self):
        """Test that reading an image returns instructions to use file_requests."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "shotgun.agents.tools.file_management.get_shotgun_base_path"
            ) as mock_base:
                shotgun_dir = Path(temp_dir) / ".shotgun"
                shotgun_dir.mkdir()
                mock_base.return_value = shotgun_dir

                # Create test image file (just binary content for testing)
                test_file = shotgun_dir / "image.png"
                test_file.write_bytes(b"\x89PNG\r\n\x1a\n fake png content")

                # Create mock context
                mock_ctx = MagicMock()
                mock_ctx.deps = MagicMock()

                result = await read_file(mock_ctx, "image.png")

                assert "binary file" in result
                assert ".png" in result
                assert "file_requests" in result
                assert str(test_file) in result

    @pytest.mark.asyncio
    async def test_read_all_supported_binary_extensions(self):
        """Test that all supported binary extensions are handled."""
        from shotgun.agents.tools.file_management import BINARY_EXTENSIONS

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

                for ext in BINARY_EXTENSIONS:
                    # Create test file
                    test_file = shotgun_dir / f"test{ext}"
                    test_file.write_bytes(b"binary content")

                    result = await read_file(mock_ctx, f"test{ext}")

                    assert "binary file" in result, f"Failed for extension {ext}"
                    assert "file_requests" in result, f"Failed for extension {ext}"

    @pytest.mark.asyncio
    async def test_permission_error_handling(self):
        """Test handling of permission errors."""
        from unittest.mock import AsyncMock

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

                # Mock aiofiles.open to raise PermissionError
                mock_file = AsyncMock()
                mock_file.__aenter__ = AsyncMock(
                    side_effect=PermissionError("Permission denied")
                )

                with patch("aiofiles.open", return_value=mock_file):
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
        from unittest.mock import AsyncMock

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "shotgun.agents.tools.file_management.get_shotgun_base_path"
            ) as mock_base:
                shotgun_dir = Path(temp_dir) / ".shotgun"
                shotgun_dir.mkdir()
                mock_base.return_value = shotgun_dir

                # Mock aiofiles.open to raise PermissionError
                mock_file = AsyncMock()
                mock_file.__aenter__ = AsyncMock(
                    side_effect=PermissionError("Permission denied")
                )

                with patch("aiofiles.open", return_value=mock_file):
                    # Create mock context
                    mock_ctx = MagicMock()
                    mock_ctx.deps.file_tracker = MagicMock()
                    mock_ctx.deps.agent_mode = None

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


@pytest.mark.asyncio
async def test_delete_file_successful():
    """Test successful file deletion."""
    with tempfile.TemporaryDirectory() as temp_dir:
        with patch(
            "shotgun.agents.tools.file_management.get_shotgun_base_path"
        ) as mock_base:
            shotgun_dir = Path(temp_dir) / ".shotgun"
            shotgun_dir.mkdir()
            mock_base.return_value = shotgun_dir

            # Create test file
            test_file = shotgun_dir / "to_delete.md"
            test_file.write_text("content to delete", encoding="utf-8")
            assert test_file.exists()

            # Create mock context with file tracker
            mock_ctx = MagicMock()
            mock_tracker = MagicMock()
            mock_ctx.deps.file_tracker = mock_tracker
            mock_ctx.deps.agent_mode = None

            result = await delete_file(mock_ctx, "to_delete.md")

            assert result == "Successfully deleted to_delete.md"
            assert not test_file.exists()

            # Verify tracker was called with DELETED operation
            mock_tracker.add_operation.assert_called_once()
            call_args = mock_tracker.add_operation.call_args
            assert call_args[0][1].value == "deleted"


@pytest.mark.asyncio
async def test_delete_file_not_found():
    """Test deletion of non-existent file."""
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
            mock_ctx.deps.agent_mode = None

            result = await delete_file(mock_ctx, "nonexistent.md")

            assert "File not found: nonexistent.md" in result


@pytest.mark.asyncio
async def test_delete_file_path_traversal_blocked():
    """Test that path traversal attacks are blocked for delete."""
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
            mock_ctx.deps.agent_mode = None

            result = await delete_file(mock_ctx, "../../../etc/passwd")

            assert "Error deleting file" in result
            assert "Access denied" in result


@pytest.mark.asyncio
async def test_delete_file_agent_permission_denied():
    """Test that agent cannot delete files outside their scope."""
    from shotgun.agents.models import AgentType

    with tempfile.TemporaryDirectory() as temp_dir:
        with patch(
            "shotgun.agents.tools.file_management.get_shotgun_base_path"
        ) as mock_base:
            shotgun_dir = Path(temp_dir) / ".shotgun"
            shotgun_dir.mkdir()
            mock_base.return_value = shotgun_dir

            # Create a file that research agent shouldn't be able to delete
            plan_file = shotgun_dir / "plan.md"
            plan_file.write_text("plan content", encoding="utf-8")

            # Create mock context with RESEARCH agent mode
            mock_ctx = MagicMock()
            mock_ctx.deps.file_tracker = MagicMock()
            mock_ctx.deps.agent_mode = AgentType.RESEARCH

            result = await delete_file(mock_ctx, "plan.md")

            assert "Error deleting file" in result
            # File should still exist
            assert plan_file.exists()


@pytest.mark.asyncio
async def test_delete_file_agent_permission_allowed():
    """Test that agent can delete files within their scope."""
    from shotgun.agents.models import AgentType

    with tempfile.TemporaryDirectory() as temp_dir:
        with patch(
            "shotgun.agents.tools.file_management.get_shotgun_base_path"
        ) as mock_base:
            shotgun_dir = Path(temp_dir) / ".shotgun"
            shotgun_dir.mkdir()
            mock_base.return_value = shotgun_dir

            # Create a file that research agent can delete
            research_file = shotgun_dir / "research.md"
            research_file.write_text("research content", encoding="utf-8")

            # Create mock context with RESEARCH agent mode
            mock_ctx = MagicMock()
            mock_tracker = MagicMock()
            mock_ctx.deps.file_tracker = mock_tracker
            mock_ctx.deps.agent_mode = AgentType.RESEARCH

            result = await delete_file(mock_ctx, "research.md")

            assert result == "Successfully deleted research.md"
            assert not research_file.exists()


@pytest.mark.asyncio
async def test_delete_file_nested_in_allowed_directory():
    """Test deletion of file in nested directory within agent scope."""
    from shotgun.agents.models import AgentType

    with tempfile.TemporaryDirectory() as temp_dir:
        with patch(
            "shotgun.agents.tools.file_management.get_shotgun_base_path"
        ) as mock_base:
            shotgun_dir = Path(temp_dir) / ".shotgun"
            shotgun_dir.mkdir()
            mock_base.return_value = shotgun_dir

            # Create nested file in research directory
            research_dir = shotgun_dir / "research"
            research_dir.mkdir()
            nested_file = research_dir / "notes.md"
            nested_file.write_text("nested notes", encoding="utf-8")

            # Create mock context with RESEARCH agent mode
            mock_ctx = MagicMock()
            mock_tracker = MagicMock()
            mock_ctx.deps.file_tracker = mock_tracker
            mock_ctx.deps.agent_mode = AgentType.RESEARCH

            result = await delete_file(mock_ctx, "research/notes.md")

            assert result == "Successfully deleted research/notes.md"
            assert not nested_file.exists()


@pytest.mark.asyncio
async def test_delete_file_export_agent_cannot_delete_protected():
    """Test that export agent cannot delete protected files."""
    from shotgun.agents.models import AgentType

    with tempfile.TemporaryDirectory() as temp_dir:
        with patch(
            "shotgun.agents.tools.file_management.get_shotgun_base_path"
        ) as mock_base:
            shotgun_dir = Path(temp_dir) / ".shotgun"
            shotgun_dir.mkdir()
            mock_base.return_value = shotgun_dir

            # Create protected file
            protected_file = shotgun_dir / "research.md"
            protected_file.write_text("protected content", encoding="utf-8")

            # Create mock context with EXPORT agent mode
            mock_ctx = MagicMock()
            mock_ctx.deps.file_tracker = MagicMock()
            mock_ctx.deps.agent_mode = AgentType.EXPORT

            result = await delete_file(mock_ctx, "research.md")

            assert "Error deleting file" in result
            assert "protected file" in result.lower()
            # File should still exist
            assert protected_file.exists()


@pytest.mark.asyncio
async def test_delete_file_export_agent_can_delete_unprotected():
    """Test that export agent can delete non-protected files."""
    from shotgun.agents.models import AgentType

    with tempfile.TemporaryDirectory() as temp_dir:
        with patch(
            "shotgun.agents.tools.file_management.get_shotgun_base_path"
        ) as mock_base:
            shotgun_dir = Path(temp_dir) / ".shotgun"
            shotgun_dir.mkdir()
            mock_base.return_value = shotgun_dir

            # Create non-protected file
            other_file = shotgun_dir / "output.txt"
            other_file.write_text("output content", encoding="utf-8")

            # Create mock context with EXPORT agent mode
            mock_ctx = MagicMock()
            mock_tracker = MagicMock()
            mock_ctx.deps.file_tracker = mock_tracker
            mock_ctx.deps.agent_mode = AgentType.EXPORT

            result = await delete_file(mock_ctx, "output.txt")

            assert result == "Successfully deleted output.txt"
            assert not other_file.exists()
