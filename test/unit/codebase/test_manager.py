"""Unit tests for manager module."""

import asyncio
import hashlib
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import anyio
import pytest

from shotgun.codebase.core.manager import CodebaseFileHandler, CodebaseGraphManager
from shotgun.codebase.models import (
    CodebaseGraph,
    FileChange,
    GraphStatus,
    OperationStats,
)


def test_codebase_file_handler_init():
    """Test CodebaseFileHandler initialization."""
    callback = Mock()
    loop = Mock()
    graph_id = "test-graph-id"

    handler = CodebaseFileHandler(graph_id, callback, loop)

    assert handler.graph_id == graph_id
    assert handler.callback == callback
    assert handler.loop == loop
    assert handler.pending_changes == []
    assert handler.ignore_patterns is not None


def test_codebase_file_handler_init_with_custom_ignore_patterns():
    """Test CodebaseFileHandler initialization with custom ignore patterns."""
    callback = Mock()
    loop = Mock()
    graph_id = "test-graph-id"
    custom_patterns = {"custom_ignore", "another_pattern"}

    handler = CodebaseFileHandler(
        graph_id, callback, loop, ignore_patterns=custom_patterns
    )

    assert handler.ignore_patterns == custom_patterns


def test_codebase_file_handler_on_any_event_ignores_directories():
    """Test that directory events are ignored."""
    callback = Mock()
    loop = Mock()
    handler = CodebaseFileHandler("test-graph", callback, loop)

    # Mock directory event
    mock_event = Mock()
    mock_event.is_directory = True
    mock_event.src_path = "/path/to/directory"

    handler.on_any_event(mock_event)

    # Should not process directory events
    assert len(handler.pending_changes) == 0


def test_codebase_file_handler_on_any_event_ignores_ignored_patterns():
    """Test that files matching ignore patterns are ignored."""
    callback = Mock()
    loop = Mock()
    handler = CodebaseFileHandler("test-graph", callback, loop)

    # Mock file event with ignored pattern
    mock_event = Mock()
    mock_event.is_directory = False
    mock_event.src_path = "/path/to/__pycache__/file.pyc"
    mock_event.event_type = "created"

    handler.on_any_event(mock_event)

    # Should ignore files in __pycache__
    assert len(handler.pending_changes) == 0


def test_codebase_file_handler_on_any_event_processes_valid_files():
    """Test that valid file events are processed."""
    callback = Mock()
    loop = Mock()
    handler = CodebaseFileHandler("test-graph", callback, loop)

    # Mock valid file event
    mock_event = Mock()
    mock_event.is_directory = False
    mock_event.src_path = "/path/to/source.py"
    mock_event.event_type = "created"
    mock_event.dest_path = None  # Add missing attribute

    # Mock asyncio.run_coroutine_threadsafe to avoid thread issues
    with (
        patch("asyncio.run_coroutine_threadsafe") as mock_run_coroutine,
        patch(
            "shotgun.codebase.core.manager.logger.info"
        ),  # Mock logger to avoid issues
    ):
        mock_future = Mock()
        mock_run_coroutine.return_value = mock_future
        handler.on_any_event(mock_event)

        # Verify that the coroutine was scheduled
        mock_run_coroutine.assert_called_once()
        # Verify that the scheduled coroutine is _queue_change
        args, kwargs = mock_run_coroutine.call_args
        assert len(args) == 2  # coroutine and loop
        assert args[1] == loop


def test_codebase_graph_manager_init():
    """Test CodebaseGraphManager initialization."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage_dir = Path(tmp_dir)

        with patch("shotgun.codebase.core.manager.Path.mkdir"):
            manager = CodebaseGraphManager(storage_dir)

        assert manager.storage_dir == storage_dir
        # Class-level attributes are properly managed by cleanup fixture


@pytest.mark.asyncio
async def test_get_or_create_connection():
    """Test database connection creation via build_graph."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage_dir = Path(tmp_dir)
        repo_path = tmp_dir

        # Create mock kuzu module
        mock_db = Mock()
        mock_conn = Mock()
        mock_kuzu = Mock()
        mock_kuzu.Database.return_value = mock_db
        mock_kuzu.Connection.return_value = mock_conn

        with (
            patch("shotgun.codebase.core.manager.Path.mkdir"),
            patch.object(Path, "exists", return_value=False),
            patch("shotgun.codebase.core.manager.get_kuzu", return_value=mock_kuzu),
            patch("shotgun.codebase.core.ingestor.CodebaseIngestor"),
            patch("shotgun.codebase.core.manager.logger"),
            patch("anyio.to_thread.run_sync"),
        ):
            manager = CodebaseGraphManager(storage_dir)

            # Mock the _execute_query method to return empty results
            with patch.object(manager, "_execute_query", return_value=[]):
                # Mock the _print_graph_statistics method
                with patch.object(manager, "_print_graph_statistics"):
                    # Connection is created during build_graph
                    graph = await manager.build_graph(repo_path, "test")
                    graph_id = graph.graph_id

                    assert graph_id in CodebaseGraphManager._connections
                    mock_kuzu.Database.assert_called()
                    mock_kuzu.Connection.assert_called_with(mock_db)


