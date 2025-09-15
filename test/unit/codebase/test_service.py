"""Unit tests for service module."""

import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from shotgun.codebase.models import CodebaseGraph, QueryResult, QueryType
from shotgun.codebase.service import CodebaseService


def test_codebase_service_init_with_path_object():
    """Test CodebaseService initialization with Path object."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage_dir = Path(tmp_dir)

        with (
            patch.object(Path, "mkdir") as mock_mkdir,
            patch(
                "shotgun.codebase.service.CodebaseGraphManager"
            ) as mock_manager_class,
        ):
            mock_manager = Mock()
            mock_manager_class.return_value = mock_manager

            service = CodebaseService(storage_dir)

            assert service.storage_dir == storage_dir
            assert service.manager == mock_manager
            mock_mkdir.assert_called_once_with(exist_ok=True)
            mock_manager_class.assert_called_once_with(storage_dir)


def test_codebase_service_init_with_string_path():
    """Test CodebaseService initialization with string path."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage_dir = tmp_dir

        with (
            patch.object(Path, "mkdir") as mock_mkdir,
            patch(
                "shotgun.codebase.service.CodebaseGraphManager"
            ) as mock_manager_class,
        ):
            mock_manager = Mock()
            mock_manager_class.return_value = mock_manager

            service = CodebaseService(storage_dir)

            assert service.storage_dir == Path(storage_dir)
            assert service.manager == mock_manager
            mock_mkdir.assert_called_once_with(exist_ok=True)


@pytest.mark.asyncio
async def test_list_graphs():
    """Test listing all graphs."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage_dir = Path(tmp_dir)

        mock_graphs = [
            CodebaseGraph(
                graph_id="graph-1",
                repo_path="/path/to/repo1",
                graph_path="/path/to/graph1",
                name="Graph 1",
                created_at=time.time(),
                updated_at=time.time(),
            ),
            CodebaseGraph(
                graph_id="graph-2",
                repo_path="/path/to/repo2",
                graph_path="/path/to/graph2",
                name="Graph 2",
                created_at=time.time(),
                updated_at=time.time(),
            ),
        ]

        with (
            patch.object(Path, "mkdir"),
            patch(
                "shotgun.codebase.service.CodebaseGraphManager"
            ) as mock_manager_class,
        ):
            mock_manager = Mock()
            mock_manager.list_graphs = AsyncMock(return_value=mock_graphs)
            mock_manager_class.return_value = mock_manager

            service = CodebaseService(storage_dir)
            graphs = await service.list_graphs()

            assert len(graphs) == 2
            assert graphs[0].graph_id == "graph-1"
            assert graphs[1].name == "Graph 2"
            mock_manager.list_graphs.assert_called_once()


@pytest.mark.asyncio
async def test_list_graphs_empty():
    """Test listing graphs when none exist."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage_dir = Path(tmp_dir)

        with (
            patch.object(Path, "mkdir"),
            patch(
                "shotgun.codebase.service.CodebaseGraphManager"
            ) as mock_manager_class,
        ):
            mock_manager = Mock()
            mock_manager.list_graphs = AsyncMock(return_value=[])
            mock_manager_class.return_value = mock_manager

            service = CodebaseService(storage_dir)
            graphs = await service.list_graphs()

            assert graphs == []


