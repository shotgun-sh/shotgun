"""Unit tests for graph open decision logic."""

import pytest

from shotgun.agents.config.models import PersistentGraphOpenBehavior
from shotgun.codebase.graph_decision import (
    GraphOpenAction,
    GraphOpenDecision,
    decide_graph_open_action,
)
from shotgun.codebase.models import CodebaseGraph, GraphStatus


@pytest.fixture
def mock_existing_graph():
    """Create a mock existing graph for testing."""
    return CodebaseGraph(
        graph_id="test123graph",
        repo_path="/home/user/my-repo",
        graph_path="/storage/test123graph.kuzu",
        name="My Repo",
        created_at=1234567890.0,
        updated_at=1234567890.0,
        status=GraphStatus.READY,
    )


def test_no_existing_graph_always_creates_new():
    """Test that no existing graph always results in NEW action regardless of behavior."""
    canonical_path = "/home/user/my-repo"

    # Test with ASK behavior
    decision = decide_graph_open_action(
        canonical_path, PersistentGraphOpenBehavior.ASK, None
    )
    assert decision.action == GraphOpenAction.NEW
    assert decision.existing_graph is None
    assert decision.should_create_new
    assert not decision.should_reuse
    assert not decision.should_ask_user

    # Test with ALWAYS_REUSE behavior (still creates new when no graph exists)
    decision = decide_graph_open_action(
        canonical_path, PersistentGraphOpenBehavior.ALWAYS_REUSE, None
    )
    assert decision.action == GraphOpenAction.NEW
    assert decision.existing_graph is None

    # Test with ALWAYS_NEW behavior
    decision = decide_graph_open_action(
        canonical_path, PersistentGraphOpenBehavior.ALWAYS_NEW, None
    )
    assert decision.action == GraphOpenAction.NEW
    assert decision.existing_graph is None


def test_always_reuse_with_existing_graph(mock_existing_graph):
    """Test ALWAYS_REUSE behavior with existing graph."""
    canonical_path = "/home/user/my-repo"

    decision = decide_graph_open_action(
        canonical_path, PersistentGraphOpenBehavior.ALWAYS_REUSE, mock_existing_graph
    )

    assert decision.action == GraphOpenAction.REUSE
    assert decision.existing_graph == mock_existing_graph
    assert decision.should_reuse
    assert not decision.should_create_new
    assert not decision.should_ask_user


def test_always_new_with_existing_graph(mock_existing_graph):
    """Test ALWAYS_NEW behavior with existing graph."""
    canonical_path = "/home/user/my-repo"

    decision = decide_graph_open_action(
        canonical_path, PersistentGraphOpenBehavior.ALWAYS_NEW, mock_existing_graph
    )

    assert decision.action == GraphOpenAction.NEW
    # Should include existing graph for potential cleanup
    assert decision.existing_graph == mock_existing_graph
    assert decision.should_create_new
    assert not decision.should_reuse
    assert not decision.should_ask_user


def test_ask_with_existing_graph(mock_existing_graph):
    """Test ASK behavior with existing graph."""
    canonical_path = "/home/user/my-repo"

    decision = decide_graph_open_action(
        canonical_path, PersistentGraphOpenBehavior.ASK, mock_existing_graph
    )

    assert decision.action == GraphOpenAction.ASK
    assert decision.existing_graph == mock_existing_graph
    assert decision.should_ask_user
    assert not decision.should_reuse
    assert not decision.should_create_new


def test_decision_properties(mock_existing_graph):
    """Test GraphOpenDecision convenience properties."""
    # Test REUSE decision properties
    reuse_decision = GraphOpenDecision(
        action=GraphOpenAction.REUSE, existing_graph=mock_existing_graph
    )
    assert reuse_decision.should_reuse is True
    assert reuse_decision.should_create_new is False
    assert reuse_decision.should_ask_user is False

    # Test NEW decision properties
    new_decision = GraphOpenDecision(action=GraphOpenAction.NEW, existing_graph=None)
    assert new_decision.should_reuse is False
    assert new_decision.should_create_new is True
    assert new_decision.should_ask_user is False

    # Test ASK decision properties
    ask_decision = GraphOpenDecision(
        action=GraphOpenAction.ASK, existing_graph=mock_existing_graph
    )
    assert ask_decision.should_reuse is False
    assert ask_decision.should_create_new is False
    assert ask_decision.should_ask_user is True


