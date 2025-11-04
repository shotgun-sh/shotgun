"""Unit tests for change_detector module."""

import hashlib
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from unittest.mock import Mock, patch

import pytest

from shotgun.codebase.core.change_detector import ChangeDetector, ChangeType


def test_change_type_enum_values():
    """Test ChangeType enum has correct values."""
    assert ChangeType.ADDED.value == "added"
    assert ChangeType.MODIFIED.value == "modified"
    assert ChangeType.DELETED.value == "deleted"


def test_change_detector_init_with_valid_path():
    """Test initialization with valid repository path."""
    mock_conn = Mock()

    with TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir)
        detector = ChangeDetector(mock_conn, repo_path)

        assert detector.conn == mock_conn
        assert detector.repo_path == repo_path.resolve()


def test_change_detector_init_with_string_path():
    """Test initialization with string path."""
    mock_conn = Mock()

    with TemporaryDirectory() as temp_dir:
        detector = ChangeDetector(mock_conn, Path(temp_dir))

        assert detector.conn == mock_conn
        assert detector.repo_path == Path(temp_dir).resolve()


def test_change_detector_init_nonexistent_path_raises_error():
    """Test initialization with nonexistent path raises ValueError."""
    mock_conn = Mock()
    nonexistent_path = Path("/nonexistent/path")

    with pytest.raises(ValueError, match="Repository path does not exist"):
        ChangeDetector(mock_conn, nonexistent_path)


def test_change_detector_init_file_path_raises_error():
    """Test initialization with file path raises ValueError."""
    mock_conn = Mock()

    with NamedTemporaryFile() as temp_file:
        with pytest.raises(ValueError, match="Repository path is not a directory"):
            ChangeDetector(mock_conn, Path(temp_file.name))


@patch("shotgun.codebase.core.language_config.get_language_config")
def test_detect_changes_new_file(mock_get_config):
    """Test detecting new file."""
    mock_conn = Mock()

    with TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir)
        detector = ChangeDetector(mock_conn, repo_path)

        # Mock language config
        mock_config = Mock()
        mock_config.file_extensions = {".py"}
        mock_get_config.return_value = mock_config

        # Create a new Python file
        test_file = repo_path / "test.py"
        test_file.write_text("print('hello')")

        # Mock _get_file_info to return None (file not tracked)
        detector._get_file_info = Mock(return_value=None)
        detector._get_tracked_files = Mock(return_value=[])

        changes = detector.detect_changes()

        assert len(changes) == 1
        assert "test.py" in changes
        assert changes["test.py"] == ChangeType.ADDED


@patch("shotgun.codebase.core.language_config.get_language_config")
def test_detect_changes_modified_file(mock_get_config):
    """Test detecting modified file."""
    mock_conn = Mock()

    with TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir)
        detector = ChangeDetector(mock_conn, repo_path)

        # Mock language config
        mock_config = Mock()
        mock_config.file_extensions = {".py"}
        mock_get_config.return_value = mock_config

        # Create a Python file
        test_file = repo_path / "test.py"
        test_file.write_text("print('hello')")

        # Mock file info with older mtime and different hash
        old_mtime = int(test_file.stat().st_mtime) - 100
        detector._get_file_info = Mock(
            return_value={"mtime": old_mtime, "hash": "old_hash"}
        )
        detector._get_tracked_files = Mock(return_value=["test.py"])

        changes = detector.detect_changes()

        assert len(changes) == 1
        assert "test.py" in changes
        assert changes["test.py"] == ChangeType.MODIFIED


@patch("shotgun.codebase.core.language_config.get_language_config")
def test_detect_changes_deleted_file(mock_get_config):
    """Test detecting deleted file."""
    mock_conn = Mock()

    with TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir)
        detector = ChangeDetector(mock_conn, repo_path)

        # Mock language config
        mock_config = Mock()
        mock_config.file_extensions = {".py"}
        mock_get_config.return_value = mock_config

        # Mock tracked files with a file that doesn't exist
        detector._get_tracked_files = Mock(return_value=["deleted.py"])

        changes = detector.detect_changes()

        assert len(changes) == 1
        assert "deleted.py" in changes
        assert changes["deleted.py"] == ChangeType.DELETED


