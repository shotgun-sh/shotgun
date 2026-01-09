"""Tests for IndexingState class."""

import pytest

from shotgun.codebase.indexing_state import IndexingState


@pytest.fixture(autouse=True)
def reset_indexing_state():
    """Reset class-level state before each test."""
    # Clear state before test
    IndexingState._active_graphs.clear()
    IndexingState._lock = None
    yield
    # Clear state after test
    IndexingState._active_graphs.clear()
    IndexingState._lock = None


@pytest.mark.asyncio
async def test_start_marks_graph_as_active():
    """Test that start() marks a graph as being indexed."""
    state = IndexingState()
    assert not state.is_active("graph-123")

    await state.start("graph-123")

    assert state.is_active("graph-123")


@pytest.mark.asyncio
async def test_complete_marks_graph_as_inactive():
    """Test that complete() marks a graph as no longer being indexed."""
    state = IndexingState()
    await state.start("graph-123")
    assert state.is_active("graph-123")

    await state.complete("graph-123")

    assert not state.is_active("graph-123")


@pytest.mark.asyncio
async def test_complete_on_non_active_graph_is_safe():
    """Test that complete() on a non-active graph doesn't error."""
    state = IndexingState()
    # Should not raise
    await state.complete("non-existent")


@pytest.mark.asyncio
async def test_has_active_returns_true_when_graphs_indexing():
    """Test has_active() returns True when any graph is being indexed."""
    state = IndexingState()
    assert not state.has_active()

    await state.start("graph-1")
    assert state.has_active()

    await state.start("graph-2")
    assert state.has_active()

    await state.complete("graph-1")
    assert state.has_active()  # graph-2 still active

    await state.complete("graph-2")
    assert not state.has_active()


@pytest.mark.asyncio
async def test_get_active_ids_returns_copy():
    """Test get_active_ids() returns a copy of active graph IDs."""
    state = IndexingState()
    await state.start("graph-1")
    await state.start("graph-2")

    active_ids = state.get_active_ids()

    assert active_ids == {"graph-1", "graph-2"}
    # Verify it's a copy
    active_ids.add("graph-3")
    assert not state.is_active("graph-3")


@pytest.mark.asyncio
async def test_class_level_state_shared_across_instances():
    """Test that IndexingState uses class-level shared state."""
    state1 = IndexingState()
    state2 = IndexingState()

    await state1.start("graph-shared")

    # Both instances should see the same state
    assert state1.is_active("graph-shared")
    assert state2.is_active("graph-shared")

    await state2.complete("graph-shared")

    # Both instances should see the updated state
    assert not state1.is_active("graph-shared")
    assert not state2.is_active("graph-shared")


@pytest.mark.asyncio
async def test_multiple_graphs_can_be_indexed_simultaneously():
    """Test that multiple graphs can be tracked as indexing at once."""
    state = IndexingState()

    await state.start("graph-a")
    await state.start("graph-b")
    await state.start("graph-c")

    assert state.is_active("graph-a")
    assert state.is_active("graph-b")
    assert state.is_active("graph-c")
    assert state.get_active_ids() == {"graph-a", "graph-b", "graph-c"}

    await state.complete("graph-b")

    assert state.is_active("graph-a")
    assert not state.is_active("graph-b")
    assert state.is_active("graph-c")
