"""High-level service for managing codebase graphs and executing queries."""

import time
from pathlib import Path
from typing import Any

from shotgun.codebase.core.cypher_models import CypherGenerationNotPossibleError
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

    async def list_graphs_for_directory(
        self, directory: Path | str | None = None
    ) -> list[CodebaseGraph]:
        """List graphs that match a specific directory.

        Args:
            directory: Directory to filter by. If None, uses current working directory.

        Returns:
            List of CodebaseGraph objects accessible from the specified directory
        """
        from pathlib import Path

        if directory is None:
            directory = Path.cwd()
        elif isinstance(directory, str):
            directory = Path(directory)

        # Resolve to absolute path for comparison
        target_path = str(directory.resolve())

        # Get all graphs and filter by those accessible from this directory
        all_graphs = await self.manager.list_graphs()
        filtered_graphs = []

        for graph in all_graphs:
            # If indexed_from_cwds is empty, it's globally accessible (backward compatibility)
            if not graph.indexed_from_cwds:
                filtered_graphs.append(graph)
            # Otherwise, check if current directory is in the allowed list
            elif target_path in graph.indexed_from_cwds:
                filtered_graphs.append(graph)
            # Also allow access if current directory IS the repository itself
            # Use Path.resolve() for robust comparison (handles symlinks, etc.)
            elif Path(target_path).resolve() == Path(graph.repo_path).resolve():
                filtered_graphs.append(graph)

        return filtered_graphs

    async def create_graph(
        self,
        repo_path: str | Path,
        name: str,
        indexed_from_cwd: str | None = None,
        progress_callback: Any | None = None,
    ) -> CodebaseGraph:
        """Create and index a new graph from a repository.

        Args:
            repo_path: Path to the repository to index
            name: Human-readable name for the graph
            indexed_from_cwd: Working directory from which indexing was initiated
            progress_callback: Optional callback for progress reporting

        Returns:
            The created CodebaseGraph
        """
        return await self.manager.build_graph(
            str(repo_path),
            name,
            indexed_from_cwd=indexed_from_cwd,
            progress_callback=progress_callback,
        )

    async def get_graph(self, graph_id: str) -> CodebaseGraph | None:
        """Get graph metadata by ID.

        Args:
            graph_id: Graph ID to retrieve

        Returns:
            CodebaseGraph object or None if not found
        """
        return await self.manager.get_graph(graph_id)

    async def add_cwd_access(self, graph_id: str, cwd: str | None = None) -> None:
        """Add a working directory to a graph's access list.

        Args:
            graph_id: Graph ID to update
            cwd: Working directory to add. If None, uses current working directory.
        """
        await self.manager.add_cwd_access(graph_id, cwd)

    async def remove_cwd_access(self, graph_id: str, cwd: str) -> None:
        """Remove a working directory from a graph's access list.

        Args:
            graph_id: Graph ID to update
            cwd: Working directory to remove
        """
        await self.manager.remove_cwd_access(graph_id, cwd)

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

        except CypherGenerationNotPossibleError as e:
            # Handle queries that cannot be converted to Cypher
            execution_time = (time.time() - start_time) * 1000
            logger.info(f"Query cannot be converted to Cypher: {e.reason}")

            return QueryResult(
                query=query,
                cypher_query=None,
                results=[],
                column_names=[],
                row_count=0,
                execution_time_ms=execution_time,
                success=False,
                error=f"This query cannot be converted to Cypher: {e.reason}",
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
