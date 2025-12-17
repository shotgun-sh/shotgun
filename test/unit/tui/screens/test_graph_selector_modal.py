"""Unit tests for GraphSelectorModal screen."""

from unittest.mock import AsyncMock, Mock

import pytest

from shotgun.codebase.models import CodebaseGraph, GraphStatus
from shotgun.tui.screens.chat.graph_selector_modal import (
    GraphSelectorAction,
    GraphSelectorModal,
    GraphSelectorResult,
)


def create_test_graph(
    graph_id: str = "test-id",
    name: str = "test-graph",
    node_count: int = 100,
    relationship_count: int = 50,
) -> CodebaseGraph:
    """Create a test CodebaseGraph."""
    return CodebaseGraph(
        graph_id=graph_id,
        repo_path="/test/path",
        graph_path=f"/test/{graph_id}.kuzu",
        name=name,
        created_at=1234567890.0,
        updated_at=1234567890.0,
        status=GraphStatus.READY,
        node_count=node_count,
        relationship_count=relationship_count,
    )


@pytest.fixture
def mock_codebase_sdk():
    """Create a mock CodebaseSDK for testing."""
    mock = Mock()
    mock.service = Mock()
    mock.service.list_graphs = AsyncMock(return_value=[])
    return mock


def test_modal_initialization(mock_codebase_sdk):
    """Test that modal initializes correctly."""
    current_graph = create_test_graph()
    modal = GraphSelectorModal(mock_codebase_sdk, current_graph)

    assert modal.codebase_sdk == mock_codebase_sdk
    assert modal.current_graph == current_graph
    assert modal.available_graphs == []
    assert modal.selected_graph is None


def test_modal_initialization_without_current_graph(mock_codebase_sdk):
    """Test modal initialization with no current graph."""
    modal = GraphSelectorModal(mock_codebase_sdk, None)

    assert modal.codebase_sdk == mock_codebase_sdk
    assert modal.current_graph is None
    assert modal.available_graphs == []
    assert modal.selected_graph is None


@pytest.mark.asyncio
async def test_load_graphs_with_single_graph(mock_codebase_sdk):
    """Test loading graphs when one graph is available."""
    graph = create_test_graph(name="single-graph")
    mock_codebase_sdk.service.list_graphs = AsyncMock(return_value=[graph])

    modal = GraphSelectorModal(mock_codebase_sdk, None)

    # Mock query_one to return mock widgets
    mock_list_view = Mock()
    mock_list_view.children = []
    mock_list_view.append = Mock()
    mock_list_view.index = 0

    mock_button = Mock()
    mock_button.disabled = False

    def query_side_effect(selector, *args, **kwargs):
        if "#graph-list" in selector:
            return mock_list_view
        elif "#btn-use" in selector:
            return mock_button
        return Mock()

    modal.query_one = Mock(side_effect=query_side_effect)

    await modal._load_graphs()

    # Verify graph was loaded
    assert len(modal.available_graphs) == 1
    assert modal.available_graphs[0] == graph
    assert modal.selected_graph == graph  # First graph auto-selected


@pytest.mark.asyncio
async def test_load_graphs_with_multiple_graphs(mock_codebase_sdk):
    """Test loading graphs when multiple graphs are available."""
    graphs = [
        create_test_graph(graph_id="id1", name="graph-1"),
        create_test_graph(graph_id="id2", name="graph-2"),
        create_test_graph(graph_id="id3", name="graph-3"),
    ]
    mock_codebase_sdk.service.list_graphs = AsyncMock(return_value=graphs)

    modal = GraphSelectorModal(mock_codebase_sdk, None)

    # Mock widgets
    mock_list_view = Mock()
    mock_list_view.children = []
    mock_list_view.append = Mock()
    mock_list_view.index = 0

    mock_button = Mock()

    def query_side_effect(selector, *args, **kwargs):
        if "#graph-list" in selector:
            return mock_list_view
        elif "#btn-use" in selector:
            return mock_button
        return Mock()

    modal.query_one = Mock(side_effect=query_side_effect)

    await modal._load_graphs()

    # Verify all graphs were loaded
    assert len(modal.available_graphs) == 3
    assert modal.selected_graph == graphs[0]  # First graph auto-selected


@pytest.mark.asyncio
async def test_load_graphs_with_current_graph_highlighting(mock_codebase_sdk):
    """Test that current graph is highlighted when present."""
    current_graph = create_test_graph(graph_id="current", name="current-graph")
    other_graphs = [
        create_test_graph(graph_id="id1", name="graph-1"),
        create_test_graph(graph_id="id2", name="graph-2"),
    ]
    all_graphs = [other_graphs[0], current_graph, other_graphs[1]]

    mock_codebase_sdk.service.list_graphs = AsyncMock(return_value=all_graphs)

    modal = GraphSelectorModal(mock_codebase_sdk, current_graph)

    # Mock widgets
    mock_list_view = Mock()
    mock_list_view.children = []
    mock_list_view.append = Mock()
    mock_list_view.index = 0

    mock_button = Mock()

    def query_side_effect(selector, *args, **kwargs):
        if "#graph-list" in selector:
            return mock_list_view
        elif "#btn-use" in selector:
            return mock_button
        return Mock()

    modal.query_one = Mock(side_effect=query_side_effect)

    await modal._load_graphs()

    # Verify current graph was found and selected
    assert modal.selected_graph == current_graph
    # Index should be set to 1 (current_graph is at index 1)
    assert mock_list_view.index == 1


