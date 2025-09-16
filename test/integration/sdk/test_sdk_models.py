"""Integration tests for SDK result models.

Tests string representations and model behaviors with realistic data.
"""

import pytest

from shotgun.codebase.models import CodebaseGraph, GraphStatus, QueryResult
from shotgun.sdk.models import (
    DeleteResult,
    ErrorResult,
    IndexResult,
    InfoResult,
    ListResult,
    QueryCommandResult,
    ReindexResult,
)


@pytest.mark.integration
def test_list_result_empty():
    """Test ListResult string representation when empty."""
    result = ListResult(graphs=[])
    output = str(result)

    assert output == "No codebases found."


@pytest.mark.integration
def test_list_result_with_graphs():
    """Test ListResult string representation with graphs."""
    # Create sample graph data
    graph = CodebaseGraph(
        graph_id="test123",
        name="Test Graph",
        repo_path="/test/path",
        graph_path="/test/graph.db",
        created_at=1234567890.0,
        updated_at=1234567890.0,
        status=GraphStatus.READY,
        node_count=100,
        relationship_count=50,
        language_stats={"python": 5, "javascript": 3},
        last_operation=None,
        current_operation_id=None,
    )

    result = ListResult(graphs=[graph])
    output = str(result)

    # Verify output contains expected elements without exact matching
    assert len(output) > 0
    assert "test123" in output
    assert "Test Graph" in output
    assert "READY" in output
    assert "/test/path" in output


@pytest.mark.integration
def test_index_result_str():
    """Test IndexResult string representation."""
    result = IndexResult(
        graph_id="abc123",
        name="Test Index",
        repo_path="/path/to/repo",
        file_count=10,
        node_count=100,
        relationship_count=50,
    )

    output = str(result)

    assert "Successfully indexed codebase!" in output
    assert "abc123" in output
    assert "10" in output
    assert "100" in output
    assert "50" in output


@pytest.mark.integration
def test_delete_result_success():
    """Test DeleteResult for successful deletion."""
    result = DeleteResult(
        graph_id="delete123",
        name="Deleted Graph",
        deleted=True,
        cancelled=False,
    )

    output = str(result)

    assert "Successfully deleted codebase" in output
    assert "delete123" in output


@pytest.mark.integration
def test_delete_result_cancelled():
    """Test DeleteResult for cancelled deletion."""
    result = DeleteResult(
        graph_id="cancel123",
        name="Cancelled Graph",
        deleted=False,
        cancelled=True,
    )

    output = str(result)

    assert output == "Deletion cancelled."


@pytest.mark.integration
def test_delete_result_failed():
    """Test DeleteResult for failed deletion."""
    result = DeleteResult(
        graph_id="fail123",
        name="Failed Graph",
        deleted=False,
        cancelled=False,
    )

    output = str(result)

    assert "Failed to delete codebase" in output
    assert "fail123" in output


@pytest.mark.integration
def test_info_result_str():
    """Test InfoResult string representation."""
    graph = CodebaseGraph(
        graph_id="info123",
        name="Info Test Graph",
        repo_path="/info/path",
        graph_path="/info/graph.db",
        created_at=1234567890.0,
        updated_at=1234567890.0,
        status=GraphStatus.READY,
        node_count=200,
        relationship_count=150,
        language_stats={"python": 10, "javascript": 5},
        node_stats={"Class": 20, "Function": 100},
        relationship_stats={"CALLS": 80, "IMPORTS": 70},
        last_operation=None,
        current_operation_id=None,
    )

    result = InfoResult(graph=graph)
    output = str(result)

    # Verify key information is present
    assert "info123" in output
    assert "Info Test Graph" in output
    assert "READY" in output
    assert "/info/path" in output
    assert "200" in output
    assert "150" in output
    assert "Language Statistics:" in output
    assert "python: 10" in output
    assert "Node Statistics:" in output
    assert "Class: 20" in output
    assert "Relationship Statistics:" in output
    assert "CALLS: 80" in output


@pytest.mark.integration
def test_query_command_result_success():
    """Test QueryCommandResult with successful query."""
    query_result = QueryResult(
        query="MATCH (c:Class) RETURN c.name",
        cypher_query="MATCH (c:Class) RETURN c.name",
        error=None,
        results=[{"c.name": "TestClass"}, {"c.name": "AnotherClass"}],
        column_names=["c.name"],
        row_count=2,
        execution_time_ms=15.5,
        success=True,
    )

    result = QueryCommandResult(
        graph_name="Query Test",
        query_type="Cypher",
        result=query_result,
    )

    output = str(result)

    assert "Query executed in 15.50ms" in output
    assert "Results: 2 rows" in output
    assert "TestClass" in output
    assert "AnotherClass" in output
    assert "c.name" in output


@pytest.mark.integration
def test_query_command_result_failed():
    """Test QueryCommandResult with failed query."""
    query_result = QueryResult(
        query="INVALID QUERY",
        execution_time_ms=0.0,
        cypher_query=None,
        error="Syntax error",
        success=False,
    )

    result = QueryCommandResult(
        graph_name="Failed Query Test",
        query_type="Cypher",
        result=query_result,
    )

    output = str(result)

    assert "Query failed: Syntax error" in output


@pytest.mark.integration
def test_query_command_result_no_results():
    """Test QueryCommandResult with no results."""
    query_result = QueryResult(
        query="MATCH (x:NonExistent) RETURN x",
        execution_time_ms=5.0,
        cypher_query=None,
        error=None,
        success=True,
        results=[],
        row_count=0,
    )

    result = QueryCommandResult(
        graph_name="Empty Result Test",
        query_type="natural language",
        result=query_result,
    )

    output = str(result)

    assert "No results found." in output


@pytest.mark.integration
def test_reindex_result_str():
    """Test ReindexResult string representation."""
    result = ReindexResult(
        graph_id="reindex123",
        name="Reindexed Graph",
        stats={"nodes_updated": 50, "relationships_updated": 25},
    )

    output = str(result)

    assert "Reindexing completed!" in output
    assert "nodes_updated" in output
    assert "relationships_updated" in output


@pytest.mark.integration
def test_reindex_result_no_stats():
    """Test ReindexResult with no stats."""
    result = ReindexResult(
        graph_id="reindex_no_stats",
        name="No Stats Graph",
        stats=None,
    )

    output = str(result)

    assert "Reindexing completed!" in output
    assert output == "Reindexing completed!"


@pytest.mark.integration
def test_error_result_str():
    """Test ErrorResult string representation."""
    result = ErrorResult(
        error_message="Something went wrong",
        details="Detailed error information",
    )

    output = str(result)

    assert "Error: Something went wrong" in output
    assert "Detailed error information" in output


@pytest.mark.integration
def test_error_result_no_details():
    """Test ErrorResult with no details."""
    result = ErrorResult(
        error_message="Simple error",
        details=None,
    )

    output = str(result)

    assert output == "Error: Simple error"
