"""Codebase SDK for framework-agnostic business logic."""

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path

from shotgun.codebase.models import CodebaseGraph, QueryType

from .exceptions import CodebaseNotFoundError, InvalidPathError
from .models import (
    DeleteResult,
    IndexResult,
    InfoResult,
    ListResult,
    QueryCommandResult,
    ReindexResult,
)
from .services import get_codebase_service


class CodebaseSDK:
    """Framework-agnostic SDK for codebase operations.

    This SDK provides business logic for codebase management that can be
    used by both CLI and TUI implementations without framework dependencies.
    """

    def __init__(self, storage_dir: Path | None = None):
        """Initialize SDK with optional storage directory.

        Args:
            storage_dir: Optional custom storage directory.
                        Defaults to ~/.shotgun-sh/codebases/
        """
        self.service = get_codebase_service(storage_dir)

    async def list_codebases(self) -> ListResult:
        """List all indexed codebases.

        Returns:
            ListResult containing list of codebases
        """
        graphs = await self.service.list_graphs()
        return ListResult(graphs=graphs)

    async def index_codebase(self, path: Path, name: str) -> IndexResult:
        """Index a new codebase.

        Args:
            path: Path to the repository to index
            name: Human-readable name for the codebase

        Returns:
            IndexResult with indexing details

        Raises:
            InvalidPathError: If the path does not exist
        """
        resolved_path = path.resolve()
        if not resolved_path.exists():
            raise InvalidPathError(f"Path does not exist: {resolved_path}")

        graph = await self.service.create_graph(resolved_path, name)
        file_count = sum(graph.language_stats.values()) if graph.language_stats else 0

        return IndexResult(
            graph_id=graph.graph_id,
            name=name,
            repo_path=str(resolved_path),
            file_count=file_count,
            node_count=graph.node_count,
            relationship_count=graph.relationship_count,
        )

    async def delete_codebase(
        self,
        graph_id: str,
        confirm_callback: Callable[[CodebaseGraph], bool]
        | Callable[[CodebaseGraph], Awaitable[bool]]
        | None = None,
    ) -> DeleteResult:
        """Delete a codebase with optional confirmation.

        Args:
            graph_id: ID of the graph to delete
            confirm_callback: Optional callback for confirmation.
                            Can be sync or async function that receives
                            the CodebaseGraph object and returns boolean.

        Returns:
            DeleteResult indicating success, failure, or cancellation

        Raises:
            CodebaseNotFoundError: If the graph is not found
        """
        graph = await self.service.get_graph(graph_id)
        if not graph:
            raise CodebaseNotFoundError(f"Graph not found: {graph_id}")

        # Handle confirmation callback if provided
        if confirm_callback:
            if asyncio.iscoroutinefunction(confirm_callback):
                confirmed = await confirm_callback(graph)
            else:
                confirmed = confirm_callback(graph)

            if not confirmed:
                return DeleteResult(
                    graph_id=graph_id,
                    name=graph.name,
                    deleted=False,
                    cancelled=True,
                )

        await self.service.delete_graph(graph_id)
        return DeleteResult(
            graph_id=graph_id,
            name=graph.name,
            deleted=True,
            cancelled=False,
        )

    async def get_info(self, graph_id: str) -> InfoResult:
        """Get detailed information about a codebase.

        Args:
            graph_id: ID of the graph to get info for

        Returns:
            InfoResult with detailed graph information

        Raises:
            CodebaseNotFoundError: If the graph is not found
        """
        graph = await self.service.get_graph(graph_id)
        if not graph:
            raise CodebaseNotFoundError(f"Graph not found: {graph_id}")

        return InfoResult(graph=graph)

    async def query_codebase(
        self, graph_id: str, query_text: str, query_type: QueryType
    ) -> QueryCommandResult:
        """Query a codebase using natural language or Cypher.

        Args:
            graph_id: ID of the graph to query
            query_text: Query text (natural language or Cypher)
            query_type: Type of query (NATURAL_LANGUAGE or CYPHER)

        Returns:
            QueryCommandResult with query results

        Raises:
            CodebaseNotFoundError: If the graph is not found
        """
        graph = await self.service.get_graph(graph_id)
        if not graph:
            raise CodebaseNotFoundError(f"Graph not found: {graph_id}")

        query_result = await self.service.execute_query(
            graph_id, query_text, query_type
        )

        return QueryCommandResult(
            graph_name=graph.name,
            query_type="Cypher"
            if query_type == QueryType.CYPHER
            else "natural language",
            result=query_result,
        )

    async def reindex_codebase(self, graph_id: str) -> ReindexResult:
        """Reindex an existing codebase.

        Args:
            graph_id: ID of the graph to reindex

        Returns:
            ReindexResult with reindexing details

        Raises:
            CodebaseNotFoundError: If the graph is not found
        """
        graph = await self.service.get_graph(graph_id)
        if not graph:
            raise CodebaseNotFoundError(f"Graph not found: {graph_id}")

        stats = await self.service.reindex_graph(graph_id)

        return ReindexResult(
            graph_id=graph_id,
            name=graph.name,
            stats=stats,
        )