@pytest.mark.asyncio
async def test_create_graph_with_string_path():
    """Test creating a graph with string repository path."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage_dir = Path(tmp_dir)
        repo_path = "/path/to/repository"
        graph_name = "My Test Graph"

        mock_graph = CodebaseGraph(
            graph_id="new-graph-id",
            repo_path=repo_path,
            graph_path="/path/to/graph",
            name=graph_name,
            created_at=time.time(),
            updated_at=time.time(),
        )

        with (
            patch.object(Path, "mkdir"),
            patch(
                "shotgun.codebase.service.CodebaseGraphManager"
            ) as mock_manager_class,
        ):
            mock_manager = Mock()
            mock_manager.build_graph = AsyncMock(return_value=mock_graph)
            mock_manager_class.return_value = mock_manager

            service = CodebaseService(storage_dir)
            created_graph = await service.create_graph(repo_path, graph_name)

            assert created_graph.graph_id == "new-graph-id"
            assert created_graph.name == graph_name
            assert created_graph.repo_path == repo_path
            mock_manager.build_graph.assert_called_once_with(repo_path, graph_name)


@pytest.mark.asyncio
async def test_create_graph_with_path_object():
    """Test creating a graph with Path repository path."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage_dir = Path(tmp_dir)
        repo_path = Path("/path/to/repository")
        graph_name = "My Test Graph"

        mock_graph = CodebaseGraph(
            graph_id="new-graph-id",
            repo_path=str(repo_path),
            graph_path="/path/to/graph",
            name=graph_name,
            created_at=time.time(),
            updated_at=time.time(),
        )

        with (
            patch.object(Path, "mkdir"),
            patch(
                "shotgun.codebase.service.CodebaseGraphManager"
            ) as mock_manager_class,
        ):
            mock_manager = Mock()
            mock_manager.build_graph = AsyncMock(return_value=mock_graph)
            mock_manager_class.return_value = mock_manager

            service = CodebaseService(storage_dir)
            created_graph = await service.create_graph(repo_path, graph_name)

            assert created_graph.name == graph_name
            mock_manager.build_graph.assert_called_once_with(str(repo_path), graph_name)


@pytest.mark.asyncio
async def test_get_graph_existing():
    """Test getting an existing graph."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage_dir = Path(tmp_dir)
        graph_id = "existing-graph-id"

        mock_graph = CodebaseGraph(
            graph_id=graph_id,
            repo_path="/path/to/repo",
            graph_path="/path/to/graph",
            name="Existing Graph",
            created_at=time.time(),
            updated_at=time.time(),
        )

        with (
            patch.object(Path, "mkdir"),
            patch(
                "shotgun.codebase.service.CodebaseGraphManager"
            ) as mock_manager_class,
        ):
            mock_manager = Mock()
            mock_manager.get_graph = AsyncMock(return_value=mock_graph)
            mock_manager_class.return_value = mock_manager

            service = CodebaseService(storage_dir)
            retrieved_graph = await service.get_graph(graph_id)

            assert retrieved_graph is not None
            assert retrieved_graph.graph_id == graph_id
            assert retrieved_graph.name == "Existing Graph"
            mock_manager.get_graph.assert_called_once_with(graph_id)


@pytest.mark.asyncio
async def test_get_graph_nonexistent():
    """Test getting a non-existent graph."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage_dir = Path(tmp_dir)

        with (
            patch.object(Path, "mkdir"),
            patch(
                "shotgun.codebase.service.CodebaseGraphManager"
            ) as mock_manager_class,
        ):
            mock_manager = Mock()
            mock_manager.get_graph = AsyncMock(return_value=None)
            mock_manager_class.return_value = mock_manager

            service = CodebaseService(storage_dir)
            retrieved_graph = await service.get_graph("nonexistent-id")

            assert retrieved_graph is None


@pytest.mark.asyncio
async def test_delete_graph():
    """Test deleting a graph."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage_dir = Path(tmp_dir)
        graph_id = "graph-to-delete"

        with (
            patch.object(Path, "mkdir"),
            patch(
                "shotgun.codebase.service.CodebaseGraphManager"
            ) as mock_manager_class,
        ):
            mock_manager = Mock()
            mock_manager.delete_graph = AsyncMock()
            mock_manager_class.return_value = mock_manager

            service = CodebaseService(storage_dir)
            await service.delete_graph(graph_id)

            mock_manager.delete_graph.assert_called_once_with(graph_id)


@pytest.mark.asyncio
async def test_reindex_graph():
    """Test reindexing a graph."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage_dir = Path(tmp_dir)
        graph_id = "graph-to-reindex"

        mock_stats = {
            "files_processed": 50,
            "nodes_created": 200,
            "relationships_created": 150,
            "duration_ms": 5000,
        }

        with (
            patch.object(Path, "mkdir"),
            patch(
                "shotgun.codebase.service.CodebaseGraphManager"
            ) as mock_manager_class,
        ):
            mock_manager = Mock()
            mock_manager.update_graph_incremental = AsyncMock(return_value=mock_stats)
            mock_manager_class.return_value = mock_manager

            service = CodebaseService(storage_dir)
            stats = await service.reindex_graph(graph_id)

            assert stats == mock_stats
            assert stats["files_processed"] == 50
            mock_manager.update_graph_incremental.assert_called_once_with(graph_id)