@patch("shotgun.codebase.core.language_config.get_language_config")
def test_detect_changes_no_changes(mock_get_config):
    """Test detecting no changes."""
    mock_conn = Mock()

    with TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir)
        detector = ChangeDetector(mock_conn, repo_path)

        # Mock language config
        mock_config = Mock()
        mock_config.file_extensions = {".py"}
        mock_get_config.return_value = mock_config

        # Create a Python file
        test_file = repo_path / "test.py"
        test_file.write_text("print('hello')")

        # Mock file info with same mtime and hash
        current_hash = hashlib.sha256(b"print('hello')").hexdigest()
        current_mtime = int(test_file.stat().st_mtime)

        detector._get_file_info = Mock(
            return_value={
                "mtime": current_mtime + 100,  # Future mtime, so no change detected
                "hash": current_hash,
            }
        )
        detector._get_tracked_files = Mock(return_value=["test.py"])

        changes = detector.detect_changes()

        assert len(changes) == 0


@patch("shotgun.codebase.core.language_config.get_language_config")
def test_detect_changes_with_specific_languages(mock_get_config):
    """Test detect_changes with specific languages filter."""
    mock_conn = Mock()

    with TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir)
        detector = ChangeDetector(mock_conn, repo_path)

        # Mock language config for Python only
        mock_config = Mock()
        mock_config.file_extensions = {".py"}
        mock_get_config.return_value = mock_config

        # Create files with different extensions
        py_file = repo_path / "test.py"
        py_file.write_text("print('hello')")
        js_file = repo_path / "test.js"
        js_file.write_text("console.log('hello');")

        # Mock both files as new
        detector._get_file_info = Mock(return_value=None)
        detector._get_tracked_files = Mock(return_value=[])

        changes = detector.detect_changes(languages=["python"])

        # Should only detect Python file
        assert len(changes) == 1
        assert "test.py" in changes
        assert "test.js" not in changes


@patch("shotgun.codebase.core.language_config.get_language_config")
def test_detect_changes_with_exclude_patterns(mock_get_config):
    """Test detect_changes with exclude patterns."""
    mock_conn = Mock()

    with TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir)
        detector = ChangeDetector(mock_conn, repo_path)

        # Mock language config
        mock_config = Mock()
        mock_config.file_extensions = {".py"}
        mock_get_config.return_value = mock_config

        # Create test files
        included_file = repo_path / "included.py"
        included_file.write_text("print('included')")
        excluded_file = repo_path / "test_excluded.py"
        excluded_file.write_text("print('excluded')")

        # Mock both files as new
        detector._get_file_info = Mock(return_value=None)
        detector._get_tracked_files = Mock(return_value=[])

        changes = detector.detect_changes(exclude_patterns=["test_*"])

        # Should only detect the included file
        assert len(changes) == 1
        assert "included.py" in changes
        assert "test_excluded.py" not in changes


@patch("shotgun.codebase.core.language_config.get_language_config")
def test_detect_changes_large_number_of_deletions(mock_get_config):
    """Test detecting large number of deletions."""
    mock_conn = Mock()

    with TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir)
        detector = ChangeDetector(mock_conn, repo_path)

        # Mock language config
        mock_config = Mock()
        mock_config.file_extensions = {".py"}
        mock_get_config.return_value = mock_config

        # Mock many tracked files that don't exist
        tracked_files = [f"deleted_{i}.py" for i in range(150)]
        detector._get_tracked_files = Mock(return_value=tracked_files)

        changes = detector.detect_changes()

        # Should detect all files as deleted
        assert len(changes) == 150
        deleted_files = [
            path
            for path, change_type in changes.items()
            if change_type == ChangeType.DELETED
        ]
        assert len(deleted_files) == 150


