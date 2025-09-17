"""High-level service for managing codebase graphs and executing queries."""

import time
from pathlib import Path
from typing import Any

from shotgun.codebase.core.manager import CodebaseGraphManager
from shotgun.codebase.core.nl_query import generate_cypher
from shotgun.codebase.models import CodebaseGraph, QueryResult, QueryType
from shotgun.logging_config import get_logger

logger = get_logger(__name__)


class CodebaseService:
    """High-level service for codebase graph management and querying."""

    def __init__(self, storage_dir: Path | str):
        """Initialize the service.

        Args:
            storage_dir: Directory to store graph databases
        """
        if isinstance(storage_dir, str):
            storage_dir = Path(storage_dir)

        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.manager = CodebaseGraphManager(storage_dir)

    async def list_graphs(self) -> list[CodebaseGraph]:
        """List all existing graphs.

        Returns:
            List of CodebaseGraph objects
        """
        return await self.manager.list_graphs()

    async def create_graph(self, repo_path: str | Path, name: str) -> CodebaseGraph:
        """Create and index a new graph from a repository.

        Args:
            repo_path: Path to the repository to index
            name: Human-readable name for the graph

        Returns:
            The created CodebaseGraph
        """
        return await self.manager.build_graph(str(repo_path), name)

    async def get_graph(self, graph_id: str) -> CodebaseGraph | None:
        """Get graph metadata by ID.

        Args:
            graph_id: Graph ID to retrieve

        Returns:
            CodebaseGraph object or None if not found
        """
        return await self.manager.get_graph(graph_id)

    async def delete_graph(self, graph_id: str) -> None:
        """Delete a graph and its data.

        Args:
            graph_id: Graph ID to delete
        """
        await self.manager.delete_graph(graph_id)

    async def reindex_graph(self, graph_id: str) -> dict[str, Any]:
        """Rebuild an existing graph (full reindex).

        Args:
            graph_id: Graph ID to reindex

        Returns:
            Statistics from the reindex operation
        """
        return await self.manager.update_graph_incremental(graph_id)

    async def execute_query(
        self,
        graph_id: str,
        query: str,
        query_type: QueryType,
        parameters: dict[str, Any] | None = None,
    ) -> QueryResult:
        """Execute a query against a graph.

        Args:
            graph_id: Graph ID to query
            query: The query (natural language or Cypher)
            query_type: Type of query being executed
            parameters: Optional parameters for Cypher queries

        Returns:
            QueryResult with results and metadata
        """
        start_time = time.time()
        cypher_query = None

        try:
            # Handle query type conversion
            if query_type == QueryType.NATURAL_LANGUAGE:
                logger.info(f"Converting natural language query to Cypher: {query}")
                cypher_query = await generate_cypher(query)
                logger.info(f"Generated Cypher: {cypher_query}")
                execute_query = cypher_query
            else:
                execute_query = query

            # Execute the query
            results = await self.manager.execute_query(
                graph_id=graph_id, query=execute_query, parameters=parameters
            )

            # Extract column names from first result
            column_names = list(results[0].keys()) if results else []

            execution_time = (time.time() - start_time) * 1000

            return QueryResult(
                query=query,
                cypher_query=cypher_query
                if query_type == QueryType.NATURAL_LANGUAGE
                else None,
                results=results,
                column_names=column_names,
                row_count=len(results),
                execution_time_ms=execution_time,
                success=True,
                error=None,
            )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(f"Query execution failed: {e}")

            return QueryResult(
                query=query,
                cypher_query=cypher_query,
                results=[],
                column_names=[],
                row_count=0,
                execution_time_ms=execution_time,
                success=False,
                error=str(e),
            )
