"""Query codebase knowledge graph using natural language."""

from pydantic_ai import RunContext

from shotgun.agents.models import AgentDeps
from shotgun.codebase.models import QueryType
from shotgun.logging_config import get_logger

from .models import QueryGraphResult

logger = get_logger(__name__)


async def query_graph(
    ctx: RunContext[AgentDeps], graph_id: str, query: str
) -> QueryGraphResult:
    """Query codebase knowledge graph using natural language.

    Args:
        ctx: RunContext containing AgentDeps with codebase service
        graph_id: Graph ID to query (use the ID, not the name)
        query: Natural language question about the codebase

    Returns:
        QueryGraphResult with formatted output via __str__
    """
    logger.debug("🔧 Querying graph %s with query: %s", graph_id, query)

    try:
        if not ctx.deps.codebase_service:
            return QueryGraphResult(
                success=False,
                query=query,
                error="No codebase indexed",
            )

        # Execute natural language query
        result = await ctx.deps.codebase_service.execute_query(
            graph_id=graph_id,
            query=query,
            query_type=QueryType.NATURAL_LANGUAGE,
        )

        # Create QueryGraphResult from service result
        graph_result = QueryGraphResult(
            success=result.success,
            query=query,
            cypher_query=result.cypher_query,
            column_names=result.column_names,
            results=result.results,
            row_count=result.row_count,
            execution_time_ms=result.execution_time_ms,
            error=result.error,
        )

        logger.debug(
            "📄 Query completed: %s with %d results",
            "success" if graph_result.success else "failed",
            graph_result.row_count,
        )

        return graph_result

    except Exception as e:
        error_msg = f"Error querying graph: {str(e)}"
        logger.error("❌ Query graph failed: %s", str(e))
        return QueryGraphResult(success=False, query=query, error=error_msg)
