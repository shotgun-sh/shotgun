"""Unit tests for path-based persistence utilities."""

import hashlib
import platform
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from shotgun.codebase.models import CodebaseGraph, GraphStatus
from shotgun.codebase.persistence import (
    _generate_graph_id_from_path,
    create_graph_for_path,
    lookup_graph_for_path,
    resolve_canonical_path,
)


def test_resolve_canonical_path_with_relative_path():
    """Test resolving a relative path to canonical form."""
    # Create a temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create a subdirectory
        subdir = temp_path / "test_project"
        subdir.mkdir()

        # Test with relative path
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(temp_path)
            canonical = resolve_canonical_path("./test_project")

            # Should resolve to absolute path
            assert Path(canonical).is_absolute()
            assert canonical == str(subdir.resolve())
        finally:
            os.chdir(original_cwd)


def test_resolve_canonical_path_with_absolute_path():
    """Test resolving an absolute path (should remain the same when canonical)."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        canonical = resolve_canonical_path(temp_path)

        # Should be the same as the resolved path
        assert canonical == str(temp_path.resolve())


def test_resolve_canonical_path_with_symlink():
    """Test resolving a path through symlinks."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create a real directory
        real_dir = temp_path / "real_project"
        real_dir.mkdir()

        # Create a symlink to it
        symlink = temp_path / "symlink_to_project"

        # Skip test on Windows if symlinks are not supported
        try:
            symlink.symlink_to(real_dir)
        except OSError:
            pytest.skip("Symlinks not supported on this platform/filesystem")

        # Resolve through the symlink
        canonical = resolve_canonical_path(symlink)

        # Should resolve to the real directory
        assert canonical == str(real_dir.resolve())


def test_resolve_canonical_path_with_parent_references():
    """Test resolving paths with .. (parent directory) references."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create nested directories
        subdir1 = temp_path / "dir1"
        subdir2 = temp_path / "dir2"
        subdir1.mkdir()
        subdir2.mkdir()

        # Create path with parent references
        complex_path = subdir1 / ".." / "dir2"
        canonical = resolve_canonical_path(complex_path)

        # Should resolve to dir2
        assert canonical == str(subdir2.resolve())


def test_resolve_canonical_path_with_path_object():
    """Test that resolve_canonical_path works with Path objects."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        canonical = resolve_canonical_path(temp_path)

        assert canonical == str(temp_path.resolve())
        assert isinstance(canonical, str)


def test_resolve_canonical_path_normalizes_separators():
    """Test that path separators are normalized to platform standard."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create a subdirectory
        subdir = temp_path / "test_dir"
        subdir.mkdir()

        canonical = resolve_canonical_path(subdir)

        # Should use platform-appropriate separators
        if platform.system() == "Windows":
            assert "\\" in canonical or "/" in canonical
        else:
            assert "/" in canonical


def test_resolve_canonical_path_handles_nonexistent_path():
    """Test resolving a path that doesn't exist (should still work)."""
    # Path.resolve() can handle non-existent paths in most Python versions
    nonexistent = "/tmp/this_path_definitely_does_not_exist_12345"
    canonical = resolve_canonical_path(nonexistent)

    # Should still return a canonical form (even if path doesn't exist)
    assert Path(canonical).is_absolute()


