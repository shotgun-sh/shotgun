"""Integrated flow for opening codebases with Stage 1 and Stage 2 decision logic.

This module provides a high-level function that combines path canonicalization,
graph lookup, and decision logic to determine what action to take when opening
a codebase.
"""

from __future__ import annotations

from pathlib import Path

from shotgun.agents.config.manager import ConfigManager
from shotgun.agents.config.models import PersistentGraphOpenBehavior
from shotgun.codebase.core.manager import CodebaseGraphManager
from shotgun.codebase.graph_decision import GraphOpenDecision, decide_graph_open_action
from shotgun.codebase.persistence import lookup_graph_for_path, resolve_canonical_path
from shotgun.logging_config import get_logger

logger = get_logger(__name__)


async def determine_graph_action_for_codebase(
    codebase_path: str | Path,
    graph_manager: CodebaseGraphManager,
    config_manager: ConfigManager | None = None,
    global_behavior: PersistentGraphOpenBehavior | None = None,
) -> GraphOpenDecision:
    """Determine what action to take when opening a codebase.

    This function integrates Stage 1 (path canonicalization and lookup) and
    Stage 2 (decision logic based on global preference) to provide a complete
    flow for determining whether to reuse an existing graph, create a new one,
    or ask the user.

    Stage 5 Error Handling: Path resolution failures are handled gracefully by
    resolve_canonical_path (falls back to absolute path). Graph lookup failures
    are treated as "no existing graph" by lookup_graph_for_path.

    Args:
        codebase_path: Raw path to the codebase directory
        graph_manager: CodebaseGraphManager instance for graph operations
        config_manager: Optional ConfigManager to read user preferences.
                       If None, uses the global singleton.
        global_behavior: Optional override for global behavior. If provided,
                        uses this instead of reading from config.

    Returns:
        GraphOpenDecision with action (REUSE/NEW/ASK) and optional existing_graph.
        In case of lookup failures, returns decision with existing_graph=None.

    Examples:
        >>> # Basic usage with default config
        >>> manager = CodebaseGraphManager()
        >>> decision = await determine_graph_action_for_codebase(
        ...     "/path/to/repo",
        ...     manager
        ... )
        >>> if decision.should_reuse:
        ...     print(f"Reusing graph: {decision.existing_graph.graph_id}")
        >>> elif decision.should_create_new:
        ...     print("Creating new graph")
        >>> elif decision.should_ask_user:
        ...     print("Show modal to ask user")

        >>> # Override global behavior
        >>> decision = await determine_graph_action_for_codebase(
        ...     "./my-project",
        ...     manager,
        ...     global_behavior=PersistentGraphOpenBehavior.ALWAYS_REUSE
        ... )
    """
    # Stage 1: Path canonicalization (handles errors internally)
    canonical_path = resolve_canonical_path(codebase_path)
    logger.info(
        f"Determining graph action for codebase - raw_path: {codebase_path}, "
        f"canonical_path: {canonical_path}"
    )

    # Stage 1: Graph lookup (handles errors internally, returns None on failure)
    existing_graph = await lookup_graph_for_path(canonical_path, graph_manager)

    # Get global behavior if not provided
    if global_behavior is None:
        if config_manager is None:
            from shotgun.agents.config.manager import get_config_manager

            config_manager = get_config_manager()

        global_behavior = await config_manager.get_persistent_graph_behavior()
        logger.debug(f"Loaded global behavior from config: {global_behavior}")

    # Stage 2: Decision logic
    decision = decide_graph_open_action(canonical_path, global_behavior, existing_graph)

    logger.info(
        f"Decision made - action: {decision.action}, "
        f"has_existing_graph: {decision.existing_graph is not None}"
    )

    return decision