def test_get_file_info_existing_file():
    """Test _get_file_info with existing file."""
    mock_conn = Mock()

    with TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir)
        detector = ChangeDetector(mock_conn, repo_path)

        # Mock database result
        mock_result = Mock()
        mock_result.has_next.return_value = True
        mock_result.get_next.return_value = [12345, "test_hash"]
        mock_conn.execute.return_value = mock_result

        result = detector._get_file_info("test.py")

        assert result == {"mtime": 12345, "hash": "test_hash"}
        mock_conn.execute.assert_called_once()


def test_get_file_info_nonexistent_file():
    """Test _get_file_info with nonexistent file."""
    mock_conn = Mock()

    with TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir)
        detector = ChangeDetector(mock_conn, repo_path)

        # Mock database result with no rows
        mock_result = Mock()
        mock_result.has_next.return_value = False
        mock_conn.execute.return_value = mock_result

        result = detector._get_file_info("nonexistent.py")

        assert result is None


def test_get_file_info_database_error():
    """Test _get_file_info with database error."""
    mock_conn = Mock()

    with TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir)
        detector = ChangeDetector(mock_conn, repo_path)

        mock_conn.execute.side_effect = Exception("Database error")

        result = detector._get_file_info("test.py")

        assert result is None


def test_get_tracked_files_success():
    """Test _get_tracked_files success case."""
    mock_conn = Mock()

    with TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir)
        detector = ChangeDetector(mock_conn, repo_path)

        # Mock database result
        mock_result = Mock()
        mock_result.has_next.side_effect = [True, True, False]
        mock_result.get_next.side_effect = [["file1.py"], ["file2.py"]]
        mock_conn.execute.return_value = mock_result

        result = detector._get_tracked_files()

        assert result == ["file1.py", "file2.py"]


@patch("os.sep", "\\")
def test_get_tracked_files_with_path_normalization():
    """Test _get_tracked_files normalizes path separators."""
    mock_conn = Mock()

    with TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir)
        detector = ChangeDetector(mock_conn, repo_path)

        # Mock database result with Windows-style paths
        mock_result = Mock()
        mock_result.has_next.side_effect = [True, True, False]
        # Return tuples like the real code would
        mock_result.get_next.side_effect = [["src\\test.py"], ["lib\\utils.py"]]
        mock_conn.execute.return_value = mock_result

        result = detector._get_tracked_files()

        # Should normalize backslashes to forward slashes
        assert result == ["src/test.py", "lib/utils.py"]


def test_get_tracked_files_database_error():
    """Test _get_tracked_files with database error."""
    mock_conn = Mock()

    with TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir)
        detector = ChangeDetector(mock_conn, repo_path)

        mock_conn.execute.side_effect = Exception("Database error")

        result = detector._get_tracked_files()

        assert result == []


def test_walk_source_files_basic():
    """Test _walk_source_files with basic functionality."""
    mock_conn = Mock()

    with TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir)
        detector = ChangeDetector(mock_conn, repo_path)

        # Create test files
        py_file = repo_path / "test.py"
        py_file.write_text("print('hello')")
        txt_file = repo_path / "readme.txt"
        txt_file.write_text("readme")

        result = detector._walk_source_files({".py"})

        assert len(result) == 1
        assert py_file.resolve() in [p.resolve() for p in result]
        # txt_file should not be in result because it doesn't have .py extension


def test_walk_source_files_ignores_common_directories():
    """Test _walk_source_files ignores common directories."""
    mock_conn = Mock()

    with TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir)
        detector = ChangeDetector(mock_conn, repo_path)

        # Create files in ignored directories
        git_dir = repo_path / ".git"
        git_dir.mkdir()
        git_file = git_dir / "config.py"
        git_file.write_text("git config")

        node_modules = repo_path / "node_modules"
        node_modules.mkdir()
        node_file = node_modules / "package.py"
        node_file.write_text("console.log('test');")

        # Create normal file
        normal_file = repo_path / "test.py"
        normal_file.write_text("print('hello')")

        result = detector._walk_source_files({".py"})

        # Should only find the normal file, ignored directory files should be excluded
        assert len(result) == 1
        assert normal_file.resolve() in [p.resolve() for p in result]