@pytest.mark.parametrize(
    "behavior,existing_graph,expected_action",
    [
        # No existing graph cases
        (PersistentGraphOpenBehavior.ASK, None, GraphOpenAction.NEW),
        (PersistentGraphOpenBehavior.ALWAYS_REUSE, None, GraphOpenAction.NEW),
        (PersistentGraphOpenBehavior.ALWAYS_NEW, None, GraphOpenAction.NEW),
        # With existing graph cases
        (
            PersistentGraphOpenBehavior.ALWAYS_REUSE,
            "existing",
            GraphOpenAction.REUSE,
        ),
        (PersistentGraphOpenBehavior.ALWAYS_NEW, "existing", GraphOpenAction.NEW),
        (PersistentGraphOpenBehavior.ASK, "existing", GraphOpenAction.ASK),
    ],
)
def test_all_combinations_parametrized(
    behavior, existing_graph, expected_action, mock_existing_graph
):
    """Parametrized test covering all combinations of behavior and graph existence."""
    canonical_path = "/home/user/test-repo"

    # Convert "existing" marker to actual graph object
    graph = mock_existing_graph if existing_graph == "existing" else None

    decision = decide_graph_open_action(canonical_path, behavior, graph)

    assert decision.action == expected_action

    # Verify existing_graph reference is set correctly
    if graph is not None:
        assert decision.existing_graph == graph
    elif expected_action == GraphOpenAction.NEW and existing_graph is None:
        assert decision.existing_graph is None


def test_decision_is_deterministic(mock_existing_graph):
    """Test that same inputs always produce same decision."""
    canonical_path = "/home/user/my-repo"

    # Call multiple times with same inputs
    decision1 = decide_graph_open_action(
        canonical_path, PersistentGraphOpenBehavior.ASK, mock_existing_graph
    )
    decision2 = decide_graph_open_action(
        canonical_path, PersistentGraphOpenBehavior.ASK, mock_existing_graph
    )
    decision3 = decide_graph_open_action(
        canonical_path, PersistentGraphOpenBehavior.ASK, mock_existing_graph
    )

    # All should produce identical results
    assert decision1.action == decision2.action == decision3.action
    assert (
        decision1.existing_graph
        == decision2.existing_graph
        == decision3.existing_graph
    )


def test_decision_with_different_paths(mock_existing_graph):
    """Test that decision logic works with different canonical paths."""
    paths = [
        "/home/user/project1",
        "/var/www/app",
        "C:\\Users\\dev\\code",
        "/tmp/test-repo",
    ]

    for path in paths:
        decision = decide_graph_open_action(
            path, PersistentGraphOpenBehavior.ALWAYS_REUSE, mock_existing_graph
        )
        assert decision.action == GraphOpenAction.REUSE
        assert decision.existing_graph == mock_existing_graph


def test_decision_model_serialization():
    """Test that GraphOpenDecision can be serialized/deserialized."""
    decision = GraphOpenDecision(
        action=GraphOpenAction.ASK, existing_graph=None
    )

    # Test Pydantic serialization
    data = decision.model_dump()
    assert data["action"] == "ask"
    assert data["existing_graph"] is None

    # Test reconstruction
    reconstructed = GraphOpenDecision(**data)
    assert reconstructed.action == decision.action
    assert reconstructed.existing_graph == decision.existing_graph


def test_graph_open_action_enum_values():
    """Test that GraphOpenAction enum has expected values."""
    assert GraphOpenAction.REUSE == "reuse"
    assert GraphOpenAction.NEW == "new"
    assert GraphOpenAction.ASK == "ask"

    # Test that all values are strings
    assert isinstance(GraphOpenAction.REUSE.value, str)
    assert isinstance(GraphOpenAction.NEW.value, str)
    assert isinstance(GraphOpenAction.ASK.value, str)


def test_persistent_graph_behavior_enum_values():
    """Test that PersistentGraphOpenBehavior enum has expected values."""
    assert PersistentGraphOpenBehavior.ASK == "ask"
    assert PersistentGraphOpenBehavior.ALWAYS_REUSE == "always_reuse"
    assert PersistentGraphOpenBehavior.ALWAYS_NEW == "always_new"
