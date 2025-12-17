"""Decision logic for persistent graph behavior when opening codebases.

This module implements Stage 2 of the persistent per-path graph reuse plan,
defining how global preferences govern behavior when opening a codebase path.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel

from shotgun.agents.config.models import PersistentGraphOpenBehavior
from shotgun.codebase.models import CodebaseGraph
from shotgun.logging_config import get_logger

logger = get_logger(__name__)


class GraphOpenAction(StrEnum):
    """Action to take when opening a codebase with respect to graph management."""

    REUSE = "reuse"  # Reuse existing graph
    NEW = "new"  # Create new graph
    ASK = "ask"  # Ask user (show modal)


class GraphOpenDecision(BaseModel):
    """Decision result for graph open action."""

    action: GraphOpenAction
    existing_graph: CodebaseGraph | None = None

    @property
    def should_reuse(self) -> bool:
        """Check if decision is to reuse existing graph."""
        return self.action == GraphOpenAction.REUSE

    @property
    def should_create_new(self) -> bool:
        """Check if decision is to create a new graph."""
        return self.action == GraphOpenAction.NEW

    @property
    def should_ask_user(self) -> bool:
        """Check if decision is to ask the user."""
        return self.action == GraphOpenAction.ASK


def decide_graph_open_action(
    canonical_path: str,
    global_behavior: PersistentGraphOpenBehavior,
    existing_graph: CodebaseGraph | None,
) -> GraphOpenDecision:
    """Decide what action to take when opening a codebase.

    Implements the Stage 2 decision flow that determines whether to reuse an
    existing graph, create a new one, or ask the user, based on the global
    preference setting and whether a graph exists for the path.

    Decision Logic:
    1. No existing graph → Always create NEW (no modal needed)
    2. Existing graph present:
       - ALWAYS_REUSE → Auto-load existing graph (REUSE)
       - ALWAYS_NEW → Create new graph (NEW)
       - ASK → Defer to modal (ASK)

    Args:
        canonical_path: Canonical codebase path (from resolve_canonical_path)
        global_behavior: User's global preference for persistent graph behavior
        existing_graph: Existing graph for this path, or None if not found

    Returns:
        GraphOpenDecision with action and optional existing_graph reference

    Examples:
        >>> # No existing graph - always create new
        >>> decision = decide_graph_open_action(
        ...     "/path/to/repo",
        ...     PersistentGraphOpenBehavior.ASK,
        ...     None
        ... )
        >>> assert decision.action == GraphOpenAction.NEW
        >>> assert decision.existing_graph is None

        >>> # Existing graph with ALWAYS_REUSE - reuse it
        >>> decision = decide_graph_open_action(
        ...     "/path/to/repo",
        ...     PersistentGraphOpenBehavior.ALWAYS_REUSE,
        ...     existing_graph
        ... )
        >>> assert decision.action == GraphOpenAction.REUSE
        >>> assert decision.existing_graph == existing_graph

        >>> # Existing graph with ASK - ask user
        >>> decision = decide_graph_open_action(
        ...     "/path/to/repo",
        ...     PersistentGraphOpenBehavior.ASK,
        ...     existing_graph
        ... )
        >>> assert decision.action == GraphOpenAction.ASK
        >>> assert decision.existing_graph == existing_graph
    """
    logger.debug(
        f"Deciding graph open action - path: {canonical_path}, "
        f"behavior: {global_behavior}, "
        f"has_existing: {existing_graph is not None}"
    )

    # Case 1: No existing graph - always create new
    if existing_graph is None:
        logger.info(
            f"No existing graph for path {canonical_path}, will create new graph"
        )
        return GraphOpenDecision(
            action=GraphOpenAction.NEW,
            existing_graph=None,
        )

    # Case 2: Existing graph present - apply global behavior
    if global_behavior == PersistentGraphOpenBehavior.ALWAYS_REUSE:
        logger.info(
            f"Global behavior is ALWAYS_REUSE, will reuse existing graph for {canonical_path}"
        )
        return GraphOpenDecision(
            action=GraphOpenAction.REUSE,
            existing_graph=existing_graph,
        )

    if global_behavior == PersistentGraphOpenBehavior.ALWAYS_NEW:
        logger.info(
            f"Global behavior is ALWAYS_NEW, will create new graph for {canonical_path}"
        )
        return GraphOpenDecision(
            action=GraphOpenAction.NEW,
            existing_graph=existing_graph,  # Include for potential cleanup
        )

    # Default: ASK behavior
    logger.info(
        f"Global behavior is ASK, will prompt user for decision on {canonical_path}"
    )
    return GraphOpenDecision(
        action=GraphOpenAction.ASK,
        existing_graph=existing_graph,
    )