@pytest.mark.asyncio
async def test_execute_query_cypher():
    """Test executing a Cypher query."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage_dir = Path(tmp_dir)
        graph_id = "test-graph"
        cypher_query = "MATCH (n:Function) RETURN n.name LIMIT 10"
        parameters = {"limit": 10}

        mock_db_results = [
            {"n.name": "function1"},
            {"n.name": "function2"},
            {"n.name": "function3"},
        ]

        with (
            patch.object(Path, "mkdir"),
            patch(
                "shotgun.codebase.service.CodebaseGraphManager"
            ) as mock_manager_class,
        ):
            mock_manager = Mock()
            mock_manager.execute_query = AsyncMock(return_value=mock_db_results)
            mock_manager_class.return_value = mock_manager

            service = CodebaseService(storage_dir)

            with patch(
                "shotgun.codebase.service.time.time", side_effect=[1000.0, 1000.5]
            ):
                result = await service.execute_query(
                    graph_id=graph_id,
                    query=cypher_query,
                    query_type=QueryType.CYPHER,
                    parameters=parameters,
                )

            assert isinstance(result, QueryResult)
            assert result.query == cypher_query
            assert result.cypher_query is None  # Not generated from natural language
            assert result.success is True
            assert result.error is None
            assert len(result.results) == 3
            assert result.row_count == 3
            assert result.column_names == ["n.name"]
            assert result.execution_time_ms == 500.0

            mock_manager.execute_query.assert_called_once_with(
                graph_id=graph_id, query=cypher_query, parameters=parameters
            )


@pytest.mark.asyncio
async def test_execute_query_natural_language():
    """Test executing a natural language query."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage_dir = Path(tmp_dir)
        graph_id = "test-graph"
        nl_query = "Show me all functions in the codebase"
        generated_cypher = "MATCH (n:Function) RETURN n.name, n.qualified_name"

        mock_db_results = [
            {"n.name": "main", "n.qualified_name": "module.main"},
            {"n.name": "helper", "n.qualified_name": "utils.helper"},
        ]

        with (
            patch.object(Path, "mkdir"),
            patch(
                "shotgun.codebase.service.CodebaseGraphManager"
            ) as mock_manager_class,
            patch("shotgun.codebase.service.generate_cypher") as mock_generate_cypher,
        ):
            mock_manager = Mock()
            mock_manager.execute_query = AsyncMock(return_value=mock_db_results)
            mock_manager_class.return_value = mock_manager

            mock_generate_cypher.return_value = generated_cypher

            service = CodebaseService(storage_dir)

            with patch("shotgun.codebase.service.time.time", return_value=1000.0):
                result = await service.execute_query(
                    graph_id=graph_id,
                    query=nl_query,
                    query_type=QueryType.NATURAL_LANGUAGE,
                )

            assert result.query == nl_query
            assert result.cypher_query == generated_cypher
            assert result.success is True
            assert len(result.results) == 2
            assert result.column_names == ["n.name", "n.qualified_name"]

            mock_generate_cypher.assert_called_once_with(nl_query)
            mock_manager.execute_query.assert_called_once_with(
                graph_id=graph_id, query=generated_cypher, parameters=None
            )


