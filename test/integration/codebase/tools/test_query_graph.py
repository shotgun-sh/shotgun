"""Integration tests for query_graph codebase tool."""

import pytest
from pydantic_ai import RunContext

from shotgun.agents.models import AgentDeps
from shotgun.agents.tools.codebase import query_graph
from shotgun.codebase.models import CodebaseGraph


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