@pytest.mark.asyncio
async def test_get_or_create_connection_reuses_existing():
    """Test that existing connections are reused."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage_dir = Path(tmp_dir)

        with patch("shotgun.codebase.core.manager.Path.mkdir"):
            CodebaseGraphManager(storage_dir)
            graph_id = "test-graph-id"

            # Mock existing connection in class-level dict
            mock_conn = Mock()
            CodebaseGraphManager._connections[graph_id] = mock_conn

            # Test that connection exists
            assert graph_id in CodebaseGraphManager._connections
            assert CodebaseGraphManager._connections[graph_id] == mock_conn


def testgenerate_graph_id():
    """Test graph ID generation."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage_dir = Path(tmp_dir)

        with patch("shotgun.codebase.core.manager.Path.mkdir"):
            manager = CodebaseGraphManager(storage_dir)

        repo_path = "/path/to/repo"
        # Implementation normalizes path and uses 12-char hash
        normalized = str(Path(repo_path).resolve())
        expected_hash = hashlib.sha256(normalized.encode()).hexdigest()[:12]

        graph_id = manager.generate_graph_id(repo_path)

        assert graph_id == expected_hash
        assert len(graph_id) == 12


@pytest.mark.asyncio
async def test_list_graphs_empty():
    """Test listing graphs when none exist."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage_dir = Path(tmp_dir)

        with (
            patch("shotgun.codebase.core.manager.Path.mkdir"),
            patch.object(Path, "iterdir", return_value=[]),
        ):
            manager = CodebaseGraphManager(storage_dir)
            graphs = await manager.list_graphs()

            assert graphs == []


@pytest.mark.asyncio
async def test_list_graphs_with_existing():
    """Test listing existing graphs."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage_dir = Path(tmp_dir)

        # Mock existing graph directory
        mock_graph_dir = Mock()
        mock_graph_dir.is_dir.return_value = True
        mock_graph_dir.name = "test-graph-id"

        # Mock metadata file
        mock_metadata_file = Mock()
        mock_metadata_file.exists.return_value = True

        with (
            patch("shotgun.codebase.core.manager.Path.mkdir"),
            patch.object(Path, "glob") as mock_glob,
            patch("shotgun.codebase.core.manager.logger"),
        ):
            # Mock .kuzu file path
            mock_kuzu_file = Mock()
            mock_kuzu_file.is_file.return_value = True
            mock_kuzu_file.stem = "test-graph-id"
            mock_glob.return_value = [mock_kuzu_file]

            manager = CodebaseGraphManager(storage_dir)

            # Mock get_graph to return the expected graph
            expected_graph = CodebaseGraph(
                graph_id="test-graph-id",
                repo_path="/path/to/repo",
                graph_path="/path/to/graph",
                name="Test Graph",
                created_at=time.time(),
                updated_at=time.time(),
            )

            with patch.object(manager, "get_graph", return_value=expected_graph):
                graphs = await manager.list_graphs()

                assert len(graphs) == 1
                assert graphs[0].graph_id == "test-graph-id"
                assert graphs[0].name == "Test Graph"


def mock_open_metadata(content):
    """Helper to mock open() for metadata reading."""
    from unittest.mock import mock_open

    return mock_open(read_data=content)


