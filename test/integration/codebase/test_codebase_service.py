"""Integration tests for CodebaseService.

These tests create actual graphs, execute real LLM queries, and test the complete flow.
They require proper configuration and may take longer to run.
"""

import pytest

from shotgun.codebase import CodebaseService, QueryType
from shotgun.codebase.models import GraphStatus


@pytest.mark.integration
@pytest.mark.asyncio
async def test_service_initialization(service: CodebaseService):
    """Test that CodebaseService initializes correctly."""
    assert service is not None
    assert service.storage_dir.exists()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_graphs_empty(service: CodebaseService):
    """Test listing graphs when none exist."""
    graphs = await service.list_graphs()
    assert graphs == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_graph(service: CodebaseService, simple_python_codebase):
    """Test creating a graph from a codebase."""
    graph = await service.create_graph(simple_python_codebase, "Test Simple Graph")

    assert graph is not None
    assert graph.name == "Test Simple Graph"
    assert graph.status == GraphStatus.READY
    assert graph.node_count > 0
    assert graph.relationship_count > 0

    # Verify graph appears in list
    graphs = await service.list_graphs()
    assert len(graphs) == 1
    assert graphs[0].graph_id == graph.graph_id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_graph(service: CodebaseService, calculator_codebase):
    """Test retrieving graph metadata."""
    # Create a graph first
    created_graph = await service.create_graph(
        calculator_codebase, "Test Calculator Graph"
    )

    # Retrieve it
    retrieved_graph = await service.get_graph(created_graph.graph_id)

    assert retrieved_graph is not None
    assert retrieved_graph.graph_id == created_graph.graph_id
    assert retrieved_graph.name == created_graph.name
    assert retrieved_graph.status == GraphStatus.READY


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_nonexistent_graph(service: CodebaseService):
    """Test retrieving a graph that doesn't exist."""
    result = await service.get_graph("nonexistent_id")
    assert result is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cypher_query_execution(service: CodebaseService, calculator_codebase):
    """Test executing a direct Cypher query."""
    # Create a graph
    graph = await service.create_graph(calculator_codebase, "Cypher Test Graph")

    # Execute a simple Cypher query
    query = "MATCH (c:Class) RETURN c.name AS name, c.qualified_name AS qualified_name ORDER BY c.name"
    result = await service.execute_query(graph.graph_id, query, QueryType.CYPHER)

    assert result.success is True
    assert result.error is None
    assert result.query == query
    assert result.cypher_query is None  # Should be None for direct Cypher
    assert result.row_count > 0
    assert "name" in result.column_names
    assert "qualified_name" in result.column_names
    assert result.execution_time_ms > 0

    # Verify we found our test classes
    class_names = [row["name"] for row in result.results]
    assert "Calculator" in class_names
    assert "ScientificCalculator" in class_names
    assert "MathConstants" in class_names


@pytest.mark.integration
@pytest.mark.llm
@pytest.mark.asyncio
async def test_natural_language_query_execution(
    service: CodebaseService, calculator_codebase
):
    """Test executing a natural language query."""
    # Create a graph
    graph = await service.create_graph(calculator_codebase, "NL Test Graph")

    # Execute a natural language query
    nl_query = "Show me all the classes in the codebase"
    result = await service.execute_query(
        graph.graph_id, nl_query, QueryType.NATURAL_LANGUAGE
    )

    assert result.success is True
    assert result.error is None
    assert result.query == nl_query
    assert result.cypher_query is not None  # Should contain generated Cypher
    assert "MATCH" in result.cypher_query.upper()
    assert "CLASS" in result.cypher_query.upper()
    assert result.row_count > 0
    assert result.execution_time_ms > 0

    # Verify we found our test classes
    assert any("Calculator" in str(row) for row in result.results)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_function_query(service: CodebaseService, calculator_codebase):
    """Test querying for functions."""
    # Create a graph
    graph = await service.create_graph(calculator_codebase, "Function Test Graph")

    # Test Cypher query for functions
    query = "MATCH (f:Function) RETURN f.name AS name, f.qualified_name AS qualified_name ORDER BY f.name LIMIT 10"
    result = await service.execute_query(graph.graph_id, query, QueryType.CYPHER)

    assert result.success is True
    assert result.row_count > 0

    # Verify we found our test functions
    function_names = [row["name"] for row in result.results]
    assert "test_validation" in function_names