def test_resolve_canonical_path_with_case_sensitivity():
    """Test that path resolution handles case sensitivity appropriately."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create a directory with specific case
        subdir = temp_path / "MyProject"
        subdir.mkdir()

        # On case-insensitive systems (like macOS default, Windows),
        # different case should resolve to same path
        canonical1 = resolve_canonical_path(subdir)
        canonical2 = resolve_canonical_path(str(subdir).lower())

        # Both should resolve (though result depends on filesystem)
        assert Path(canonical1).is_absolute()
        assert Path(canonical2).is_absolute()


@pytest.mark.parametrize(
    "path_style,expected_absolute",
    [
        (".", True),
        ("..", True),
        ("./relative/path", True),
        ("../relative/path", True),
    ],
)
def test_resolve_canonical_path_parametrized(path_style, expected_absolute):
    """Parametrized test for various path styles."""
    with tempfile.TemporaryDirectory() as temp_dir:
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(temp_dir)
            canonical = resolve_canonical_path(path_style)
            assert Path(canonical).is_absolute() == expected_absolute
        finally:
            os.chdir(original_cwd)


def test_generate_graph_id_from_path_is_deterministic():
    """Test that graph ID generation is deterministic for the same path."""
    path = "/home/user/my-project"

    id1 = _generate_graph_id_from_path(path)
    id2 = _generate_graph_id_from_path(path)

    assert id1 == id2


def test_generate_graph_id_from_path_length():
    """Test that generated graph IDs are 12 characters long."""
    path = "/home/user/my-project"
    graph_id = _generate_graph_id_from_path(path)

    assert len(graph_id) == 12


def test_generate_graph_id_from_path_differs_for_different_paths():
    """Test that different paths generate different graph IDs."""
    path1 = "/home/user/project1"
    path2 = "/home/user/project2"

    id1 = _generate_graph_id_from_path(path1)
    id2 = _generate_graph_id_from_path(path2)

    assert id1 != id2


def test_generate_graph_id_from_path_uses_sha256():
    """Test that graph ID is derived from SHA256 hash."""
    path = "/home/user/my-project"
    expected_hash = hashlib.sha256(path.encode()).hexdigest()[:12]

    graph_id = _generate_graph_id_from_path(path)

    assert graph_id == expected_hash


@pytest.mark.asyncio
async def test_lookup_graph_for_path_returns_none_when_not_found():
    """Test that lookup returns None when no graph exists for the path."""
    canonical_path = "/home/user/my-project"

    # Mock manager
    mock_manager = Mock()
    mock_manager.get_graph = AsyncMock(return_value=None)

    result = await lookup_graph_for_path(canonical_path, mock_manager)

    assert result is None
    # Verify manager was called with correct graph_id
    expected_graph_id = _generate_graph_id_from_path(canonical_path)
    mock_manager.get_graph.assert_called_once_with(expected_graph_id)


@pytest.mark.asyncio
async def test_lookup_graph_for_path_returns_graph_when_found():
    """Test that lookup returns the graph when it exists."""
    canonical_path = "/home/user/my-project"

    # Create a mock graph
    mock_graph = CodebaseGraph(
        graph_id="abc123def456",
        repo_path=canonical_path,
        graph_path="/storage/abc123def456.kuzu",
        name="My Project",
        created_at=1234567890.0,
        updated_at=1234567890.0,
        status=GraphStatus.READY,
    )

    # Mock manager
    mock_manager = Mock()
    mock_manager.get_graph = AsyncMock(return_value=mock_graph)

    result = await lookup_graph_for_path(canonical_path, mock_manager)

    assert result is not None
    assert result.graph_id == mock_graph.graph_id
    assert result.repo_path == canonical_path


@pytest.mark.asyncio
async def test_lookup_graph_for_path_uses_correct_graph_id():
    """Test that lookup generates and uses the correct deterministic graph ID."""
    canonical_path = "/home/user/my-project"
    expected_graph_id = _generate_graph_id_from_path(canonical_path)

    # Mock manager
    mock_manager = Mock()
    mock_manager.get_graph = AsyncMock(return_value=None)

    await lookup_graph_for_path(canonical_path, mock_manager)

    # Verify the correct graph ID was used
    mock_manager.get_graph.assert_called_once_with(expected_graph_id)


@pytest.mark.asyncio
async def test_create_graph_for_path_creates_new_graph():
    """Test that create_graph_for_path creates a new graph."""
    with tempfile.TemporaryDirectory() as temp_dir:
        canonical_path = temp_dir

        # Mock graph to be returned
        mock_graph = CodebaseGraph(
            graph_id="abc123def456",
            repo_path=canonical_path,
            graph_path="/storage/abc123def456.kuzu",
            name="test_dir",
            created_at=1234567890.0,
            updated_at=1234567890.0,
            status=GraphStatus.READY,
        )

        # Mock manager
        mock_manager = Mock()
        mock_manager.get_graph = AsyncMock(return_value=None)  # No existing graph
        mock_manager.build_graph = AsyncMock(return_value=mock_graph)

        result = await create_graph_for_path(canonical_path, mock_manager)

        assert result is not None
        assert result.graph_id == mock_graph.graph_id
        # Verify build_graph was called
        mock_manager.build_graph.assert_called_once()


@pytest.mark.asyncio
async def test_create_graph_for_path_with_custom_name():
    """Test creating a graph with a custom name."""
    with tempfile.TemporaryDirectory() as temp_dir:
        canonical_path = temp_dir
        custom_name = "My Custom Project"

        # Mock graph
        mock_graph = CodebaseGraph(
            graph_id="abc123def456",
            repo_path=canonical_path,
            graph_path="/storage/abc123def456.kuzu",
            name=custom_name,
            created_at=1234567890.0,
            updated_at=1234567890.0,
            status=GraphStatus.READY,
        )

        # Mock manager
        mock_manager = Mock()
        mock_manager.get_graph = AsyncMock(return_value=None)
        mock_manager.build_graph = AsyncMock(return_value=mock_graph)

        result = await create_graph_for_path(
            canonical_path, mock_manager, name=custom_name
        )

        # Verify name was passed to build_graph
        call_args = mock_manager.build_graph.call_args
        assert call_args[1]["name"] == custom_name


@pytest.mark.asyncio
async def test_create_graph_for_path_replaces_existing_graph():
    """Test that creating a graph for an existing path replaces the old graph."""
    with tempfile.TemporaryDirectory() as temp_dir:
        canonical_path = temp_dir

        # Mock existing graph
        existing_graph = CodebaseGraph(
            graph_id="old123graph456",
            repo_path=canonical_path,
            graph_path="/storage/old123graph456.kuzu",
            name="Old Graph",
            created_at=1234567890.0,
            updated_at=1234567890.0,
            status=GraphStatus.READY,
        )

        # Mock new graph
        new_graph = CodebaseGraph(
            graph_id="new123graph456",
            repo_path=canonical_path,
            graph_path="/storage/new123graph456.kuzu",
            name="New Graph",
            created_at=1234567900.0,
            updated_at=1234567900.0,
            status=GraphStatus.READY,
        )

        # Mock manager
        mock_manager = Mock()
        mock_manager.get_graph = AsyncMock(return_value=existing_graph)
        mock_manager.delete_graph = AsyncMock()
        mock_manager.build_graph = AsyncMock(return_value=new_graph)

        result = await create_graph_for_path(canonical_path, mock_manager)

        # Verify old graph was deleted
        mock_manager.delete_graph.assert_called_once()
        # Verify new graph was created
        mock_manager.build_graph.assert_called_once()
        assert result.graph_id == new_graph.graph_id


@pytest.mark.asyncio
async def test_create_graph_for_path_with_languages():
    """Test creating a graph with specific languages."""
    with tempfile.TemporaryDirectory() as temp_dir:
        canonical_path = temp_dir
        languages = ["python", "javascript"]

        mock_graph = CodebaseGraph(
            graph_id="abc123def456",
            repo_path=canonical_path,
            graph_path="/storage/abc123def456.kuzu",
            name="test_dir",
            created_at=1234567890.0,
            updated_at=1234567890.0,
            status=GraphStatus.READY,
        )

        mock_manager = Mock()
        mock_manager.get_graph = AsyncMock(return_value=None)
        mock_manager.build_graph = AsyncMock(return_value=mock_graph)

        await create_graph_for_path(
            canonical_path, mock_manager, languages=languages
        )

        # Verify languages were passed
        call_args = mock_manager.build_graph.call_args
        assert call_args[1]["languages"] == languages


@pytest.mark.asyncio
async def test_create_graph_for_path_with_exclude_patterns():
    """Test creating a graph with exclude patterns."""
    with tempfile.TemporaryDirectory() as temp_dir:
        canonical_path = temp_dir
        exclude_patterns = ["*.pyc", "__pycache__"]

        mock_graph = CodebaseGraph(
            graph_id="abc123def456",
            repo_path=canonical_path,
            graph_path="/storage/abc123def456.kuzu",
            name="test_dir",
            created_at=1234567890.0,
            updated_at=1234567890.0,
            status=GraphStatus.READY,
        )

        mock_manager = Mock()
        mock_manager.get_graph = AsyncMock(return_value=None)
        mock_manager.build_graph = AsyncMock(return_value=mock_graph)

        await create_graph_for_path(
            canonical_path, mock_manager, exclude_patterns=exclude_patterns
        )

        # Verify exclude_patterns were passed
        call_args = mock_manager.build_graph.call_args
        assert call_args[1]["exclude_patterns"] == exclude_patterns


@pytest.mark.asyncio
async def test_create_graph_for_path_raises_error_for_nonexistent_path():
    """Test that create_graph_for_path raises ValueError for non-existent paths."""
    nonexistent_path = "/tmp/this_path_does_not_exist_xyz123"
    mock_manager = Mock()

    with pytest.raises(ValueError, match="Path does not exist"):
        await create_graph_for_path(nonexistent_path, mock_manager)


@pytest.mark.asyncio
async def test_create_graph_for_path_raises_error_for_file_path():
    """Test that create_graph_for_path raises ValueError when path is a file."""
    with tempfile.NamedTemporaryFile() as temp_file:
        mock_manager = Mock()

        with pytest.raises(ValueError, match="Path is not a directory"):
            await create_graph_for_path(temp_file.name, mock_manager)


@pytest.mark.asyncio
async def test_create_graph_for_path_uses_directory_name_as_default():
    """Test that directory name is used as default graph name."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        canonical_path = str(temp_path)

        mock_graph = CodebaseGraph(
            graph_id="abc123def456",
            repo_path=canonical_path,
            graph_path="/storage/abc123def456.kuzu",
            name=temp_path.name,
            created_at=1234567890.0,
            updated_at=1234567890.0,
            status=GraphStatus.READY,
        )

        mock_manager = Mock()
        mock_manager.get_graph = AsyncMock(return_value=None)
        mock_manager.build_graph = AsyncMock(return_value=mock_graph)

        await create_graph_for_path(canonical_path, mock_manager)

        # Verify name defaults to directory name
        call_args = mock_manager.build_graph.call_args
        assert call_args[1]["name"] == temp_path.name