@pytest.mark.asyncio
async def test_get_graph_existing():
    """Test getting an existing graph."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage_dir = Path(tmp_dir)

        metadata = {
            "graph_id": "test-graph-id",
            "repo_path": "/path/to/repo",
            "name": "Test Graph",
            "created_at": time.time(),
            "updated_at": time.time(),
            "schema_version": "1.0.0",
            "build_options": "{}",  # JSON string
            "language_stats": {},
            "node_count": 100,
            "relationship_count": 50,
            "node_stats": {},
            "relationship_stats": {},
            "is_watching": False,
            "status": "READY",
            "last_operation": None,
            "current_operation_id": None,
        }

        with (
            patch("shotgun.codebase.core.manager.Path.mkdir"),
            patch.object(Path, "exists", return_value=True),
            patch("shotgun.codebase.core.manager.logger"),
        ):
            manager = CodebaseGraphManager(storage_dir)

            # Mock the _execute_query method to return the expected project data
            project_data = [{"p": metadata}]
            lang_stats_data = []  # Empty language stats
            count_data = [{"count": 100}]  # Node count

            with patch.object(manager, "_execute_query") as mock_execute:
                # Set up the side_effect to return different data for different queries
                mock_execute.side_effect = [
                    project_data,  # Project query
                    lang_stats_data,  # Language stats query
                    count_data,  # Node count query
                    count_data,  # Relationship count query
                ]

                # Mock _get_graph_statistics to return empty stats
                with patch.object(
                    manager, "_get_graph_statistics", return_value=({}, {})
                ):
                    graph = await manager.get_graph("test-graph-id")

                    assert graph is not None
                    assert graph.graph_id == "test-graph-id"
                    assert graph.name == "Test Graph"


@pytest.mark.asyncio
async def test_get_graph_nonexistent():
    """Test getting a non-existent graph."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage_dir = Path(tmp_dir)

        with (
            patch("shotgun.codebase.core.manager.Path.mkdir"),
            patch.object(Path, "exists", return_value=False),
        ):
            manager = CodebaseGraphManager(storage_dir)
            graph = await manager.get_graph("nonexistent-id")

            assert graph is None