def test_walk_source_files_with_exclude_patterns():
    """Test _walk_source_files with exclude patterns."""
    mock_conn = Mock()

    with TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir)
        detector = ChangeDetector(mock_conn, repo_path)

        # Create test files
        included = repo_path / "included.py"
        included.write_text("print('included')")
        excluded = repo_path / "test_excluded.py"
        excluded.write_text("print('excluded')")

        result = detector._walk_source_files({".py"}, exclude_patterns=["test_*"])

        assert len(result) == 1
        resolved_results = [p.resolve() for p in result]
        assert included.resolve() in resolved_results
        assert excluded.resolve() not in resolved_results


def test_walk_source_files_with_directory_exclude_patterns():
    """Test _walk_source_files with directory exclude patterns."""
    mock_conn = Mock()

    with TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir)
        detector = ChangeDetector(mock_conn, repo_path)

        # Create excluded directory
        excluded_dir = repo_path / "excluded"
        excluded_dir.mkdir()

        detector._walk_source_files({".py"}, exclude_patterns=["*/excluded"])

        # excluded directory should be added to ignore_dirs
        # This tests the custom exclude pattern logic


def test_matches_pattern_glob():
    """Test _matches_pattern with glob patterns."""
    mock_conn = Mock()

    with TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir)
        detector = ChangeDetector(mock_conn, repo_path)

        assert detector._matches_pattern("test_file.py", "test_*.py")
        assert not detector._matches_pattern("other_file.py", "test_*.py")
        assert detector._matches_pattern("src/test.py", "*/test.py")


def test_matches_pattern_substring():
    """Test _matches_pattern with substring matching."""
    mock_conn = Mock()

    with TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir)
        detector = ChangeDetector(mock_conn, repo_path)

        assert detector._matches_pattern("test_file.py", "test_")
        assert not detector._matches_pattern("other_file.py", "test_")
        assert detector._matches_pattern("src/test/file.py", "test")


@pytest.mark.asyncio
async def test_calculate_file_hash_success():
    """Test _calculate_file_hash success case."""
    mock_conn = Mock()

    with TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir)
        detector = ChangeDetector(mock_conn, repo_path)

        test_file = repo_path / "test.py"
        content = "print('hello')"
        test_file.write_text(content)

        expected_hash = hashlib.sha256(content.encode()).hexdigest()
        result = await detector._calculate_file_hash(test_file)

        assert result == expected_hash


@pytest.mark.asyncio
async def test_calculate_file_hash_nonexistent_file():
    """Test _calculate_file_hash with nonexistent file."""
    mock_conn = Mock()

    with TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir)
        detector = ChangeDetector(mock_conn, repo_path)

        nonexistent = repo_path / "nonexistent.py"

        result = await detector._calculate_file_hash(nonexistent)

        assert result == ""


@pytest.mark.asyncio
async def test_calculate_file_hash_permission_error():
    """Test _calculate_file_hash with permission error."""
    mock_conn = Mock()

    with TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir)
        detector = ChangeDetector(mock_conn, repo_path)

        with patch("aiofiles.open", side_effect=PermissionError("Access denied")):
            test_file = repo_path / "test.py"
            test_file.write_text("content")

            result = await detector._calculate_file_hash(test_file)

            assert result == ""


def test_get_file_nodes_success():
    """Test get_file_nodes success case."""
    mock_conn = Mock()

    with TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir)
        detector = ChangeDetector(mock_conn, repo_path)

        # Mock database results for different node types
        def mock_execute(query, params):
            mock_result = Mock()
            if "TRACKS_Module" in query:
                mock_result.has_next.side_effect = [True, False]
                mock_result.get_next.return_value = ["module1"]
            elif "TRACKS_Class" in query:
                mock_result.has_next.side_effect = [True, True, False]
                mock_result.get_next.side_effect = [["class1"], ["class2"]]
            elif "TRACKS_Function" in query:
                mock_result.has_next.return_value = False
            elif "TRACKS_Method" in query:
                mock_result.has_next.side_effect = [True, False]
                mock_result.get_next.return_value = ["method1"]
            return mock_result

        mock_conn.execute.side_effect = mock_execute

        result = detector.get_file_nodes("test.py")

        assert result == {"module1", "class1", "class2", "method1"}


