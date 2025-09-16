"""Integration tests for query_graph codebase tool."""

import pytest
from pydantic_ai import RunContext

from shotgun.agents.models import AgentDeps
from shotgun.agents.tools.codebase import query_graph
from shotgun.codebase.models import CodebaseGraph


@pytest.mark.integration
@pytest.mark.llm
@pytest.mark.asyncio
async def test_query_graph_basic_smoke(
    indexed_graph: CodebaseGraph,
    run_context: RunContext[AgentDeps],
):
    """Smoke test for basic natural language queries."""
    # Test a simple query about classes
    result = await query_graph(
        ctx=run_context,
        graph_id=indexed_graph.graph_id,
        query="What classes are in this codebase?",
    )

    # Smoke test assertions - just verify it works
    assert result.success is True
    assert result.query == "What classes are in this codebase?"
    assert result.cypher_query is not None
    assert len(result.cypher_query) > 0
    assert result.column_names is not None
    assert result.results is not None

    # Verify string representation works
    result_str = str(result)
    assert isinstance(result_str, str)
    assert len(result_str) > 0
    # Should contain some indication of classes found
    assert "Calculator" in result_str or "class" in result_str.lower()


@pytest.mark.integration
@pytest.mark.llm
@pytest.mark.asyncio
async def test_query_graph_function_search(
    indexed_graph: CodebaseGraph,
    run_context: RunContext[AgentDeps],
):
    """Test querying for functions in the codebase."""
    result = await query_graph(
        ctx=run_context,
        graph_id=indexed_graph.graph_id,
        query="Find all functions that calculate something",
    )

    # Smoke test assertions
    assert result.success is True
    assert result.query == "Find all functions that calculate something"
    assert result.cypher_query is not None
    assert result.results is not None

    # Should find some calculation functions
    result_str = str(result)
    assert any(
        func in result_str for func in ["calculate", "add", "subtract", "multiply"]
    )


@pytest.mark.integration
@pytest.mark.llm
@pytest.mark.asyncio
async def test_query_graph_method_search(
    indexed_graph: CodebaseGraph,
    run_context: RunContext[AgentDeps],
):
    """Test querying for methods in classes."""
    result = await query_graph(
        ctx=run_context,
        graph_id=indexed_graph.graph_id,
        query="Show me methods in the Calculator class",
    )

    # Smoke test assertions
    assert result.success is True
    assert result.cypher_query is not None
    assert result.results is not None

    # Should find Calculator methods
    result_str = str(result)
    assert "Calculator" in result_str
    assert any(method in result_str for method in ["add", "subtract", "multiply"])


@pytest.mark.integration
@pytest.mark.asyncio
async def test_query_graph_invalid_graph_id(
    run_context: RunContext[AgentDeps],
):
    """Test querying with invalid graph ID."""
    result = await query_graph(
        ctx=run_context,
        graph_id="nonexistent-graph-id",
        query="What classes are in this codebase?",
    )

    # Should fail gracefully
    assert result.success is False
    assert result.error is not None
    assert "not found" in result.error.lower() or "nonexistent" in result.error.lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_query_graph_no_codebase_service(
    indexed_graph: CodebaseGraph,
):
    """Test querying when no codebase service is available."""

    # Create run context without codebase service
    class MockRunContextNoService:
        def __init__(self):
            self.deps = type("MockDeps", (), {"codebase_service": None})()

    context = MockRunContextNoService()

    result = await query_graph(
        ctx=context,
        graph_id=indexed_graph.graph_id,
        query="What classes are in this codebase?",
    )

    # Should fail gracefully
    assert result.success is False
    assert result.error is not None
    assert "codebase service" in result.error.lower()


@pytest.mark.integration
@pytest.mark.llm
@pytest.mark.asyncio
async def test_query_graph_empty_query(
    indexed_graph: CodebaseGraph,
    run_context: RunContext[AgentDeps],
):
    """Test querying with empty or minimal query."""
    result = await query_graph(
        ctx=run_context, graph_id=indexed_graph.graph_id, query=""
    )

    # Should handle gracefully (may succeed or fail depending on LLM)
    assert result.query == ""
    assert isinstance(result.success, bool)
    if not result.success:
        assert result.error is not None


@pytest.mark.integration
@pytest.mark.llm
@pytest.mark.asyncio
async def test_query_graph_complex_query(
    indexed_graph: CodebaseGraph,
    run_context: RunContext[AgentDeps],
):
    """Test a more complex natural language query."""
    result = await query_graph(
        ctx=run_context,
        graph_id=indexed_graph.graph_id,
        query="Find classes that inherit from Calculator and show their methods",
    )

    # Smoke test assertions
    assert result.success is True
    assert result.cypher_query is not None
    assert result.results is not None

    # Should find ScientificCalculator
    result_str = str(result)
    assert (
        "Scientific" in result_str
        or "power" in result_str
        or "square_root" in result_str
    )


@pytest.mark.integration
@pytest.mark.llm
@pytest.mark.asyncio
async def test_query_graph_string_representation(
    indexed_graph: CodebaseGraph,
    run_context: RunContext[AgentDeps],
):
    """Test that string representation of results is well-formatted."""
    result = await query_graph(
        ctx=run_context,
        graph_id=indexed_graph.graph_id,
        query="List all classes and functions",
    )

    assert result.success is True

    # Test string representation
    result_str = str(result)
    assert isinstance(result_str, str)
    assert len(result_str) > 0

    # Should contain query execution information
    # The query itself is only shown in error cases, not success cases
    assert "Generated Cypher" in result_str or "Results" in result_str

    # Should contain results in a readable format
    assert "Results" in result_str

    # Should not contain raw data structures
    assert "column_names:" not in result_str
    assert "results:" not in result_str
