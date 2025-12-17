"""Graph indicator component for showing current graph information."""

from textual.reactive import reactive
from textual.widgets import Static

from shotgun.codebase.models import CodebaseGraph


class GraphIndicator(Static):
    """Display current graph information with click-to-switch functionality."""

    DEFAULT_CSS = """
    GraphIndicator {
        width: auto;
        height: 1;
        text-align: right;
    }

    GraphIndicator:hover {
        text-style: underline;
        cursor: pointer;
    }
    """

    current_graph: reactive[CodebaseGraph | None] = reactive(None)

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)

    def update_graph(self, graph: CodebaseGraph | None) -> None:
        """Update the indicator with new graph data.

        Args:
            graph: Current graph or None if no graph is active
        """
        self.current_graph = graph
        self._refresh_display()

    def _refresh_display(self) -> None:
        """Refresh the display with current graph data."""
        if self.current_graph is None:
            self.update("[$foreground-muted]No graph[/]")
            return

        # Format graph name with entity count
        graph = self.current_graph
        entity_count = graph.node_count + graph.relationship_count

        # Format entity count in a compact way
        if entity_count >= 1000:
            count_str = f"{entity_count // 1000}K"
        else:
            count_str = str(entity_count)

        # Build display string
        parts = [
            "[$foreground-muted]Graph:[/]",
            f"[bold]{graph.name}[/]",
            f"[$foreground-muted]({count_str} entities)[/]",
        ]

        self.update(" ".join(parts))

    def watch_current_graph(self, graph: CodebaseGraph | None) -> None:
        """React to graph changes."""
        self._refresh_display()

    async def on_click(self) -> None:
        """Handle click event to open graph selector."""
        # Post message to parent screen to open graph selector
        from shotgun.tui.screens.chat_screen.messages import OpenGraphSelector

        self.post_message(OpenGraphSelector())