@pytest.mark.integration
@pytest.mark.llm
@pytest.mark.asyncio
async def test_method_query(service: CodebaseService, calculator_codebase):
    """Test querying for methods."""
    # Create a graph
    graph = await service.create_graph(calculator_codebase, "Method Test Graph")

    # Test natural language query for methods
    nl_query = "What methods does the Calculator class have?"
    result = await service.execute_query(
        graph.graph_id, nl_query, QueryType.NATURAL_LANGUAGE
    )

    assert result.success is True
    assert result.row_count > 0

    # Verify we found Calculator methods
    method_names = [row.get("name", "") for row in result.results]
    assert "add" in method_names
    assert "subtract" in method_names


@pytest.mark.integration
@pytest.mark.llm
@pytest.mark.asyncio
async def test_search_query(service: CodebaseService, calculator_codebase):
    """Test searching with natural language."""
    # Create a graph
    graph = await service.create_graph(calculator_codebase, "Search Test Graph")

    # Test search for test functions
    nl_query = "Find all functions that start with test"
    result = await service.execute_query(
        graph.graph_id, nl_query, QueryType.NATURAL_LANGUAGE
    )

    assert result.success is True
    if result.row_count > 0:
        # Verify all results are test functions
        for row in result.results:
            name = row.get("name", "")
            assert name.startswith("test")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_invalid_cypher_query(service: CodebaseService, simple_python_codebase):
    """Test error handling with invalid Cypher query."""
    # Create a graph
    graph = await service.create_graph(simple_python_codebase, "Error Test Graph")

    # Execute invalid Cypher query
    invalid_query = "INVALID CYPHER SYNTAX"
    result = await service.execute_query(
        graph.graph_id, invalid_query, QueryType.CYPHER
    )

    assert result.success is False
    assert result.error is not None
    assert "Parser exception" in result.error or "syntax" in result.error.lower()
    assert result.row_count == 0
    assert result.results == []
    assert result.execution_time_ms > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_query_nonexistent_graph(service: CodebaseService):
    """Test querying a graph that doesn't exist."""
    query = "MATCH (n) RETURN n LIMIT 1"
    result = await service.execute_query("nonexistent_id", query, QueryType.CYPHER)

    assert result.success is False
    assert result.error is not None
    assert "not found" in result.error.lower() or "graph" in result.error.lower()


@pytest.mark.integration
@pytest.mark.llm
@pytest.mark.skip(
    reason="Flaky test - natural language query generation is inconsistent"
)
@pytest.mark.slow
@pytest.mark.asyncio
async def test_complex_natural_language_query(
    service: CodebaseService, calculator_codebase
):
    """Test a more complex natural language query."""
    # Create a graph
    graph = await service.create_graph(calculator_codebase, "Complex Query Test Graph")

    # Test complex query
    nl_query = "Find all methods in classes that inherit from Calculator"
    result = await service.execute_query(
        graph.graph_id, nl_query, QueryType.NATURAL_LANGUAGE
    )

    # This should find methods in ScientificCalculator
    assert result.success is True
    if result.row_count > 0:
        # Verify we found scientific calculator methods
        method_names = [row.get("name", "") for row in result.results]
        assert any(name in ["power"] for name in method_names)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_graph(service: CodebaseService, simple_python_codebase):
    """Test deleting a graph."""
    # Create a graph
    graph = await service.create_graph(simple_python_codebase, "Delete Test Graph")

    # Verify it exists
    graphs = await service.list_graphs()
    assert len(graphs) == 1

    # Delete it
    await service.delete_graph(graph.graph_id)

    # Verify it's gone
    graphs = await service.list_graphs()
    assert len(graphs) == 0

    # Verify we can't retrieve it
    retrieved = await service.get_graph(graph.graph_id)
    assert retrieved is None


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_reindex_graph(service: CodebaseService, calculator_codebase):
    """Test reindexing a graph."""
    # Create a graph
    graph = await service.create_graph(calculator_codebase, "Reindex Test Graph")

    # Reindex it
    stats = await service.reindex_graph(graph.graph_id)

    assert stats is not None
    assert isinstance(stats, dict)

    # Verify the graph still exists and was updated
    updated_graph = await service.get_graph(graph.graph_id)
    assert updated_graph is not None
    assert updated_graph.status == GraphStatus.READY