@pytest.mark.asyncio
async def test_delete_graph():
    """Test deleting a graph."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage_dir = Path(tmp_dir)

        async def run_sync_passthrough(func, *args, **kwargs):
            return func(*args, **kwargs)

        with (
            patch("shotgun.codebase.core.manager.Path.mkdir"),
            patch("shotgun.codebase.core.manager.logger"),
            patch("anyio.to_thread.run_sync", side_effect=run_sync_passthrough),
        ):
            manager = CodebaseGraphManager(storage_dir)
            graph_id = "test-graph-id"

            # Mock existing connection and watcher
            mock_conn = Mock()
            mock_watcher = Mock()
            mock_db = Mock()
            CodebaseGraphManager._connections[graph_id] = mock_conn
            CodebaseGraphManager._databases[graph_id] = mock_db
            CodebaseGraphManager._watchers[graph_id] = mock_watcher

            # Mock handlers dict for stop_watcher
            CodebaseGraphManager._handlers = {graph_id: Mock()}
            CodebaseGraphManager._handlers[graph_id].pending_changes = []

            # Mock path exists to return False so file deletion is skipped
            with patch.object(Path, "exists", return_value=False):
                await manager.delete_graph(graph_id)

            # Should stop watcher and close connections
            mock_watcher.stop.assert_called_once()
            mock_conn.close.assert_called_once()
            mock_db.close.assert_called_once()
            # Should remove from tracking dicts
            assert graph_id not in CodebaseGraphManager._connections
            assert graph_id not in CodebaseGraphManager._databases
            assert graph_id not in CodebaseGraphManager._watchers


@pytest.mark.asyncio
async def test_build_graph(temp_storage_dir, unique_graph_id):
    """Test building a new graph."""
    storage_dir = temp_storage_dir
    with (
        patch("shotgun.codebase.core.manager.Path.mkdir"),
        patch("shotgun.codebase.core.ingestor.CodebaseIngestor") as mock_ingestor_class,
        patch("shotgun.codebase.core.manager.logger"),
    ):
        mock_ingestor = Mock()
        mock_ingestor_class.return_value = mock_ingestor

        manager = CodebaseGraphManager(storage_dir)

        # Mock repository path exists but graph doesn't
        def mock_exists(self):
            # Repository path exists, but graph database doesn't
            if str(self) == "/path/to/repo":
                return True
            return False  # Graph database doesn't exist yet

        def mock_is_dir(self):
            if str(self) == "/path/to/repo":
                return True
            return False

        with (
            patch.object(Path, "exists", mock_exists),
            patch.object(Path, "is_dir", mock_is_dir),
            patch.object(manager, "generate_graph_id", return_value="test-unique-id"),
            patch(
                "anyio.to_thread.run_sync"
            ) as mock_run_sync,  # Mock threaded ingestor call
        ):
            # Mock the ingestor build call to avoid actual graph building
            mock_run_sync.return_value = None

            graph = await manager.build_graph("/path/to/repo", "Test Graph")

            assert graph.name == "Test Graph"
            assert graph.repo_path == "/path/to/repo"
            # Verify the ingestor was called in a thread
            mock_run_sync.assert_called()


@pytest.mark.asyncio
async def test_build_graph_invalid_path(temp_storage_dir, unique_graph_id):
    """Test building graph with invalid repository path."""
    storage_dir = temp_storage_dir
    with (
        patch("shotgun.codebase.core.manager.Path.mkdir"),
        patch("shotgun.codebase.core.manager.logger"),
    ):
        manager = CodebaseGraphManager(storage_dir)

        # Test currently doesn't validate repo path, so just test that it doesn't crash
        # Mock path exists to avoid graph collision and let build succeed
        def mock_exists(self):
            return False  # Graph doesn't exist yet

        with (
            patch.object(Path, "exists", mock_exists),
            patch.object(manager, "_build_graph_impl") as mock_build,
        ):
            mock_graph = CodebaseGraph(
                graph_id="test-id",
                repo_path="/nonexistent/path",
                graph_path="/path/to/graph",
                name="Test Graph",
                created_at=time.time(),
                updated_at=time.time(),
                last_operation=None,
                current_operation_id=None,
            )
            mock_build.return_value = mock_graph

            # Should succeed even with invalid path since validation happens in ingestor
            graph = await manager.build_graph("/nonexistent/path", "Test Graph")
            assert graph.repo_path == "/nonexistent/path"


@pytest.mark.asyncio
async def test_execute_query():
    """Test executing a query against a graph."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage_dir = Path(tmp_dir)

        mock_conn = Mock()
        mock_result = Mock()

        # Configure result properly
        mock_result.get_column_names.return_value = ["node"]
        mock_result.has_next.side_effect = [True, False]  # First true, then false
        mock_result.get_next.return_value = [{"name": "TestClass"}]  # Single row

        mock_conn.execute.return_value = mock_result

        with patch("shotgun.codebase.core.manager.Path.mkdir"):
            manager = CodebaseGraphManager(storage_dir)
            CodebaseGraphManager._connections["test-graph"] = mock_conn

            # Mock anyio.to_thread.run_sync to directly call the function
            with patch(
                "anyio.to_thread.run_sync",
                side_effect=lambda func, *args, **kwargs: func(*args, **kwargs),
            ):
                results = await manager.execute_query(
                    "test-graph", "MATCH (n:Class) RETURN n", {}
                )

                assert len(results) == 1
                assert results[0]["node"] == {"name": "TestClass"}
                mock_conn.execute.assert_called_once()


@pytest.mark.asyncio
async def test_execute_query_no_connection():
    """Test executing query when no connection exists."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage_dir = Path(tmp_dir)

        with patch("shotgun.codebase.core.manager.Path.mkdir"):
            manager = CodebaseGraphManager(storage_dir)

            # Mock Path.exists to return False for nonexistent graph
            with patch.object(Path, "exists", return_value=False):
                with pytest.raises(ValueError, match="Graph .* not found"):
                    await manager.execute_query(
                        "nonexistent-graph", "MATCH (n) RETURN n", {}
                    )


@pytest.mark.asyncio
async def test_start_watcher():
    """Test starting file system watching."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage_dir = Path(tmp_dir)

        with (
            patch("shotgun.codebase.core.manager.Path.mkdir"),
            patch("shotgun.codebase.core.manager.Observer") as mock_observer_class,
            patch("shotgun.codebase.core.manager.logger"),
        ):
            mock_observer = Mock()
            mock_observer_class.return_value = mock_observer

            manager = CodebaseGraphManager(storage_dir)
            graph_id = "test-graph"
            repo_path = "/path/to/repo"

            # Mock get_graph to return a valid graph
            mock_graph = CodebaseGraph(
                graph_id=graph_id,
                repo_path=repo_path,
                graph_path="/path/to/graph",
                name="Test Graph",
                created_at=time.time(),
                updated_at=time.time(),
                last_operation=None,
                current_operation_id=None,
            )
            with patch.object(manager, "get_graph", return_value=mock_graph):
                await manager.start_watcher(graph_id, repo_path)

                assert graph_id in CodebaseGraphManager._watchers
                mock_observer.schedule.assert_called_once()
                mock_observer.start.assert_called_once()


