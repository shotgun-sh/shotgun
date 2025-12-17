"""Unit tests for GraphDecisionModal screen."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from textual.widgets import Button

from shotgun.codebase.models import CodebaseGraph, GraphStatus
from shotgun.tui.screens.chat.graph_decision_modal import (
    GraphChoice,
    GraphDecisionModal,
    GraphDecisionResult,
)


@pytest.fixture
def mock_existing_graph():
    """Create a mock existing graph for testing."""
    return CodebaseGraph(
        graph_id="test123graph",
        repo_path="/home/user/my-repo",
        graph_path="/storage/test123graph.kuzu",
        name="My Test Repo",
        created_at=1234567890.0,
        updated_at=1234567890.0,
        status=GraphStatus.READY,
        node_count=1500,
        relationship_count=3200,
    )


def test_modal_initialization(mock_existing_graph):
    """Test that modal initializes correctly with graph data."""
    modal = GraphDecisionModal(mock_existing_graph)

    assert modal.existing_graph == mock_existing_graph
    assert isinstance(modal, GraphDecisionModal)


def test_handle_reuse_button(mock_existing_graph):
    """Test that reuse button handler works correctly."""
    modal = GraphDecisionModal(mock_existing_graph)

    # Mock the dismiss method
    modal.dismiss = Mock()

    # Simulate button press
    event = Mock()
    event.stop = Mock()

    modal.handle_reuse(event)

    # Verify event was stopped
    event.stop.assert_called_once()

    # Verify dismiss was called with correct result
    modal.dismiss.assert_called_once()
    call_args = modal.dismiss.call_args[0][0]
    assert isinstance(call_args, GraphDecisionResult)
    assert call_args.choice == GraphChoice.REUSE
    assert call_args.existing_graph == mock_existing_graph


def test_handle_new_button(mock_existing_graph):
    """Test that new button handler works correctly."""
    modal = GraphDecisionModal(mock_existing_graph)

    # Mock the dismiss method
    modal.dismiss = Mock()

    # Simulate button press
    event = Mock()
    event.stop = Mock()

    modal.handle_new(event)

    # Verify event was stopped
    event.stop.assert_called_once()

    # Verify dismiss was called with correct result
    modal.dismiss.assert_called_once()
    call_args = modal.dismiss.call_args[0][0]
    assert isinstance(call_args, GraphDecisionResult)
    assert call_args.choice == GraphChoice.NEW
    assert call_args.existing_graph == mock_existing_graph


def test_handle_cancel_button(mock_existing_graph):
    """Test that cancel button handler works correctly."""
    modal = GraphDecisionModal(mock_existing_graph)

    # Mock the dismiss method
    modal.dismiss = Mock()

    # Simulate button press
    event = Mock()
    event.stop = Mock()

    modal.handle_cancel(event)

    # Verify event was stopped
    event.stop.assert_called_once()

    # Verify dismiss was called with correct result
    modal.dismiss.assert_called_once()
    call_args = modal.dismiss.call_args[0][0]
    assert isinstance(call_args, GraphDecisionResult)
    assert call_args.choice == GraphChoice.CANCEL
    assert call_args.existing_graph == mock_existing_graph


def test_escape_key_cancels(mock_existing_graph):
    """Test that escape key dismisses modal with cancel choice."""
    modal = GraphDecisionModal(mock_existing_graph)

    # Mock the dismiss method
    modal.dismiss = Mock()

    # Simulate escape key press
    event = Mock()
    event.key = "escape"
    event.stop = Mock()

    modal.on_key(event)

    # Verify event was stopped
    event.stop.assert_called_once()

    # Verify dismiss was called with cancel result
    modal.dismiss.assert_called_once()
    call_args = modal.dismiss.call_args[0][0]
    assert isinstance(call_args, GraphDecisionResult)
    assert call_args.choice == GraphChoice.CANCEL


def test_graph_choice_enum_values():
    """Test that GraphChoice enum has expected values."""
    assert GraphChoice.REUSE == "reuse"
    assert GraphChoice.NEW == "new"
    assert GraphChoice.CANCEL == "cancel"

    # Test that all values are strings
    assert isinstance(GraphChoice.REUSE.value, str)
    assert isinstance(GraphChoice.NEW.value, str)
    assert isinstance(GraphChoice.CANCEL.value, str)


def test_graph_decision_result_model():
    """Test GraphDecisionResult Pydantic model."""
    graph = CodebaseGraph(
        graph_id="test",
        repo_path="/test",
        graph_path="/test.kuzu",
        name="Test",
        created_at=1.0,
        updated_at=1.0,
        status=GraphStatus.READY,
    )

    result = GraphDecisionResult(
        choice=GraphChoice.REUSE,
        existing_graph=graph,
    )

    assert result.choice == GraphChoice.REUSE
    assert result.existing_graph == graph

    # Test serialization
    data = result.model_dump()
    assert data["choice"] == "reuse"
    assert data["existing_graph"] is not None


def test_graph_decision_result_without_graph():
    """Test GraphDecisionResult can be created without graph."""
    result = GraphDecisionResult(
        choice=GraphChoice.CANCEL,
        existing_graph=None,
    )

    assert result.choice == GraphChoice.CANCEL
    assert result.existing_graph is None