@pytest.mark.integration
@pytest.mark.asyncio
async def test_multiple_graphs(
    service: CodebaseService, simple_python_codebase, calculator_codebase
):
    """Test managing multiple graphs."""
    # Create multiple graphs
    graph1 = await service.create_graph(simple_python_codebase, "Graph 1")
    graph2 = await service.create_graph(calculator_codebase, "Graph 2")

    # Verify both exist
    graphs = await service.list_graphs()
    assert len(graphs) == 2

    graph_names = {g.name for g in graphs}
    assert "Graph 1" in graph_names
    assert "Graph 2" in graph_names

    # Test queries on both
    query = "MATCH (c:Class) RETURN count(c) as count"

    result1 = await service.execute_query(graph1.graph_id, query, QueryType.CYPHER)
    result2 = await service.execute_query(graph2.graph_id, query, QueryType.CYPHER)

    assert result1.success is True
    assert result2.success is True

    # Graph 2 should have more classes than Graph 1
    count1 = result1.results[0]["count"] if result1.results else 0
    count2 = result2.results[0]["count"] if result2.results else 0
    assert count2 > count1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_query_performance_timing(
    service: CodebaseService, simple_python_codebase
):
    """Test that query timing is recorded accurately."""
    # Create a graph
    graph = await service.create_graph(simple_python_codebase, "Performance Test Graph")

    # Execute a simple query
    result = await service.execute_query(
        graph.graph_id, "MATCH (n) RETURN count(n) as total", QueryType.CYPHER
    )

    assert result.success is True
    assert result.execution_time_ms > 0
    # Execution time should be reasonable (less than 10 seconds)
    assert result.execution_time_ms < 10000


@pytest.mark.integration
@pytest.mark.asyncio
async def test_query_parameters(service: CodebaseService, calculator_codebase):
    """Test Cypher queries with parameters."""
    # Create a graph
    graph = await service.create_graph(calculator_codebase, "Parameters Test Graph")

    # Execute parameterized query
    query = "MATCH (c:Class) WHERE c.name = $class_name RETURN c.name AS name, c.qualified_name AS qualified_name"
    result = await service.execute_query(
        graph.graph_id, query, QueryType.CYPHER, parameters={"class_name": "Calculator"}
    )

    assert result.success is True
    assert result.row_count == 1
    assert result.results[0]["name"] == "Calculator"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_service_with_empty_codebase(service: CodebaseService, temp_storage_dir):
    """Test service behavior with an empty codebase."""
    # Create empty codebase
    empty_codebase = temp_storage_dir / "empty"
    empty_codebase.mkdir()

    # Should still create a graph, just with minimal content
    graph = await service.create_graph(empty_codebase, "Empty Graph")
    assert graph is not None
    assert graph.status == GraphStatus.READY

    # Queries should work but return no results
    result = await service.execute_query(
        graph.graph_id, "MATCH (c:Class) RETURN c.name", QueryType.CYPHER
    )
    assert result.success is True
    assert result.row_count == 0