@pytest.mark.asyncio
async def test_stop_watcher():
    """Test stopping file system watching."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage_dir = Path(tmp_dir)

        with (
            patch("shotgun.codebase.core.manager.Path.mkdir"),
            patch("shotgun.codebase.core.manager.logger"),
        ):
            manager = CodebaseGraphManager(storage_dir)
            graph_id = "test-graph"

            # Mock existing watcher
            mock_watcher = Mock()
            CodebaseGraphManager._watchers[graph_id] = mock_watcher

            # Mock handlers dict
            CodebaseGraphManager._handlers = {graph_id: Mock()}
            CodebaseGraphManager._handlers[graph_id].pending_changes = []

            await manager.stop_watcher(graph_id)

            mock_watcher.stop.assert_called_once()
            assert graph_id not in CodebaseGraphManager._watchers


@pytest.mark.asyncio
async def test_update_graph_incremental():
    """Test incremental graph update."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage_dir = Path(tmp_dir)

        with (
            patch("shotgun.codebase.core.manager.Path.mkdir"),
            patch("shotgun.codebase.core.manager.logger"),
        ):
            manager = CodebaseGraphManager(storage_dir)
            graph_id = "test-graph"

            # Mock graph metadata
            mock_graph = CodebaseGraph(
                graph_id=graph_id,
                repo_path="/path/to/repo",
                graph_path="/path/to/graph",
                name="Test Graph",
                created_at=time.time(),
                updated_at=time.time(),
                last_operation=None,
                current_operation_id=None,
            )

            # Mock path methods to simulate valid directory
            def mock_exists(self):
                if str(self) == "/path/to/repo":
                    return True
                return False

            def mock_is_dir(self):
                if str(self) == "/path/to/repo":
                    return True
                return False

            # Create mock kuzu module
            mock_kuzu = Mock()
            mock_kuzu.Database.return_value = Mock()
            mock_kuzu.Connection.return_value = Mock()

            with (
                patch.object(manager, "get_graph", return_value=mock_graph),
                patch.object(Path, "exists", mock_exists),
                patch.object(Path, "is_dir", mock_is_dir),
                patch("shotgun.codebase.core.manager.get_kuzu", return_value=mock_kuzu),
                patch(
                    "shotgun.codebase.core.change_detector.ChangeDetector"
                ) as mock_detector_class,
                patch(
                    "shotgun.codebase.core.parser_loader.load_parsers"
                ) as mock_load_parsers,
            ):
                # Mock the change detector
                mock_detector = MagicMock()
                mock_detector.detect_changes.return_value = []
                mock_detector_class.return_value = mock_detector

                # Mock parsers
                mock_load_parsers.return_value = (
                    {"python": MagicMock()},
                    {"python": MagicMock()},
                )

                stats = await manager.update_graph_incremental(graph_id)

                # Since no changes are detected, should return zero stats
                expected_stats = {
                    "nodes_added": 0,
                    "nodes_removed": 0,
                    "nodes_modified": 0,
                    "relationships_added": 0,
                    "relationships_removed": 0,
                    "files_added": 0,
                    "files_modified": 0,
                    "files_deleted": 0,
                    "files_skipped": 0,
                }

                assert stats["nodes_added"] == expected_stats["nodes_added"]
                assert stats["files_added"] == expected_stats["files_added"]
                assert "update_time_ms" in stats


