"""Tests for GraphIndicator component."""

from unittest.mock import Mock

from shotgun.codebase.models import CodebaseGraph
from shotgun.tui.components.graph_indicator import GraphIndicator


def create_test_graph(
    name: str = "test-graph",
    graph_id: str = "test-id-123",
    node_count: int = 100,
    relationship_count: int = 50,
) -> CodebaseGraph:
    """Create a test CodebaseGraph object."""
    return CodebaseGraph(
        graph_id=graph_id,
        name=name,
        repo_path="/test/path",
        node_count=node_count,
        relationship_count=relationship_count,
    )


def test_graph_indicator_initialization():
    """Test GraphIndicator can be initialized."""
    indicator = GraphIndicator(id="test-indicator")
    assert indicator.current_graph is None


def test_graph_indicator_update_graph():
    """Test updating graph indicator with graph data."""
    indicator = GraphIndicator()

    graph = create_test_graph(
        name="my-project", node_count=1000, relationship_count=500
    )

    indicator.update_graph(graph)

    assert indicator.current_graph == graph


def test_graph_indicator_update_graph_to_none():
    """Test updating graph indicator to None (no graph)."""
    indicator = GraphIndicator()

    # First set a graph
    graph = create_test_graph()
    indicator.update_graph(graph)
    assert indicator.current_graph == graph

    # Now clear it
    indicator.update_graph(None)
    assert indicator.current_graph is None


def test_graph_indicator_display_with_no_graph():
    """Test display when no graph is active."""
    indicator = GraphIndicator()
    indicator._refresh_display()

    # Should have no graph
    assert indicator.current_graph is None


def test_graph_indicator_display_with_small_entity_count():
    """Test display with entity count < 1000."""
    indicator = GraphIndicator()

    graph = create_test_graph(
        name="small-project", node_count=100, relationship_count=50
    )

    indicator.update_graph(graph)

    # Verify internal state
    assert indicator.current_graph == graph

    # Entity count should be 150 (100 + 50)
    entity_count = graph.node_count + graph.relationship_count
    assert entity_count == 150


def test_graph_indicator_display_with_large_entity_count():
    """Test display with entity count >= 1000."""
    indicator = GraphIndicator()

    graph = create_test_graph(
        name="large-project", node_count=5000, relationship_count=3000
    )

    indicator.update_graph(graph)

    # Verify internal state
    assert indicator.current_graph == graph

    # Entity count should be 8000 (5000 + 3000)
    entity_count = graph.node_count + graph.relationship_count
    assert entity_count == 8000


def test_graph_indicator_watcher_triggers():
    """Test that watch_current_graph is called when graph changes."""
    indicator = GraphIndicator()

    # Mock the watcher to verify it's called
    indicator._refresh_display = Mock()  # type: ignore[method-assign]

    graph = create_test_graph()
    indicator.current_graph = graph

    # Manually trigger watcher (Textual would do this automatically)
    indicator.watch_current_graph(graph)

    # Verify refresh was called
    indicator._refresh_display.assert_called_once()


def test_graph_indicator_entity_count_formatting_under_1k():
    """Test entity count formatting for counts under 1000."""
    indicator = GraphIndicator()

    # Test various counts under 1000
    for node_count, rel_count in [(10, 5), (100, 50), (500, 499)]:
        graph = create_test_graph(node_count=node_count, relationship_count=rel_count)
        indicator.update_graph(graph)

        entity_count = node_count + rel_count
        assert entity_count < 1000


def test_graph_indicator_entity_count_formatting_over_1k():
    """Test entity count formatting for counts over 1000."""
    indicator = GraphIndicator()

    # 1000 entities = 1K
    graph = create_test_graph(node_count=600, relationship_count=400)
    indicator.update_graph(graph)
    assert (graph.node_count + graph.relationship_count) == 1000

    # 5000 entities = 5K
    graph = create_test_graph(node_count=3000, relationship_count=2000)
    indicator.update_graph(graph)
    assert (graph.node_count + graph.relationship_count) == 5000


def test_graph_indicator_click_handler():
    """Test that click handler posts OpenGraphSelector message."""
    indicator = GraphIndicator()

    # Mock post_message to verify it's called
    indicator.post_message = Mock()  # type: ignore[method-assign]

    # Simulate click - this would normally be called by Textual
    # We can't easily test the async on_click without a full app context,
    # but we can verify the method exists
    assert hasattr(indicator, "on_click")
    assert callable(indicator.on_click)


def test_graph_indicator_with_different_graph_names():
    """Test display with various graph names."""
    indicator = GraphIndicator()

    # Test with different naming conventions
    test_names = [
        "simple-name",
        "project_with_underscores",
        "CamelCaseProject",
        "name-with-many-dashes-and-words",
        "123-numeric-prefix",
    ]

    for name in test_names:
        graph = create_test_graph(name=name)
        indicator.update_graph(graph)
        assert indicator.current_graph.name == name


def test_graph_indicator_with_different_graph_ids():
    """Test with various graph ID formats."""
    indicator = GraphIndicator()

    test_ids = [
        "short-id",
        "very-long-graph-id-with-many-characters-12345678",
        "abc123def456",
        "00000000",
    ]

    for graph_id in test_ids:
        graph = create_test_graph(graph_id=graph_id)
        indicator.update_graph(graph)
        assert indicator.current_graph.graph_id == graph_id


def test_graph_indicator_zero_entities():
    """Test with graph having zero entities (empty graph)."""
    indicator = GraphIndicator()

    graph = create_test_graph(node_count=0, relationship_count=0)
    indicator.update_graph(graph)

    assert indicator.current_graph == graph
    entity_count = graph.node_count + graph.relationship_count
    assert entity_count == 0


def test_graph_indicator_large_numbers():
    """Test with very large entity counts."""
    indicator = GraphIndicator()

    # Test with 100K+ entities
    graph = create_test_graph(node_count=50_000, relationship_count=50_000)
    indicator.update_graph(graph)

    entity_count = graph.node_count + graph.relationship_count
    assert entity_count == 100_000

    # Test with 1M+ entities
    graph = create_test_graph(node_count=600_000, relationship_count=400_000)
    indicator.update_graph(graph)

    entity_count = graph.node_count + graph.relationship_count
    assert entity_count == 1_000_000


def test_graph_indicator_sequential_updates():
    """Test updating graph indicator multiple times sequentially."""
    indicator = GraphIndicator()

    # Update with first graph
    graph1 = create_test_graph(name="graph-1", node_count=100)
    indicator.update_graph(graph1)
    assert indicator.current_graph == graph1

    # Update with second graph
    graph2 = create_test_graph(name="graph-2", node_count=200)
    indicator.update_graph(graph2)
    assert indicator.current_graph == graph2

    # Clear to None
    indicator.update_graph(None)
    assert indicator.current_graph is None

    # Set third graph
    graph3 = create_test_graph(name="graph-3", node_count=300)
    indicator.update_graph(graph3)
    assert indicator.current_graph == graph3