@pytest.mark.asyncio
async def test_load_graphs_with_no_graphs(mock_codebase_sdk):
    """Test loading when no graphs are available."""
    mock_codebase_sdk.service.list_graphs = AsyncMock(return_value=[])

    modal = GraphSelectorModal(mock_codebase_sdk, None)

    # Mock widgets
    mock_list_view = Mock()
    mock_list_view.children = []
    mock_list_view.append = Mock()

    mock_button = Mock()
    mock_button.disabled = False

    def query_side_effect(selector, *args, **kwargs):
        if "#graph-list" in selector:
            return mock_list_view
        elif "#btn-use" in selector:
            return mock_button
        return Mock()

    modal.query_one = Mock(side_effect=query_side_effect)

    await modal._load_graphs()

    # Verify no graphs loaded
    assert len(modal.available_graphs) == 0
    # Button should be disabled
    assert mock_button.disabled is True


@pytest.mark.asyncio
async def test_load_graphs_with_error(mock_codebase_sdk):
    """Test loading graphs when an error occurs."""
    mock_codebase_sdk.service.list_graphs = AsyncMock(
        side_effect=Exception("Database error")
    )

    modal = GraphSelectorModal(mock_codebase_sdk, None)

    # Mock widgets
    mock_list_view = Mock()
    mock_list_view.children = []
    mock_list_view.append = Mock()

    mock_button = Mock()
    mock_button.disabled = False

    def query_side_effect(selector, *args, **kwargs):
        if "#graph-list" in selector:
            return mock_list_view
        elif "#btn-use" in selector:
            return mock_button
        return Mock()

    modal.query_one = Mock(side_effect=query_side_effect)

    await modal._load_graphs()

    # Verify error handling
    assert len(modal.available_graphs) == 0
    assert mock_button.disabled is True


def test_handle_selection_event(mock_codebase_sdk):
    """Test ListView.Selected event handler."""
    graphs = [
        create_test_graph(graph_id="id1", name="graph-1"),
        create_test_graph(graph_id="id2", name="graph-2"),
    ]

    modal = GraphSelectorModal(mock_codebase_sdk, None)
    modal.available_graphs = graphs
    modal.dismiss = Mock()

    # Mock _handle_use_selected to verify it's called
    modal._handle_use_selected = Mock()

    # Simulate selection event
    event = Mock()
    event.list_view = Mock()
    event.list_view.index = 1
    event.stop = Mock()

    modal.handle_selection(event)

    # Verify graph was selected and use handler called
    assert modal.selected_graph == graphs[1]
    event.stop.assert_called_once()
    modal._handle_use_selected.assert_called_once()


def test_handle_highlight_event(mock_codebase_sdk):
    """Test ListView.Highlighted event handler."""
    graphs = [
        create_test_graph(graph_id="id1", name="graph-1"),
        create_test_graph(graph_id="id2", name="graph-2"),
    ]

    modal = GraphSelectorModal(mock_codebase_sdk, None)
    modal.available_graphs = graphs

    # Simulate highlight event
    event = Mock()
    event.list_view = Mock()
    event.list_view.index = 0
    event.stop = Mock()

    modal.handle_highlight(event)

    # Verify graph was highlighted (not dismissed)
    assert modal.selected_graph == graphs[0]
    event.stop.assert_called_once()


def test_handle_use_button(mock_codebase_sdk):
    """Test 'Use Selected' button handler."""
    graph = create_test_graph(name="selected-graph")

    modal = GraphSelectorModal(mock_codebase_sdk, None)
    modal.selected_graph = graph
    modal.dismiss = Mock()

    # Simulate button press
    event = Mock()
    event.stop = Mock()

    modal.handle_use_button(event)

    # Verify event handling
    event.stop.assert_called_once()

    # Verify dismiss was called with correct result
    modal.dismiss.assert_called_once()
    result = modal.dismiss.call_args[0][0]
    assert isinstance(result, GraphSelectorResult)
    assert result.action == GraphSelectorAction.USE_SELECTED
    assert result.selected_graph == graph


def test_handle_use_button_without_selection(mock_codebase_sdk):
    """Test 'Use Selected' button when no graph is selected."""
    modal = GraphSelectorModal(mock_codebase_sdk, None)
    modal.selected_graph = None
    modal.dismiss = Mock()

    # Simulate button press
    event = Mock()
    event.stop = Mock()

    modal.handle_use_button(event)

    # Should handle gracefully without dismissing
    event.stop.assert_called_once()
    modal.dismiss.assert_not_called()