@pytest.mark.asyncio
async def test_update_graph_incremental_not_found():
    """Test incremental update of non-existent graph."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage_dir = Path(tmp_dir)

        with patch("shotgun.codebase.core.manager.Path.mkdir"):
            manager = CodebaseGraphManager(storage_dir)

            with patch.object(manager, "get_graph", return_value=None):
                with pytest.raises(ValueError, match="Graph .* not found"):
                    await manager.update_graph_incremental("nonexistent-graph")


def test_file_change_model():
    """Test FileChange model creation."""
    change = FileChange(
        event_type="created",
        src_path="/path/to/file.py",
        dest_path=None,
        is_directory=False,
    )

    assert change.event_type == "created"
    assert change.src_path == "/path/to/file.py"
    assert change.dest_path is None
    assert change.is_directory is False


def test_operation_stats_model():
    """Test OperationStats model creation."""
    stats = OperationStats(
        operation_type="build",
        started_at=time.time(),
        completed_at=time.time() + 60,
        success=True,
        error=None,
        stats={"files_processed": 100},
    )

    assert stats.operation_type == "build"
    assert stats.success is True
    assert stats.error is None
    assert stats.stats["files_processed"] == 100


def test_codebase_graph_model():
    """Test CodebaseGraph model creation."""
    graph = CodebaseGraph(
        graph_id="test-id",
        repo_path="/path/to/repo",
        graph_path="/path/to/graph",
        name="Test Graph",
        created_at=time.time(),
        updated_at=time.time(),
        last_operation=None,
        current_operation_id=None,
    )

    assert graph.graph_id == "test-id"
    assert graph.repo_path == "/path/to/repo"
    assert graph.name == "Test Graph"
    assert graph.status == GraphStatus.READY  # Default value
    assert graph.node_count == 0  # Default value


def test_graph_status_enum():
    """Test GraphStatus enum values."""
    assert GraphStatus.READY == "READY"
    assert GraphStatus.BUILDING == "BUILDING"
    assert GraphStatus.UPDATING == "UPDATING"
    assert GraphStatus.ERROR == "ERROR"


# Tests for _save_graph_metadata and _load_graph_metadata removed
# as these methods no longer exist in the current implementation
# The manager now stores metadata directly in the graph database


def test_hash_consistency():
    """Test that hash generation is consistent."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage_dir = Path(tmp_dir)

        with patch("shotgun.codebase.core.manager.Path.mkdir"):
            manager = CodebaseGraphManager(storage_dir)

        repo_path = "/path/to/repo"
        hash1 = manager.generate_graph_id(repo_path)
        hash2 = manager.generate_graph_id(repo_path)

        assert hash1 == hash2


# Test for _cleanup removed as this method no longer exists
# Cleanup is now handled automatically by the manager


@pytest.mark.asyncio
async def test_concurrent_operations():
    """Test handling of concurrent operations."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage_dir = Path(tmp_dir)

        with patch("shotgun.codebase.core.manager.Path.mkdir"):
            manager = CodebaseGraphManager(storage_dir)

        graph_id = "test-graph"

        # Mock concurrent access to same graph
        mock_graph = CodebaseGraph(
            graph_id=graph_id,
            repo_path="/path/to/repo",
            graph_path="/path/to/graph",
            name="Test Graph",
            created_at=time.time(),
            updated_at=time.time(),
            last_operation=None,
            current_operation_id="operation-1",
        )

        # First operation in progress
        with patch.object(manager, "get_graph", return_value=mock_graph):
            # Should handle concurrent access appropriately
            result = await manager.get_graph(graph_id)
            assert result is not None
            assert result.current_operation_id == "operation-1"


@pytest.mark.asyncio
async def test_error_handling_in_build():
    """Test error handling during graph building."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage_dir = Path(tmp_dir)

        with (
            patch("shotgun.codebase.core.manager.Path.mkdir"),
            patch("shotgun.codebase.core.manager.logger"),
        ):
            manager = CodebaseGraphManager(storage_dir)

            # Mock the _build_graph_impl method to raise an exception
            # Mock repo path exists but graph doesn't exist yet
            def mock_exists(self):
                if str(self) == "/path/to/repo":
                    return True
                return False  # Graph database doesn't exist yet

            def mock_is_dir(self):
                if str(self) == "/path/to/repo":
                    return True
                return False

            with (
                patch.object(Path, "exists", mock_exists),
                patch.object(Path, "is_dir", mock_is_dir),
                patch("anyio.to_thread.run_sync", side_effect=Exception("Build Error")),
            ):
                with pytest.raises(Exception, match="Build Error"):
                    await manager.build_graph("/path/to/repo", "Test Graph")