@pytest.mark.asyncio
async def test_execute_query_natural_language_with_parameters():
    """Test executing natural language query with parameters."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage_dir = Path(tmp_dir)

        with (
            patch.object(Path, "mkdir"),
            patch(
                "shotgun.codebase.service.CodebaseGraphManager"
            ) as mock_manager_class,
            patch("shotgun.codebase.service.generate_cypher") as mock_generate_cypher,
        ):
            mock_manager = Mock()
            mock_manager.execute_query = AsyncMock(return_value=[])
            mock_manager_class.return_value = mock_manager
            mock_generate_cypher.return_value = "MATCH (n) RETURN n"

            service = CodebaseService(storage_dir)

            await service.execute_query(
                graph_id="test-graph",
                query="Find functions",
                query_type=QueryType.NATURAL_LANGUAGE,
                parameters={"param": "value"},
            )

            # Parameters should be passed through to manager
            mock_manager.execute_query.assert_called_once_with(
                graph_id="test-graph",
                query="MATCH (n) RETURN n",
                parameters={"param": "value"},
            )


@pytest.mark.asyncio
async def test_execute_query_database_error():
    """Test handling database errors during query execution."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage_dir = Path(tmp_dir)

        with (
            patch.object(Path, "mkdir"),
            patch(
                "shotgun.codebase.service.CodebaseGraphManager"
            ) as mock_manager_class,
        ):
            mock_manager = Mock()
            mock_manager.execute_query = AsyncMock(
                side_effect=Exception("Database connection failed")
            )
            mock_manager_class.return_value = mock_manager

            service = CodebaseService(storage_dir)

            with patch(
                "shotgun.codebase.service.time.time",
                side_effect=[1000.0, 1000.1, 1000.2, 1000.3, 1000.4, 1001.0],
            ):
                result = await service.execute_query(
                    graph_id="test-graph",
                    query="MATCH (n) RETURN n",
                    query_type=QueryType.CYPHER,
                )

            assert result.success is False
            assert result.error == "Database connection failed"
            assert result.results == []
            assert result.row_count == 0
            assert abs(result.execution_time_ms - 100.0) < 0.01


@pytest.mark.asyncio
async def test_execute_query_cypher_generation_error():
    """Test handling errors during Cypher generation."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage_dir = Path(tmp_dir)

        with (
            patch.object(Path, "mkdir"),
            patch(
                "shotgun.codebase.service.CodebaseGraphManager"
            ) as mock_manager_class,
            patch("shotgun.codebase.service.generate_cypher") as mock_generate_cypher,
        ):
            mock_manager_class.return_value = Mock()
            mock_generate_cypher.side_effect = Exception("Cypher generation failed")

            service = CodebaseService(storage_dir)

            with patch(
                "shotgun.codebase.service.time.time",
                side_effect=[1000.0, 1000.1, 1000.2, 1000.3, 1000.4, 1001.0],
            ):
                result = await service.execute_query(
                    graph_id="test-graph",
                    query="Invalid natural language query",
                    query_type=QueryType.NATURAL_LANGUAGE,
                )

            assert result.success is False
            assert result.error == "Cypher generation failed"
            assert result.cypher_query is None


@pytest.mark.asyncio
async def test_execute_query_empty_results():
    """Test executing query that returns no results."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage_dir = Path(tmp_dir)

        with (
            patch.object(Path, "mkdir"),
            patch(
                "shotgun.codebase.service.CodebaseGraphManager"
            ) as mock_manager_class,
        ):
            mock_manager = Mock()
            mock_manager.execute_query = AsyncMock(return_value=[])
            mock_manager_class.return_value = mock_manager

            service = CodebaseService(storage_dir)

            result = await service.execute_query(
                graph_id="test-graph",
                query="MATCH (n:NonExistentType) RETURN n",
                query_type=QueryType.CYPHER,
            )

            assert result.success is True
            assert result.results == []
            assert result.row_count == 0
            assert result.column_names == []


def test_query_type_enum():
    """Test QueryType enum values."""
    assert QueryType.NATURAL_LANGUAGE == "natural_language"
    assert QueryType.CYPHER == "cypher"