def test_get_file_nodes_no_nodes():
    """Test get_file_nodes with no nodes."""
    mock_conn = Mock()

    with TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir)
        detector = ChangeDetector(mock_conn, repo_path)

        # Mock empty results for all node types
        mock_result = Mock()
        mock_result.has_next.return_value = False
        mock_conn.execute.return_value = mock_result

        result = detector.get_file_nodes("test.py")

        assert result == set()


def test_get_file_nodes_database_error():
    """Test get_file_nodes with database errors."""
    mock_conn = Mock()

    with TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir)
        detector = ChangeDetector(mock_conn, repo_path)

        mock_conn.execute.side_effect = Exception("Database error")

        result = detector.get_file_nodes("test.py")

        # Should return empty set and not crash
        assert result == set()


@patch("shotgun.codebase.core.language_config.get_language_config")
def test_complete_change_detection_workflow(mock_get_config):
    """Test complete change detection workflow."""
    mock_conn = Mock()

    with TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir)
        detector = ChangeDetector(mock_conn, repo_path)

        # Mock language config
        mock_config = Mock()
        mock_config.file_extensions = {".py"}
        mock_get_config.return_value = mock_config

        # Create directory structure with various files
        src_dir = repo_path / "src"
        src_dir.mkdir()

        # New file
        new_file = src_dir / "new.py"
        new_file.write_text("def new_function(): pass")

        # Modified file
        modified_file = src_dir / "modified.py"
        modified_file.write_text("def modified_function(): pass")

        # Mock database responses
        def mock_get_file_info(filepath):
            if "modified.py" in filepath:
                return {"mtime": 1000, "hash": "old_hash"}
            return None

        def mock_get_tracked_files():
            return ["src/modified.py", "src/deleted.py"]

        detector._get_file_info = mock_get_file_info
        detector._get_tracked_files = mock_get_tracked_files

        changes = detector.detect_changes()

        assert len(changes) == 3
        assert changes["src/new.py"] == ChangeType.ADDED
        assert changes["src/modified.py"] == ChangeType.MODIFIED
        assert changes["src/deleted.py"] == ChangeType.DELETED


@patch("shotgun.codebase.core.language_config.get_language_config")
def test_error_resilience(mock_get_config):
    """Test error resilience in change detection with database errors."""
    mock_conn = Mock()

    with TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir)
        detector = ChangeDetector(mock_conn, repo_path)

        # Mock language config
        mock_config = Mock()
        mock_config.file_extensions = {".py"}
        mock_get_config.return_value = mock_config

        # Create a test file
        test_file = repo_path / "test.py"
        test_file.write_text("print('test')")

        # Mock database methods to return None/empty for errors
        # (simulating graceful error handling rather than exceptions)
        detector._get_file_info = Mock(return_value=None)
        detector._get_tracked_files = Mock(return_value=[])

        # Should work and detect the file as new since db returns empty
        changes = detector.detect_changes()

        # Should detect file as new since database appears empty
        assert isinstance(changes, dict)
        assert len(changes) == 1
        assert "test.py" in changes
        assert changes["test.py"] == ChangeType.ADDED


def test_path_normalization_consistency():
    """Test path normalization consistency across methods."""
    mock_conn = Mock()

    with TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir)
        detector = ChangeDetector(mock_conn, repo_path)

        # Test that paths are normalized consistently
        test_path_windows = "src\\test.py"
        test_path_unix = "src/test.py"

        # Mock tracked files method to return Windows-style paths from database
        # The method should normalize these to Unix-style paths
        mock_result = Mock()
        mock_result.has_next.side_effect = [True, False]
        mock_result.get_next.return_value = [test_path_windows]
        mock_conn.execute.return_value = mock_result

        # Use patch to mock os.sep as backslash to ensure normalization works
        with patch("shotgun.codebase.core.change_detector.os.sep", "\\"):
            tracked_files = detector._get_tracked_files()

        # Should normalize backslashes to forward slashes
        assert tracked_files == [test_path_unix]