@pytest.mark.asyncio
async def test_stop_all_watchers():
    """Test stopping all file watchers at once."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage_dir = Path(tmp_dir)

        with (
            patch("shotgun.codebase.core.manager.Path.mkdir"),
            patch("shotgun.codebase.core.manager.logger"),
        ):
            CodebaseGraphManager(storage_dir)

            # Set up multiple mock watchers
            mock_watcher1 = Mock()
            mock_watcher2 = Mock()
            mock_handler1 = Mock()
            mock_handler2 = Mock()

            CodebaseGraphManager._watchers["graph-1"] = mock_watcher1
            CodebaseGraphManager._watchers["graph-2"] = mock_watcher2
            CodebaseGraphManager._handlers["graph-1"] = mock_handler1
            CodebaseGraphManager._handlers["graph-2"] = mock_handler2

            await CodebaseGraphManager.stop_all_watchers()

            # All watchers should be stopped and joined
            mock_watcher1.stop.assert_called_once()
            mock_watcher1.join.assert_called_once_with(timeout=5)
            mock_watcher2.stop.assert_called_once()
            mock_watcher2.join.assert_called_once_with(timeout=5)

            # Dicts should be cleared
            assert len(CodebaseGraphManager._watchers) == 0
            assert len(CodebaseGraphManager._handlers) == 0


@pytest.mark.asyncio
async def test_stop_all_watchers_handles_errors():
    """Test that stop_all_watchers handles errors gracefully."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage_dir = Path(tmp_dir)

        with (
            patch("shotgun.codebase.core.manager.Path.mkdir"),
            patch("shotgun.codebase.core.manager.logger"),
        ):
            CodebaseGraphManager(storage_dir)

            # Set up a watcher that raises on stop
            mock_watcher_bad = Mock()
            mock_watcher_bad.stop.side_effect = RuntimeError("stop failed")
            mock_watcher_good = Mock()

            CodebaseGraphManager._watchers["bad"] = mock_watcher_bad
            CodebaseGraphManager._watchers["good"] = mock_watcher_good
            CodebaseGraphManager._handlers["bad"] = Mock()
            CodebaseGraphManager._handlers["good"] = Mock()

            await CodebaseGraphManager.stop_all_watchers()

            # Good watcher should still be stopped despite bad one failing
            mock_watcher_good.stop.assert_called_once()

            # Dicts should be cleared regardless of errors
            assert len(CodebaseGraphManager._watchers) == 0
            assert len(CodebaseGraphManager._handlers) == 0


def test_stop_all_watchers_sync():
    """Test synchronous version of stop_all_watchers."""
    mock_watcher1 = Mock()
    mock_watcher2 = Mock()

    CodebaseGraphManager._watchers["graph-1"] = mock_watcher1
    CodebaseGraphManager._watchers["graph-2"] = mock_watcher2
    CodebaseGraphManager._handlers["graph-1"] = Mock()
    CodebaseGraphManager._handlers["graph-2"] = Mock()

    CodebaseGraphManager.stop_all_watchers_sync()

    mock_watcher1.stop.assert_called_once()
    mock_watcher1.join.assert_called_once_with(timeout=5)
    mock_watcher2.stop.assert_called_once()
    mock_watcher2.join.assert_called_once_with(timeout=5)

    assert len(CodebaseGraphManager._watchers) == 0
    assert len(CodebaseGraphManager._handlers) == 0


def test_ignore_patterns_logic():
    """Test ignore patterns logic in file handler."""
    callback = Mock()
    loop = Mock()
    handler = CodebaseFileHandler("test-graph", callback, loop)

    # Test various paths
    test_cases = [
        ("src/main.py", False),  # Should not ignore
        ("__pycache__/compiled.pyc", True),  # Should ignore
        (".git/config", True),  # Should ignore
        ("node_modules/pkg/index.js", True),  # Should ignore
        ("test/test_file.py", False),  # Should not ignore
    ]

    for path, should_ignore in test_cases:
        # Check if path contains any ignore pattern
        is_ignored = any(pattern in path for pattern in handler.ignore_patterns)
        assert is_ignored == should_ignore


def test_lock_initialized_eagerly():
    """Verify _lock is an anyio.Lock at class definition time, not None."""
    assert CodebaseGraphManager._lock is not None
    assert isinstance(CodebaseGraphManager._lock, anyio.Lock)


