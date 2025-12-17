"""Modal for deciding whether to reuse existing graph or create new one."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel
from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

from shotgun.codebase.models import CodebaseGraph


class GraphChoice(StrEnum):
    """User's choice for handling existing graph."""

    REUSE = "reuse"
    NEW = "new"
    CANCEL = "cancel"


class GraphDecisionResult(BaseModel):
    """Result from graph decision modal."""

    choice: GraphChoice
    existing_graph: CodebaseGraph | None = None


class GraphDecisionModal(ModalScreen[GraphDecisionResult | None]):
    """Modal for choosing whether to reuse existing graph or create new one.

    Shown when:
    - User opens a codebase that has an existing graph
    - Global preference is set to ASK

    Options:
    - Reuse Graph: Load and continue with existing graph
    - Create New: Build a new graph (replaces existing)
    - Cancel: Don't do anything
    """

    DEFAULT_CSS = """
        GraphDecisionModal {
            align: center middle;
            background: rgba(0, 0, 0, 0.5);
        }

        GraphDecisionModal > #dialog-container {
            width: 70%;
            max-width: 80;
            height: auto;
            border: thick $primary;
            padding: 1 2;
            layout: vertical;
            background: $surface;
        }

        GraphDecisionModal #dialog-title {
            text-style: bold;
            color: $text;
            padding-bottom: 1;
            text-align: center;
        }

        GraphDecisionModal #dialog-message {
            color: $text-muted;
            padding-bottom: 1;
        }

        GraphDecisionModal #graph-info {
            background: $panel;
            padding: 1 2;
            margin: 1 0;
            border-left: thick $accent;
        }

        GraphDecisionModal #graph-info-title {
            text-style: bold;
            color: $accent;
        }

        GraphDecisionModal #dialog-buttons {
            layout: horizontal;
            align-horizontal: center;
            height: auto;
            padding-top: 1;
        }

        GraphDecisionModal Button {
            margin: 0 1;
            min-width: 16;
        }
    """

    def __init__(self, existing_graph: CodebaseGraph) -> None:
        """Initialize the modal with information about the existing graph.

        Args:
            existing_graph: The existing graph found for this codebase path
        """
        super().__init__()
        self.existing_graph = existing_graph

    def compose(self) -> ComposeResult:
        """Compose the modal UI."""
        with Container(id="dialog-container"):
            yield Label("Existing Graph Found", id="dialog-title")
            yield Static(
                f"A saved graph already exists for this codebase.",
                id="dialog-message",
            )

            # Show graph info
            with Container(id="graph-info"):
                yield Static("Graph Information", id="graph-info-title")
                yield Static(f"Name: {self.existing_graph.name}")
                yield Static(f"Graph ID: {self.existing_graph.graph_id}")
                yield Static(
                    f"Nodes: {self.existing_graph.node_count:,} | "
                    f"Relationships: {self.existing_graph.relationship_count:,}"
                )

            yield Static(
                "\nWhat would you like to do?",
                id="dialog-question",
            )

            with Horizontal(id="dialog-buttons"):
                yield Button(
                    "Use Existing Graph",
                    id="btn-reuse",
                    variant="primary",
                )
                yield Button(
                    "Create New Graph",
                    id="btn-new",
                    variant="default",
                )
                yield Button(
                    "Cancel",
                    id="btn-cancel",
                    variant="default",
                )

    def on_mount(self) -> None:
        """Focus the reuse button by default (safest option)."""
        self.query_one("#btn-reuse", Button).focus()

    @on(Button.Pressed, "#btn-reuse")
    def handle_reuse(self, event: Button.Pressed) -> None:
        """User chose to reuse the existing graph."""
        event.stop()
        self.dismiss(
            GraphDecisionResult(
                choice=GraphChoice.REUSE,
                existing_graph=self.existing_graph,
            )
        )

    @on(Button.Pressed, "#btn-new")
    def handle_new(self, event: Button.Pressed) -> None:
        """User chose to create a new graph."""
        event.stop()
        self.dismiss(
            GraphDecisionResult(
                choice=GraphChoice.NEW,
                existing_graph=self.existing_graph,
            )
        )

    @on(Button.Pressed, "#btn-cancel")
    def handle_cancel(self, event: Button.Pressed) -> None:
        """User cancelled the operation."""
        event.stop()
        self.dismiss(
            GraphDecisionResult(
                choice=GraphChoice.CANCEL,
                existing_graph=self.existing_graph,
            )
        )

    def on_key(self, event) -> None:
        """Handle keyboard shortcuts."""
        if event.key == "escape":
            event.stop()
            self.dismiss(
                GraphDecisionResult(
                    choice=GraphChoice.CANCEL,
                    existing_graph=self.existing_graph,
                )
            )