@pytest.mark.asyncio
async def test_create_graph_for_path_with_progress_callback():
    """Test creating a graph with a progress callback."""
    with tempfile.TemporaryDirectory() as temp_dir:
        canonical_path = temp_dir
        mock_callback = Mock()

        mock_graph = CodebaseGraph(
            graph_id="abc123def456",
            repo_path=canonical_path,
            graph_path="/storage/abc123def456.kuzu",
            name="test_dir",
            created_at=1234567890.0,
            updated_at=1234567890.0,
            status=GraphStatus.READY,
        )

        mock_manager = Mock()
        mock_manager.get_graph = AsyncMock(return_value=None)
        mock_manager.build_graph = AsyncMock(return_value=mock_graph)

        await create_graph_for_path(
            canonical_path, mock_manager, progress_callback=mock_callback
        )

        # Verify callback was passed
        call_args = mock_manager.build_graph.call_args
        assert call_args[1]["progress_callback"] == mock_callback


# Stage 5: Error Handling Tests


@pytest.mark.asyncio
async def test_lookup_graph_for_path_handles_storage_error():
    """Test that lookup_graph_for_path handles storage errors gracefully (Stage 5)."""
    canonical_path = "/home/user/my-project"

    # Mock manager that raises an exception
    mock_manager = Mock()
    mock_manager.get_graph = AsyncMock(side_effect=Exception("Database connection failed"))

    # Should return None instead of raising
    result = await lookup_graph_for_path(canonical_path, mock_manager)

    assert result is None
    # Verify manager was called
    mock_manager.get_graph.assert_called_once()