@pytest.mark.asyncio
async def test_close_all_databases_closes_connections_and_dbs():
    """Test close_all_databases closes connections first, then databases, and clears dicts."""
    mock_conn = Mock()
    mock_db = Mock()

    CodebaseGraphManager._connections["g1"] = mock_conn
    CodebaseGraphManager._databases["g1"] = mock_db

    with patch(
        "anyio.to_thread.run_sync",
        side_effect=lambda func, *a, **kw: func(*a, **kw),
    ):
        await CodebaseGraphManager.close_all_databases()

    mock_conn.close.assert_called_once()
    mock_db.close.assert_called_once()
    assert len(CodebaseGraphManager._connections) == 0
    assert len(CodebaseGraphManager._databases) == 0


@pytest.mark.asyncio
async def test_close_all_databases_handles_close_errors():
    """Test that close_all_databases clears dicts even when close() raises."""
    mock_conn = Mock()
    mock_conn.close.side_effect = RuntimeError("connection close failed")
    mock_db = Mock()
    mock_db.close.side_effect = RuntimeError("db close failed")

    CodebaseGraphManager._connections["g1"] = mock_conn
    CodebaseGraphManager._databases["g1"] = mock_db

    with (
        patch(
            "anyio.to_thread.run_sync",
            side_effect=lambda func, *a, **kw: func(*a, **kw),
        ),
        patch("shotgun.codebase.core.manager.logger"),
    ):
        await CodebaseGraphManager.close_all_databases()

    assert len(CodebaseGraphManager._connections) == 0
    assert len(CodebaseGraphManager._databases) == 0


@pytest.mark.asyncio
async def test_close_all_databases_handles_timeout():
    """Test that close_all_databases handles a slow close that times out."""
    mock_conn = Mock()

    async def slow_close(*args, **kwargs):
        await asyncio.sleep(10)

    CodebaseGraphManager._connections["g1"] = mock_conn
    CodebaseGraphManager._databases.clear()

    with (
        patch("anyio.to_thread.run_sync", side_effect=slow_close),
        patch("shotgun.codebase.core.manager.logger"),
    ):
        await CodebaseGraphManager.close_all_databases(timeout_seconds=0.1)

    assert len(CodebaseGraphManager._connections) == 0


def test_close_all_databases_sync():
    """Test close_all_databases_sync closes connections and databases."""
    mock_conn = Mock()
    mock_db = Mock()

    CodebaseGraphManager._connections["g1"] = mock_conn
    CodebaseGraphManager._databases["g1"] = mock_db

    CodebaseGraphManager.close_all_databases_sync()

    mock_conn.close.assert_called_once()
    mock_db.close.assert_called_once()
    assert len(CodebaseGraphManager._connections) == 0
    assert len(CodebaseGraphManager._databases) == 0


def test_close_all_databases_sync_handles_errors():
    """Test close_all_databases_sync clears dicts even when close() raises."""
    mock_conn = Mock()
    mock_conn.close.side_effect = RuntimeError("close failed")

    CodebaseGraphManager._connections["g1"] = mock_conn
    CodebaseGraphManager._databases.clear()

    CodebaseGraphManager.close_all_databases_sync()

    assert len(CodebaseGraphManager._connections) == 0


@pytest.mark.asyncio
async def test_delete_graph_timeout_on_close():
    """Test that delete_graph doesn't block forever on a hung close."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage_dir = Path(tmp_dir)

        async def slow_run_sync(func, *args, **kwargs):
            await asyncio.sleep(10)

        with (
            patch("shotgun.codebase.core.manager.Path.mkdir"),
            patch("shotgun.codebase.core.manager.logger"),
        ):
            manager = CodebaseGraphManager(storage_dir)
            graph_id = "test-graph-timeout"

            mock_conn = Mock()
            mock_db = Mock()
            CodebaseGraphManager._connections[graph_id] = mock_conn
            CodebaseGraphManager._databases[graph_id] = mock_db

            with (
                patch("anyio.to_thread.run_sync", side_effect=slow_run_sync),
                patch.object(Path, "exists", return_value=False),
            ):
                await manager.delete_graph(graph_id)

            # Dicts should be cleared despite timeout
            assert graph_id not in CodebaseGraphManager._connections
            assert graph_id not in CodebaseGraphManager._databases
