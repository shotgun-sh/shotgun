"""Tests for query_graph tool."""

import pytest

from shotgun.agents.tools.codebase import QueryGraphResult, query_graph
from shotgun.codebase.models import QueryResult


@pytest.mark.asyncio
async def test_query_graph_success(mock_run_context, mock_codebase_service):
    """Test successful graph query."""
    # Setup mock response
    query_result = QueryResult(
        query="test query",
        cypher_query="MATCH (n) RETURN n",
        results=[{"name": "TestClass", "type": "class"}],
        column_names=["name", "type"],
        row_count=1,
        execution_time_ms=50.0,
        success=True,
        error=None,
    )
    mock_codebase_service.execute_query.return_value = query_result

    # Execute
    result = await query_graph(mock_run_context, "graph-id", "test query")

    # Verify
    assert isinstance(result, QueryGraphResult)
    assert result.success is True
    assert result.query == "test query"
    assert result.cypher_query == "MATCH (n) RETURN n"
    assert result.row_count == 1
    assert "TestClass" in str(result)


@pytest.mark.asyncio
async def test_query_graph_no_service(mock_run_context):
    """Test query_graph with no codebase service."""
    mock_run_context.deps.codebase_service = None

    result = await query_graph(mock_run_context, "graph-id", "test query")

    assert isinstance(result, QueryGraphResult)
    assert result.success is False
    assert result.error and "No codebase indexed" in result.error


@pytest.mark.asyncio
async def test_query_graph_while_indexing(mock_run_context, mock_codebase_service):
    """Test query_graph returns error when graph is being indexed."""
    # Mark graph as currently being indexed
    mock_codebase_service.indexing.is_active.return_value = True

    result = await query_graph(mock_run_context, "graph-id", "test query")

    assert isinstance(result, QueryGraphResult)
    assert result.success is False
    assert result.error is not None
    assert "currently being indexed" in result.error
    # Verify execute_query was NOT called
    mock_codebase_service.execute_query.assert_not_called()
