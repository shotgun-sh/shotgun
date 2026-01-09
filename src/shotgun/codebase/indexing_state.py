"""State tracking for codebase indexing operations."""

import asyncio
from typing import ClassVar

from shotgun.logging_config import get_logger

logger = get_logger(__name__)


class IndexingState:
    """Tracks which graph_ids are currently being indexed.

    This is a simple state container that tools can check to determine
    if a graph is available or currently being built. This prevents
    race conditions on Windows where Kuzu uses exclusive file locking.

    Uses class-level state so all service instances share the same state.
    This is similar to how CodebaseGraphManager shares connections.
    """

    # Error message for when tools try to access a graph being indexed
    INDEXING_IN_PROGRESS_ERROR = (
        "This codebase is currently being indexed. "
        "Please wait for indexing to complete before accessing it."
    )

    # Class-level state shared across all instances
    _active_graphs: ClassVar[set[str]] = set()
    _lock: ClassVar[asyncio.Lock | None] = None

    @classmethod
    def _get_lock(cls) -> asyncio.Lock:
        """Get or create the class-level lock."""
        if cls._lock is None:
            cls._lock = asyncio.Lock()
        return cls._lock

    async def start(self, graph_id: str) -> None:
        """Mark a graph as being indexed.

        Args:
            graph_id: The graph ID that is starting to be indexed
        """
        lock = self._get_lock()
        async with lock:
            self._active_graphs.add(graph_id)
            logger.debug(f"Indexing started for graph: {graph_id}")

    async def complete(self, graph_id: str) -> None:
        """Mark a graph as finished indexing.

        Args:
            graph_id: The graph ID that finished indexing
        """
        lock = self._get_lock()
        async with lock:
            self._active_graphs.discard(graph_id)
            logger.debug(f"Indexing completed for graph: {graph_id}")

    def is_active(self, graph_id: str) -> bool:
        """Check if a specific graph is currently being indexed.

        Args:
            graph_id: The graph ID to check

        Returns:
            True if the graph is currently being indexed
        """
        return graph_id in self._active_graphs

    def has_active(self) -> bool:
        """Check if any graph is currently being indexed.

        Returns:
            True if any graph is being indexed
        """
        return len(self._active_graphs) > 0

    def get_active_ids(self) -> set[str]:
        """Get set of graph IDs currently being indexed.

        Returns:
            Copy of the set of graph IDs being indexed
        """
        return self._active_graphs.copy()
