"""Modal for selecting and managing graphs for the current codebase."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel
from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Label, ListItem, ListView, Static

from shotgun.codebase.models import CodebaseGraph
from shotgun.logging_config import get_logger
from shotgun.sdk.codebase import CodebaseSDK

logger = get_logger(__name__)


class GraphSelectorAction(StrEnum):
    """User's action from graph selector modal."""

    USE_SELECTED = "use_selected"
    CREATE_NEW = "create_new"
    OPEN_SETTINGS = "open_settings"
    CANCEL = "cancel"


class GraphSelectorResult(BaseModel):
    """Result from graph selector modal."""

    action: GraphSelectorAction
    selected_graph: CodebaseGraph | None = None


class GraphSelectorModal(ModalScreen[GraphSelectorResult | None]):
    """Modal for selecting, creating, or managing graphs.

    Allows users to:
    - View all available graphs for the current codebase
    - Select a graph to use
    - Create a new graph
    - Open graph settings
    - Cancel the operation

    Returns:
        GraphSelectorResult with action and optional selected graph
    """

    DEFAULT_CSS = """
        GraphSelectorModal {
            align: center middle;
            background: rgba(0, 0, 0, 0.5);
        }

        GraphSelectorModal > #dialog-container {
            width: 80%;
            max-width: 100;
            height: auto;
            max-height: 90%;
            border: thick $primary;
            padding: 1 2;
            layout: vertical;
            background: $surface;
        }

        GraphSelectorModal #dialog-title {
            text-style: bold;
            color: $text;
            padding-bottom: 1;
            text-align: center;
        }

        GraphSelectorModal #dialog-message {
            color: $text-muted;
            padding-bottom: 1;
        }

        GraphSelectorModal #graph-list {
            height: auto;
            max-height: 20;
            border: solid $accent;
            margin: 1 0;
        }

        GraphSelectorModal #dialog-buttons {
            layout: horizontal;
            align-horizontal: center;
            height: auto;
            padding-top: 1;
        }

        GraphSelectorModal Button {
            margin: 0 1;
            min-width: 16;
        }

        GraphSelectorModal ListItem {
            height: auto;
            padding: 1;
        }

        GraphSelectorModal ListItem:hover {
            background: $boost;
        }

        GraphSelectorModal ListItem.-selected {
            background: $primary 20%;
            border-left: thick $primary;
        }

        GraphSelectorModal #graph-name {
            text-style: bold;
            color: $text;
        }

        GraphSelectorModal #graph-meta {
            color: $text-muted;
        }

        GraphSelectorModal #no-graphs {
            text-align: center;
            color: $text-muted;
            padding: 2;
            text-style: italic;
        }
    """

    def __init__(
        self,
        codebase_sdk: CodebaseSDK,
        current_graph: CodebaseGraph | None = None,
    ) -> None:
        """Initialize the modal.

        Args:
            codebase_sdk: CodebaseSDK instance for querying graphs
            current_graph: Currently active graph (will be highlighted)
        """
        super().__init__()
        self.codebase_sdk = codebase_sdk
        self.current_graph = current_graph
        self.available_graphs: list[CodebaseGraph] = []
        self.selected_graph: CodebaseGraph | None = None

    def compose(self) -> ComposeResult:
        """Compose the modal UI."""
        with Container(id="dialog-container"):
            yield Label("Select Graph", id="dialog-title")
            yield Static(
                "Choose a graph to work with, create a new one, or manage settings:",
                id="dialog-message",
            )

            yield ListView(id="graph-list")

            with Horizontal(id="dialog-buttons"):
                yield Button(
                    "Use Selected",
                    id="btn-use",
                    variant="primary",
                )
                yield Button(
                    "Create New Graph",
                    id="btn-create",
                    variant="default",
                )
                yield Button(
                    "Settings...",
                    id="btn-settings",
                    variant="default",
                )
                yield Button(
                    "Cancel",
                    id="btn-cancel",
                    variant="default",
                )

    async def on_mount(self) -> None:
        """Load available graphs and populate list."""
        await self._load_graphs()
        self.query_one("#btn-use", Button).focus()

    async def _load_graphs(self) -> None:
        """Load available graphs from codebase service."""
        try:
            # Query filtered codebase service for graphs in current directory
            self.available_graphs = await self.codebase_sdk.service.list_graphs()
            logger.debug(f"Loaded {len(self.available_graphs)} available graphs")

            # Populate list view
            list_view = self.query_one("#graph-list", ListView)

            # Clear existing items
            for child in list(list_view.children):
                child.remove()

            if not self.available_graphs:
                # Show "no graphs" message
                list_view.append(
                    ListItem(
                        Label("No graphs available for this codebase.", id="no-graphs"),
                        disabled=True,
                    )
                )
                # Disable "Use Selected" button
                self.query_one("#btn-use", Button).disabled = True
            else:
                # Add graph items
                for i, graph in enumerate(self.available_graphs):
                    list_view.append(self._create_graph_list_item(graph))

                # Highlight current graph if present
                if self.current_graph:
                    for i, graph in enumerate(self.available_graphs):
                        if graph.graph_id == self.current_graph.graph_id:
                            list_view.index = i
                            self.selected_graph = graph
                            break

                # If no current graph, select first one
                if self.selected_graph is None and self.available_graphs:
                    list_view.index = 0
                    self.selected_graph = self.available_graphs[0]

        except Exception as e:
            logger.error(f"Failed to load graphs: {e}", exc_info=True)
            # Show error in list
            list_view = self.query_one("#graph-list", ListView)
            list_view.append(
                ListItem(
                    Label(f"Error loading graphs: {e}", id="no-graphs"),
                    disabled=True,
                )
            )
            self.query_one("#btn-use", Button).disabled = True

    def _create_graph_list_item(self, graph: CodebaseGraph) -> ListItem:
        """Create a list item for a graph.

        Args:
            graph: The graph to create an item for

        Returns:
            ListItem widget with graph information
        """
        # Format entity count
        entity_count = graph.node_count + graph.relationship_count
        if entity_count >= 1000:
            count_str = f"{entity_count // 1000}K"
        else:
            count_str = str(entity_count)

        # Format last modified (if available)
        # For now, just show entity count - timestamp can be added later
        meta_info = f"{count_str} entities"

        # Check if this is the current graph
        is_current = (
            self.current_graph and graph.graph_id == self.current_graph.graph_id
        )
        current_indicator = " (current)" if is_current else ""

        # Create item with graph info
        item_content = Container(
            Static(f"{graph.name}{current_indicator}", id="graph-name"),
            Static(f"ID: {graph.graph_id} | {meta_info}", id="graph-meta"),
        )

        return ListItem(item_content, id=f"graph-{graph.graph_id}")

    @on(ListView.Selected)
    def handle_selection(self, event: ListView.Selected) -> None:
        """Handle graph selection from list."""
        event.stop()

        # Get selected graph from list index
        if 0 <= event.list_view.index < len(self.available_graphs):
            self.selected_graph = self.available_graphs[event.list_view.index]
            logger.debug(f"Selected graph: {self.selected_graph.name}")

            # Double-click on item = use it
            self._handle_use_selected()

    @on(ListView.Highlighted)
    def handle_highlight(self, event: ListView.Highlighted) -> None:
        """Handle graph highlighting (arrow keys)."""
        event.stop()

        # Get highlighted graph from list index
        if 0 <= event.list_view.index < len(self.available_graphs):
            self.selected_graph = self.available_graphs[event.list_view.index]
            logger.debug(f"Highlighted graph: {self.selected_graph.name}")

    @on(Button.Pressed, "#btn-use")
    def handle_use_button(self, event: Button.Pressed) -> None:
        """Handle 'Use Selected' button press."""
        event.stop()
        self._handle_use_selected()

    def _handle_use_selected(self) -> None:
        """Handle using the selected graph."""
        if self.selected_graph:
            self.dismiss(
                GraphSelectorResult(
                    action=GraphSelectorAction.USE_SELECTED,
                    selected_graph=self.selected_graph,
                )
            )
        else:
            # No graph selected - shouldn't happen but handle gracefully
            logger.warning("Use Selected pressed but no graph selected")

    @on(Button.Pressed, "#btn-create")
    def handle_create(self, event: Button.Pressed) -> None:
        """Handle 'Create New Graph' button press."""
        event.stop()
        self.dismiss(
            GraphSelectorResult(
                action=GraphSelectorAction.CREATE_NEW,
                selected_graph=None,
            )
        )

    @on(Button.Pressed, "#btn-settings")
    def handle_settings(self, event: Button.Pressed) -> None:
        """Handle 'Settings' button press."""
        event.stop()
        self.dismiss(
            GraphSelectorResult(
                action=GraphSelectorAction.OPEN_SETTINGS,
                selected_graph=None,
            )
        )

    @on(Button.Pressed, "#btn-cancel")
    def handle_cancel(self, event: Button.Pressed) -> None:
        """Handle 'Cancel' button press."""
        event.stop()
        self.dismiss(
            GraphSelectorResult(
                action=GraphSelectorAction.CANCEL,
                selected_graph=None,
            )
        )

    def on_key(self, event) -> None:
        """Handle keyboard shortcuts."""
        if event.key == "escape":
            event.stop()
            self.dismiss(
                GraphSelectorResult(
                    action=GraphSelectorAction.CANCEL,
                    selected_graph=None,
                )
            )
