"""Path-based persistence utilities for code knowledge graphs.

This module provides utilities for managing graphs keyed by canonical codebase paths,
implementing the Stage 1 requirements for persistent per-path graph reuse.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from shotgun.codebase.models import CodebaseGraph
from shotgun.logging_config import get_logger

logger = get_logger(__name__)


def resolve_canonical_path(raw_path: str | Path) -> str:
    """Resolve a raw filesystem path to its canonical form.

    This function normalizes paths by:
    - Converting to absolute path
    - Resolving symlinks
    - Normalizing path separators (platform-specific)
    - Handling case sensitivity based on platform

    Args:
        raw_path: Raw filesystem path (absolute or relative)

    Returns:
        Canonical absolute path as a string

    Examples:
        >>> resolve_canonical_path("./my-project")
        "/Users/username/my-project"

        >>> resolve_canonical_path("/tmp/../var/log")
        "/var/log"
    """
    try:
        # Convert to Path object if string
        path = Path(raw_path)

        # Resolve to absolute path, following symlinks
        # This handles:
        # - Relative paths (./foo, ../bar)
        # - Symlinks (following them to their target)
        # - Path normalization (removing . and ..)
        canonical = path.resolve()

        # Convert to string with platform-appropriate separators
        return str(canonical)

    except (OSError, RuntimeError) as e:
        # Handle cases where path resolution fails
        # (e.g., too many symlink levels, permission errors)
        logger.warning(
            f"Failed to resolve path '{raw_path}': {e}. Using absolute path without symlink resolution."
        )
        # Fallback: just make it absolute without resolving symlinks
        return str(Path(raw_path).absolute())


def _generate_graph_id_from_path(canonical_path: str) -> str:
    """Generate deterministic graph ID from canonical path.

    Args:
        canonical_path: Canonical repository path

    Returns:
        12-character graph ID (SHA256 hash truncated)
    """
    return hashlib.sha256(canonical_path.encode()).hexdigest()[:12]


async def lookup_graph_for_path(
    canonical_path: str, manager: Any
) -> CodebaseGraph | None:
    """Look up an existing graph for a canonical codebase path.

    This enforces the single-graph-per-path invariant: at most one graph
    can exist for any given canonical path.

    Stage 5 Error Handling: If storage or lookup fails, this function treats
    it as "no existing graph" and returns None, allowing the caller to proceed
    with creating a new graph.

    Args:
        canonical_path: Canonical codebase path (from resolve_canonical_path)
        manager: CodebaseGraphManager instance

    Returns:
        CodebaseGraph if a saved graph exists for this path, None otherwise.
        Returns None if lookup fails due to storage errors.

    Examples:
        >>> canonical = resolve_canonical_path("/home/user/my-repo")
        >>> graph = await lookup_graph_for_path(canonical, manager)
        >>> if graph:
        ...     print(f"Found graph: {graph.name}")
        ... else:
        ...     print("No saved graph for this path")
    """
    # Generate deterministic graph ID from canonical path
    graph_id = _generate_graph_id_from_path(canonical_path)

    logger.debug(
        f"Looking up graph for path - canonical_path: {canonical_path}, graph_id: {graph_id}"
    )

    try:
        # Query the manager for this graph ID
        graph = await manager.get_graph(graph_id)

        if graph:
            logger.info(
                f"Found existing graph for path - path: {canonical_path}, graph_id: {graph_id}, name: {graph.name}"
            )
        else:
            logger.debug(f"No existing graph found for path - path: {canonical_path}")

        return graph

    except Exception as e:
        # Stage 5: Treat lookup/storage failures as "no existing graph"
        logger.warning(
            f"Failed to lookup graph for path '{canonical_path}' (graph_id: {graph_id}): {e}. "
            "Treating as no existing graph."
        )
        return None


async def create_graph_for_path(
    canonical_path: str,
    manager: Any,
    name: str | None = None,
    languages: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
    indexed_from_cwd: str | None = None,
    progress_callback: Any = None,
) -> CodebaseGraph:
    """Create a new graph bound to a canonical codebase path.

    If a graph already exists for this path, this will replace it by creating
    a new graph with the same graph ID (overwrite behavior).

    Args:
        canonical_path: Canonical codebase path (from resolve_canonical_path)
        manager: CodebaseGraphManager instance
        name: Optional human-readable name for the graph
        languages: Optional list of languages to index
        exclude_patterns: Optional list of patterns to exclude
        indexed_from_cwd: Optional working directory for access control
        progress_callback: Optional progress callback

    Returns:
        Newly created CodebaseGraph

    Raises:
        Exception: If graph creation fails

    Examples:
        >>> canonical = resolve_canonical_path("/home/user/my-repo")
        >>> graph = await create_graph_for_path(
        ...     canonical,
        ...     manager,
        ...     name="My Repository"
        ... )
        >>> print(f"Created graph: {graph.graph_id}")
    """
    # Verify the path exists
    path = Path(canonical_path)
    if not path.exists():
        raise ValueError(f"Path does not exist: {canonical_path}")

    if not path.is_dir():
        raise ValueError(f"Path is not a directory: {canonical_path}")

    # Generate graph ID - this ensures we have exactly one graph per path
    graph_id = _generate_graph_id_from_path(canonical_path)

    # Check if graph already exists
    existing_graph = await manager.get_graph(graph_id)
    if existing_graph:
        logger.warning(
            f"Graph already exists for path - path: {canonical_path}, graph_id: {graph_id}. "
            "Creating new graph will replace the existing one."
        )
        # Delete the existing graph to replace it
        await manager.delete_graph(graph_id)

    # Use path name as default graph name if not provided
    if name is None:
        name = path.name

    logger.info(
        f"Creating new graph for path - path: {canonical_path}, graph_id: {graph_id}, name: {name}"
    )

    # Build the graph using the manager
    graph = await manager.build_graph(
        repo_path=canonical_path,
        name=name,
        languages=languages,
        exclude_patterns=exclude_patterns,
        indexed_from_cwd=indexed_from_cwd,
        progress_callback=progress_callback,
    )

    logger.info(
        f"Successfully created graph for path - path: {canonical_path}, graph_id: {graph.graph_id}"
    )

    return graph