def test_handle_create_button(mock_codebase_sdk):
    """Test 'Create New Graph' button handler."""
    modal = GraphSelectorModal(mock_codebase_sdk, None)
    modal.dismiss = Mock()

    # Simulate button press
    event = Mock()
    event.stop = Mock()

    modal.handle_create(event)

    # Verify dismiss was called with CREATE_NEW action
    event.stop.assert_called_once()
    modal.dismiss.assert_called_once()
    result = modal.dismiss.call_args[0][0]
    assert isinstance(result, GraphSelectorResult)
    assert result.action == GraphSelectorAction.CREATE_NEW
    assert result.selected_graph is None


def test_handle_settings_button(mock_codebase_sdk):
    """Test 'Settings' button handler."""
    modal = GraphSelectorModal(mock_codebase_sdk, None)
    modal.dismiss = Mock()

    # Simulate button press
    event = Mock()
    event.stop = Mock()

    modal.handle_settings(event)

    # Verify dismiss was called with OPEN_SETTINGS action
    event.stop.assert_called_once()
    modal.dismiss.assert_called_once()
    result = modal.dismiss.call_args[0][0]
    assert isinstance(result, GraphSelectorResult)
    assert result.action == GraphSelectorAction.OPEN_SETTINGS
    assert result.selected_graph is None


def test_handle_cancel_button(mock_codebase_sdk):
    """Test 'Cancel' button handler."""
    modal = GraphSelectorModal(mock_codebase_sdk, None)
    modal.dismiss = Mock()

    # Simulate button press
    event = Mock()
    event.stop = Mock()

    modal.handle_cancel(event)

    # Verify dismiss was called with CANCEL action
    event.stop.assert_called_once()
    modal.dismiss.assert_called_once()
    result = modal.dismiss.call_args[0][0]
    assert isinstance(result, GraphSelectorResult)
    assert result.action == GraphSelectorAction.CANCEL
    assert result.selected_graph is None


def test_escape_key_cancels(mock_codebase_sdk):
    """Test that escape key dismisses modal with cancel action."""
    modal = GraphSelectorModal(mock_codebase_sdk, None)
    modal.dismiss = Mock()

    # Simulate escape key press
    event = Mock()
    event.key = "escape"
    event.stop = Mock()

    modal.on_key(event)

    # Verify dismiss was called with CANCEL
    event.stop.assert_called_once()
    modal.dismiss.assert_called_once()
    result = modal.dismiss.call_args[0][0]
    assert result.action == GraphSelectorAction.CANCEL


def test_graph_selector_action_enum_values():
    """Test that GraphSelectorAction enum has expected values."""
    assert GraphSelectorAction.USE_SELECTED == "use_selected"
    assert GraphSelectorAction.CREATE_NEW == "create_new"
    assert GraphSelectorAction.OPEN_SETTINGS == "open_settings"
    assert GraphSelectorAction.CANCEL == "cancel"


def test_graph_selector_result_model():
    """Test GraphSelectorResult Pydantic model."""
    graph = create_test_graph()

    result = GraphSelectorResult(
        action=GraphSelectorAction.USE_SELECTED,
        selected_graph=graph,
    )

    assert result.action == GraphSelectorAction.USE_SELECTED
    assert result.selected_graph == graph

    # Test serialization
    data = result.model_dump()
    assert data["action"] == "use_selected"
    assert data["selected_graph"] is not None


def test_graph_selector_result_without_graph():
    """Test GraphSelectorResult can be created without graph."""
    result = GraphSelectorResult(
        action=GraphSelectorAction.CREATE_NEW,
        selected_graph=None,
    )

    assert result.action == GraphSelectorAction.CREATE_NEW
    assert result.selected_graph is None


def test_create_graph_list_item_formatting(mock_codebase_sdk):
    """Test formatting of graph list items."""
    modal = GraphSelectorModal(mock_codebase_sdk, None)

    # Test small entity count (< 1000)
    graph_small = create_test_graph(node_count=100, relationship_count=50)
    item_small = modal._create_graph_list_item(graph_small)
    assert item_small is not None

    # Test large entity count (>= 1000)
    graph_large = create_test_graph(node_count=5000, relationship_count=3000)
    item_large = modal._create_graph_list_item(graph_large)
    assert item_large is not None


def test_create_graph_list_item_with_current_indicator(mock_codebase_sdk):
    """Test that current graph gets special indicator."""
    current_graph = create_test_graph(graph_id="current", name="current-graph")
    modal = GraphSelectorModal(mock_codebase_sdk, current_graph)

    # Create item for current graph
    item = modal._create_graph_list_item(current_graph)
    assert item is not None

    # Create item for different graph
    other_graph = create_test_graph(graph_id="other", name="other-graph")
    item_other = modal._create_graph_list_item(other_graph)
    assert item_other is not None
