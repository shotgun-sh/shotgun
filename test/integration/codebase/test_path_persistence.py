"""Integration tests for path-based graph persistence.

These tests validate the end-to-end flow of path canonicalization,
graph lookup by path, and graph creation bound to canonical paths.
"""

import tempfile
from pathlib import Path

import pytest

from shotgun.codebase.core.manager import CodebaseGraphManager
from shotgun.codebase.models import GraphStatus
from shotgun.codebase.persistence import (
    create_graph_for_path,
    lookup_graph_for_path,
    resolve_canonical_path,
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_end_to_end_path_canonicalization_and_lookup_without_api_key(tmp_path):
    """Test complete flow: canonicalize -> lookup -> create -> lookup again."""
    # Create a test codebase directory
    codebase_dir = tmp_path / "test_project"
    codebase_dir.mkdir()

    # Add a simple Python file
    (codebase_dir / "main.py").write_text(
        """
def hello():
    return "world"
"""
    )

    # Initialize manager with temporary storage
    manager = CodebaseGraphManager(tmp_path / "graphs")

    # Step 1: Resolve canonical path
    canonical_path = resolve_canonical_path(codebase_dir)
    assert Path(canonical_path).is_absolute()
    assert str(canonical_path) == str(codebase_dir.resolve())

    print(f"Canonical path: {canonical_path}")

    # Step 2: Lookup graph (should not exist initially)
    existing_graph = await lookup_graph_for_path(canonical_path, manager)
    assert existing_graph is None
    print(f"Initial lookup: No graph found (expected)")

    # Step 3: Create graph bound to canonical path
    created_graph = await create_graph_for_path(
        canonical_path, manager, name="Test Project"
    )
    assert created_graph is not None
    assert created_graph.name == "Test Project"
    assert created_graph.repo_path == canonical_path
    assert created_graph.status == GraphStatus.READY
    print(f"Created graph: {created_graph.graph_id}")

    # Step 4: Lookup graph again (should exist now)
    found_graph = await lookup_graph_for_path(canonical_path, manager)
    assert found_graph is not None
    assert found_graph.graph_id == created_graph.graph_id
    assert found_graph.repo_path == canonical_path
    print(f"Second lookup: Found graph {found_graph.graph_id}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_path_with_relative_references_without_api_key(tmp_path):
    """Test canonicalization with relative path references like .."""
    # Create nested directories
    base = tmp_path / "base"
    dir1 = base / "dir1"
    dir2 = base / "dir2"
    dir1.mkdir(parents=True)
    dir2.mkdir(parents=True)

    # Add a file to dir2
    (dir2 / "code.py").write_text("x = 1")

    # Create path with parent reference: dir1/../dir2
    relative_path = dir1 / ".." / "dir2"

    # Resolve canonical path
    canonical_path = resolve_canonical_path(relative_path)

    # Should resolve to dir2
    assert canonical_path == str(dir2.resolve())
    print(f"Resolved {relative_path} -> {canonical_path}")

    # Create graph and verify lookup works
    manager = CodebaseGraphManager(tmp_path / "graphs")
    created_graph = await create_graph_for_path(canonical_path, manager)

    # Lookup with different path representations should find the same graph
    found_via_canonical = await lookup_graph_for_path(canonical_path, manager)
    found_via_direct = await lookup_graph_for_path(str(dir2), manager)

    assert found_via_canonical is not None
    assert found_via_direct is not None
    assert found_via_canonical.graph_id == created_graph.graph_id
    assert found_via_direct.graph_id == created_graph.graph_id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_path_with_symlink_without_api_key(tmp_path):
    """Test canonicalization through symlinks."""
    # Create a real directory
    real_dir = tmp_path / "real_project"
    real_dir.mkdir()
    (real_dir / "app.py").write_text("app = 1")

    # Create a symlink to it
    symlink_dir = tmp_path / "symlink_project"

    # Skip test on systems that don't support symlinks
    try:
        symlink_dir.symlink_to(real_dir)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks not supported on this platform/filesystem")

    # Resolve both paths
    canonical_real = resolve_canonical_path(real_dir)
    canonical_symlink = resolve_canonical_path(symlink_dir)

    # Both should resolve to the same canonical path (the real directory)
    assert canonical_real == canonical_symlink
    print(f"Real path: {canonical_real}")
    print(f"Symlink path: {canonical_symlink}")

    # Create graph via symlink
    manager = CodebaseGraphManager(tmp_path / "graphs")
    created_graph = await create_graph_for_path(canonical_symlink, manager)

    # Lookup via real path should find the same graph
    found_graph = await lookup_graph_for_path(canonical_real, manager)
    assert found_graph is not None
    assert found_graph.graph_id == created_graph.graph_id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_single_graph_per_path_invariant_without_api_key(tmp_path):
    """Test that only one graph can exist per canonical path."""
    # Create a codebase
    codebase = tmp_path / "single_graph_test"
    codebase.mkdir()
    (codebase / "test.py").write_text("test = 1")

    canonical_path = resolve_canonical_path(codebase)
    manager = CodebaseGraphManager(tmp_path / "graphs")

    # Create first graph
    graph1 = await create_graph_for_path(
        canonical_path, manager, name="First Graph"
    )
    assert graph1.name == "First Graph"

    # Lookup should find first graph
    found = await lookup_graph_for_path(canonical_path, manager)
    assert found.graph_id == graph1.graph_id

    # Create second graph for same path (should replace first)
    graph2 = await create_graph_for_path(
        canonical_path, manager, name="Second Graph"
    )
    assert graph2.name == "Second Graph"

    # Lookup should now find second graph
    found = await lookup_graph_for_path(canonical_path, manager)
    assert found.graph_id == graph2.graph_id

    # Both graphs have the same ID (derived from path), so looking up graph1's ID
    # should return graph2's data (the replacement)
    graph1_lookup = await manager.get_graph(graph1.graph_id)
    assert graph1_lookup is not None
    assert graph1_lookup.name == "Second Graph"  # Should have graph2's name
    assert graph1.graph_id == graph2.graph_id  # Same ID (same path)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_multiple_different_paths_without_api_key(tmp_path):
    """Test that different paths create different graphs."""
    manager = CodebaseGraphManager(tmp_path / "graphs")

    # Create multiple codebases
    projects = []
    for i in range(3):
        project_dir = tmp_path / f"project_{i}"
        project_dir.mkdir()
        (project_dir / "code.py").write_text(f"x = {i}")

        canonical = resolve_canonical_path(project_dir)
        graph = await create_graph_for_path(
            canonical, manager, name=f"Project {i}"
        )
        projects.append((canonical, graph))

    # Verify each path has its own graph
    for canonical, created_graph in projects:
        found = await lookup_graph_for_path(canonical, manager)
        assert found is not None
        assert found.graph_id == created_graph.graph_id

    # Verify all graphs are distinct
    graph_ids = [g.graph_id for _, g in projects]
    assert len(graph_ids) == len(set(graph_ids))  # All unique


@pytest.mark.integration
@pytest.mark.asyncio
async def test_path_canonicalization_script_output_without_api_key(tmp_path, capsys):
    """Test that validates the script-like output for path canonicalization.

    This test simulates the behavior described in the task:
    'Add a small integration test or script that, given a raw filesystem path,
    prints the canonical key and whether a saved graph exists.'
    """
    # Create a test codebase
    codebase = tmp_path / "script_test"
    codebase.mkdir()
    (codebase / "main.py").write_text("main = 1")

    manager = CodebaseGraphManager(tmp_path / "graphs")

    # Simulate script behavior for a new path
    raw_path = str(codebase)
    canonical = resolve_canonical_path(raw_path)
    existing = await lookup_graph_for_path(canonical, manager)

    print(f"Raw path: {raw_path}")
    print(f"Canonical path: {canonical}")
    print(f"Graph exists: {existing is not None}")
    if existing:
        print(f"Graph ID: {existing.graph_id}")
        print(f"Graph name: {existing.name}")

    captured = capsys.readouterr()
    assert f"Canonical path: {canonical}" in captured.out
    assert "Graph exists: False" in captured.out

    # Create a graph
    graph = await create_graph_for_path(canonical, manager, name="Script Test")

    # Simulate script behavior for an existing path
    existing = await lookup_graph_for_path(canonical, manager)

    print(f"\nAfter graph creation:")
    print(f"Canonical path: {canonical}")
    print(f"Graph exists: {existing is not None}")
    if existing:
        print(f"Graph ID: {existing.graph_id}")
        print(f"Graph name: {existing.name}")

    captured = capsys.readouterr()
    assert "Graph exists: True" in captured.out
    assert f"Graph ID: {graph.graph_id}" in captured.out
    assert "Graph name: Script Test" in captured.out


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cross_platform_path_normalization_without_api_key(tmp_path):
    """Test that path normalization works consistently across platforms."""
    # Create a codebase with spaces in name (common edge case)
    codebase = tmp_path / "My Project Name"
    codebase.mkdir()
    (codebase / "app.py").write_text("app = 1")

    manager = CodebaseGraphManager(tmp_path / "graphs")

    # Test with different path representations
    path_representations = [
        str(codebase),  # String representation
        codebase,  # Path object
        str(codebase.absolute()),  # Explicit absolute
    ]

    # All should canonicalize to the same path
    canonical_paths = [resolve_canonical_path(p) for p in path_representations]
    assert all(cp == canonical_paths[0] for cp in canonical_paths)

    # Create graph with first representation
    graph = await create_graph_for_path(canonical_paths[0], manager)

    # Should be findable with any representation
    for canonical in canonical_paths:
        found = await lookup_graph_for_path(canonical, manager)
        assert found is not None
        assert found.graph_id == graph.graph_id