def test_query_result_model():
    """Test QueryResult model creation."""
    result = QueryResult(
        query="MATCH (n) RETURN n",
        cypher_query=None,
        results=[{"n.name": "test"}],
        column_names=["n.name"],
        row_count=1,
        execution_time_ms=100.0,
        success=True,
        error=None,
    )

    assert result.query == "MATCH (n) RETURN n"
    assert result.row_count == 1
    assert result.success is True
    assert result.error is None


def test_query_result_model_with_error():
    """Test QueryResult model with error state."""
    result = QueryResult(
        query="INVALID QUERY",
        cypher_query=None,
        results=[],
        column_names=[],
        row_count=0,
        execution_time_ms=50.0,
        success=False,
        error="Syntax error in query",
    )

    assert result.success is False
    assert result.error == "Syntax error in query"
    assert result.results == []


@pytest.mark.asyncio
async def test_service_error_propagation():
    """Test that manager errors are properly propagated."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage_dir = Path(tmp_dir)

        with (
            patch.object(Path, "mkdir"),
            patch(
                "shotgun.codebase.service.CodebaseGraphManager"
            ) as mock_manager_class,
        ):
            mock_manager = Mock()
            mock_manager.build_graph = AsyncMock(
                side_effect=ValueError("Invalid repository path")
            )
            mock_manager_class.return_value = mock_manager

            service = CodebaseService(storage_dir)

            with pytest.raises(ValueError, match="Invalid repository path"):
                await service.create_graph("/invalid/path", "Test Graph")


@pytest.mark.asyncio
async def test_concurrent_queries():
    """Test handling concurrent queries."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage_dir = Path(tmp_dir)

        with (
            patch.object(Path, "mkdir"),
            patch(
                "shotgun.codebase.service.CodebaseGraphManager"
            ) as mock_manager_class,
        ):
            mock_manager = Mock()
            mock_manager.execute_query = AsyncMock(
                return_value=[{"result": "concurrent"}]
            )
            mock_manager_class.return_value = mock_manager

            service = CodebaseService(storage_dir)

            # Execute multiple queries concurrently
            import asyncio

            tasks = [
                service.execute_query("graph-1", "QUERY 1", QueryType.CYPHER),
                service.execute_query("graph-2", "QUERY 2", QueryType.CYPHER),
                service.execute_query("graph-3", "QUERY 3", QueryType.CYPHER),
            ]

            results = await asyncio.gather(*tasks)

            assert len(results) == 3
            assert all(result.success for result in results)
            assert mock_manager.execute_query.call_count == 3


def test_service_directory_creation():
    """Test that storage directory is created during initialization."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage_dir = tmp_dir

        with (
            patch.object(Path, "mkdir") as mock_mkdir,
            patch("shotgun.codebase.service.CodebaseGraphManager"),
        ):
            service = CodebaseService(storage_dir)

            mock_mkdir.assert_called_once_with(exist_ok=True)
            assert service.storage_dir == Path(storage_dir)


@pytest.mark.asyncio
async def test_query_timing_accuracy():
    """Test that query timing is measured accurately."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage_dir = Path(tmp_dir)

        with (
            patch.object(Path, "mkdir"),
            patch(
                "shotgun.codebase.service.CodebaseGraphManager"
            ) as mock_manager_class,
        ):
            mock_manager = Mock()

            # Simulate a query that takes some time
            async def slow_query(*args, **kwargs):
                import asyncio

                await asyncio.sleep(0.1)  # 100ms delay
                return [{"result": "slow"}]

            mock_manager.execute_query = AsyncMock(side_effect=slow_query)
            mock_manager_class.return_value = mock_manager

            service = CodebaseService(storage_dir)

            result = await service.execute_query(
                "test-graph", "SLOW QUERY", QueryType.CYPHER
            )

            # Should measure actual execution time (approximately 100ms)
            assert result.execution_time_ms >= 100
