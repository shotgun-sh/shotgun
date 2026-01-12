"""Regression tests for codebase indexing functionality.

These tests ensure that existing CLI commands and SDK APIs continue
to work correctly after parallel execution changes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from shotgun.codebase import CodebaseService, QueryType
from shotgun.codebase.models import GraphStatus, IndexProgress, ProgressPhase

# =============================================================================
# CLI Command Regression Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_codebase_index_command_works(
    simple_python_codebase: Path,
    tmp_path: Path,
) -> None:
    """Test existing `shotgun codebase index` command still works."""
    service = CodebaseService(tmp_path / "storage")

    graph = await service.create_graph(
        simple_python_codebase,
        "Regression Test Index",
    )

    assert graph is not None
    assert graph.status == GraphStatus.READY
    assert graph.node_count > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_codebase_create_graph_with_parallel(
    calculator_codebase: Path,
    tmp_path: Path,
) -> None:
    """Test that create_graph works with parallel mode enabled."""
    service = CodebaseService(tmp_path / "storage")

    # Create graph (parallel mode is default when CPU >= 4)
    graph = await service.create_graph(
        calculator_codebase,
        "Parallel Regression Test",
    )

    assert graph is not None
    assert graph.status == GraphStatus.READY
    assert graph.node_count > 0
    assert graph.relationship_count > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_codebase_query_after_indexing(
    simple_python_codebase: Path,
    tmp_path: Path,
) -> None:
    """Test that querying works after indexing."""
    service = CodebaseService(tmp_path / "storage")

    graph = await service.create_graph(
        simple_python_codebase,
        "Query Regression Test",
    )

    # Execute a Cypher query
    result = await service.execute_query(
        graph.graph_id,
        "MATCH (n) RETURN count(n) as count",
        QueryType.CYPHER,
    )

    assert result.success is True
    assert result.row_count == 1


# =============================================================================
# Progress Reporting Regression Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_progress_reporting_format_compatible(
    simple_python_codebase: Path,
    tmp_path: Path,
) -> None:
    """Test progress reporting format is compatible with TUI."""
    progress_events: list[IndexProgress] = []

    def progress_callback(progress: IndexProgress) -> None:
        progress_events.append(progress)

    service = CodebaseService(tmp_path / "storage")

    await service.create_graph(
        simple_python_codebase,
        "Progress Test",
        progress_callback=progress_callback,
    )

    # Verify progress events have expected structure
    for event in progress_events:
        assert hasattr(event, "phase")
        assert hasattr(event, "phase_name")
        assert isinstance(event.phase_name, str)
        assert hasattr(event, "current")
        assert isinstance(event.current, int)
        # total can be None for indeterminate progress


@pytest.mark.integration
@pytest.mark.asyncio
async def test_progress_shows_phase_transitions(
    calculator_codebase: Path,
    tmp_path: Path,
) -> None:
    """Test that progress reporting shows phase transitions."""
    progress_events: list[IndexProgress] = []

    def progress_callback(progress: IndexProgress) -> None:
        progress_events.append(progress)

    service = CodebaseService(tmp_path / "storage")

    await service.create_graph(
        calculator_codebase,
        "Phase Transition Test",
        progress_callback=progress_callback,
    )

    # Should have multiple phases reported
    phase_names = {e.phase_name for e in progress_events}
    assert len(phase_names) > 1, "Should report multiple phases"


# =============================================================================
# Sequential Mode Identical Results Test
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sequential_mode_produces_results(
    calculator_codebase: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Verify sequential mode produces correct results.

    This is a smoke test to ensure the parallel implementation doesn't
    break sequential mode.
    """
    # Force sequential mode
    monkeypatch.setenv("SHOTGUN_INDEX_PARALLEL", "false")

    service = CodebaseService(tmp_path / "storage")

    graph = await service.create_graph(
        calculator_codebase,
        "Sequential Mode Test",
    )

    assert graph is not None
    assert graph.status == GraphStatus.READY
    assert graph.node_count > 0

    # Query to verify data was indexed
    result = await service.execute_query(
        graph.graph_id,
        "MATCH (c:Class) RETURN c.name as name",
        QueryType.CYPHER,
    )

    assert result.success is True
    # calculator_codebase has Calculator, ScientificCalculator, MathConstants
    assert result.row_count >= 3