@pytest.mark.asyncio
async def test_lookup_graph_for_path_handles_permission_error():
    """Test that lookup handles permission errors gracefully (Stage 5)."""
    canonical_path = "/home/user/my-project"

    # Mock manager that raises permission error
    mock_manager = Mock()
    mock_manager.get_graph = AsyncMock(side_effect=PermissionError("Access denied"))

    # Should return None and log warning
    result = await lookup_graph_for_path(canonical_path, mock_manager)

    assert result is None


@pytest.mark.asyncio
async def test_lookup_graph_for_path_handles_corruption_error():
    """Test that lookup handles database corruption errors gracefully (Stage 5)."""
    canonical_path = "/home/user/my-project"

    # Mock manager that raises corruption error
    mock_manager = Mock()
    mock_manager.get_graph = AsyncMock(
        side_effect=RuntimeError("Database file corrupted")
    )

    # Should return None, allowing fallback to creating new graph
    result = await lookup_graph_for_path(canonical_path, mock_manager)

    assert result is None


def test_resolve_canonical_path_handles_symlink_loop():
    """Test that resolve_canonical_path handles symlink loops gracefully (Stage 5)."""
    # Create a path that would cause infinite symlink recursion
    # Python's Path.resolve() should handle this, but let's verify our wrapper does too

    with patch("pathlib.Path.resolve") as mock_resolve:
        # Simulate symlink loop error
        mock_resolve.side_effect = OSError("Too many levels of symbolic links")

        # Should fall back to absolute path without raising
        result = resolve_canonical_path("/some/path/with/loop")

        # Should still return a valid absolute path
        assert Path(result).is_absolute()


def test_resolve_canonical_path_handles_permission_denied():
    """Test that resolve_canonical_path handles permission errors (Stage 5)."""
    with patch("pathlib.Path.resolve") as mock_resolve:
        # Simulate permission error
        mock_resolve.side_effect = PermissionError("Permission denied")

        # Should fall back to absolute path
        result = resolve_canonical_path("/restricted/path")

        # Should still return a path (fallback behavior)
        assert Path(result).is_absolute()