@pytest.mark.integration
@pytest.mark.asyncio
async def test_parallel_and_sequential_both_work(
    simple_python_codebase: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Test that both parallel and sequential modes produce valid results."""
    # Test sequential mode
    monkeypatch.setenv("SHOTGUN_INDEX_PARALLEL", "false")
    seq_service = CodebaseService(tmp_path / "storage_seq")
    seq_graph = await seq_service.create_graph(
        simple_python_codebase,
        "Sequential Test",
    )

    # Test parallel mode
    monkeypatch.setenv("SHOTGUN_INDEX_PARALLEL", "true")
    par_service = CodebaseService(tmp_path / "storage_par")
    par_graph = await par_service.create_graph(
        simple_python_codebase,
        "Parallel Test",
    )

    # Both should complete successfully
    assert seq_graph.status == GraphStatus.READY
    assert par_graph.status == GraphStatus.READY

    # Both should have nodes
    assert seq_graph.node_count > 0
    assert par_graph.node_count > 0

    # Query both to verify data
    seq_result = await seq_service.execute_query(
        seq_graph.graph_id,
        "MATCH (n) RETURN count(n) as count",
        QueryType.CYPHER,
    )
    par_result = await par_service.execute_query(
        par_graph.graph_id,
        "MATCH (n) RETURN count(n) as count",
        QueryType.CYPHER,
    )

    assert seq_result.success is True
    assert par_result.success is True


# =============================================================================
# API Stability Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_codebase_service_api_unchanged(
    tmp_path: Path,
) -> None:
    """Test that CodebaseService API signature is unchanged."""
    service = CodebaseService(tmp_path / "storage")

    # Verify expected methods exist
    assert hasattr(service, "create_graph")
    assert hasattr(service, "get_graph")
    assert hasattr(service, "delete_graph")  # delete_graph, not remove_graph
    assert hasattr(service, "execute_query")
    assert callable(service.create_graph)
    assert callable(service.get_graph)
    assert callable(service.delete_graph)
    assert callable(service.execute_query)


@pytest.mark.integration
def test_index_progress_model_unchanged() -> None:
    """Test that IndexProgress model structure is unchanged."""
    # Verify ProgressPhase enum has expected values
    assert hasattr(ProgressPhase, "STRUCTURE")
    assert hasattr(ProgressPhase, "DEFINITIONS")
    assert hasattr(ProgressPhase, "RELATIONSHIPS")

    # Verify IndexProgress can be created with expected fields
    progress = IndexProgress(
        phase=ProgressPhase.STRUCTURE,
        phase_name="Test Phase",
        current=0,
        total=100,
        message="Testing",
    )

    assert progress.phase == ProgressPhase.STRUCTURE
    assert progress.phase_name == "Test Phase"
    assert progress.current == 0
    assert progress.total == 100


@pytest.mark.integration
def test_graph_status_enum_unchanged() -> None:
    """Test that GraphStatus enum has expected values."""
    # Verify expected status values exist
    assert hasattr(GraphStatus, "READY")
    assert hasattr(GraphStatus, "BUILDING")  # Building status for initial indexing
    assert hasattr(GraphStatus, "ERROR")


# =============================================================================
# Backward Compatibility Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_graph_without_progress_callback(
    simple_python_codebase: Path,
    tmp_path: Path,
) -> None:
    """Test that create_graph works without progress callback."""
    service = CodebaseService(tmp_path / "storage")

    # Should work without progress_callback
    graph = await service.create_graph(
        simple_python_codebase,
        "No Callback Test",
    )

    assert graph is not None
    assert graph.status == GraphStatus.READY


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_graph_with_progress_callback(
    simple_python_codebase: Path,
    tmp_path: Path,
) -> None:
    """Test that create_graph works with progress callback."""
    callback_called = False

    def progress_callback(progress: IndexProgress) -> None:
        nonlocal callback_called
        callback_called = True

    service = CodebaseService(tmp_path / "storage")

    graph = await service.create_graph(
        simple_python_codebase,
        "With Callback Test",
        progress_callback=progress_callback,
    )

    assert graph is not None
    assert graph.status == GraphStatus.READY
    assert callback_called, "Progress callback should have been called"
