"""Modal for configuring global graph behavior preferences."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Label, ListView, ListItem, Static

from shotgun.agents.config.manager import ConfigManager
from shotgun.agents.config.models import PersistentGraphOpenBehavior


class GraphSettingsModal(ModalScreen[bool]):
    """Modal for configuring how Shotgun handles existing graphs.

    Allows users to set their global preference for what happens when
    opening a codebase with an existing graph:
    - ASK: Show modal each time (default)
    - ALWAYS_REUSE: Automatically load existing graph
    - ALWAYS_NEW: Always create new graph

    Returns:
        bool: True if settings were changed and saved, False if cancelled
    """

    DEFAULT_CSS = """
        GraphSettingsModal {
            align: center middle;
            background: rgba(0, 0, 0, 0.5);
        }

        GraphSettingsModal > #dialog-container {
            width: 70%;
            max-width: 70;
            height: auto;
            border: thick $primary;
            padding: 1 2;
            layout: vertical;
            background: $surface;
        }

        GraphSettingsModal #dialog-title {
            text-style: bold;
            color: $text;
            padding-bottom: 1;
            text-align: center;
        }

        GraphSettingsModal #dialog-message {
            color: $text-muted;
            padding-bottom: 1;
        }

        GraphSettingsModal #options-list {
            height: auto;
            max-height: 10;
            border: solid $accent;
            margin: 1 0;
        }

        GraphSettingsModal #dialog-buttons {
            layout: horizontal;
            align-horizontal: center;
            height: auto;
            padding-top: 1;
        }

        GraphSettingsModal Button {
            margin: 0 1;
            min-width: 12;
        }

        GraphSettingsModal ListItem {
            height: auto;
            padding: 0 1;
        }

        GraphSettingsModal ListItem:hover {
            background: $boost;
        }

        GraphSettingsModal ListItem.-selected {
            background: $primary;
            text-style: bold;
        }
    """

    def __init__(self, config_manager: ConfigManager) -> None:
        """Initialize the modal.

        Args:
            config_manager: ConfigManager instance for reading/writing settings
        """
        super().__init__()
        self.config_manager = config_manager
        self.current_behavior: PersistentGraphOpenBehavior | None = None
        self.selected_behavior: PersistentGraphOpenBehavior | None = None

    async def on_mount(self) -> None:
        """Load current setting and set up UI."""
        # Load current behavior from config
        self.current_behavior = await self.config_manager.get_persistent_graph_behavior()
        self.selected_behavior = self.current_behavior

        # Highlight the current selection
        list_view = self.query_one("#options-list", ListView)
        behavior_to_index = {
            PersistentGraphOpenBehavior.ASK: 0,
            PersistentGraphOpenBehavior.ALWAYS_REUSE: 1,
            PersistentGraphOpenBehavior.ALWAYS_NEW: 2,
        }
        index = behavior_to_index.get(self.current_behavior, 0)
        list_view.index = index

        # Focus the save button
        self.query_one("#btn-save", Button).focus()

    def compose(self) -> ComposeResult:
        """Compose the modal UI."""
        with Container(id="dialog-container"):
            yield Label("Graph Behavior Preferences", id="dialog-title")
            yield Static(
                "Choose what happens when opening a codebase with an existing graph:",
                id="dialog-message",
            )

            with ListView(id="options-list"):
                yield ListItem(
                    Label(
                        "○ Ask me each time\n"
                        "  Show a modal to choose between reusing or creating new graph"
                    ),
                    id="option-ask",
                )
                yield ListItem(
                    Label(
                        "○ Always reuse existing graph\n"
                        "  Automatically load the saved graph without asking"
                    ),
                    id="option-always-reuse",
                )
                yield ListItem(
                    Label(
                        "○ Always create new graph\n"
                        "  Always start fresh, replacing any existing graph"
                    ),
                    id="option-always-new",
                )

            with Horizontal(id="dialog-buttons"):
                yield Button("Save", id="btn-save", variant="primary")
                yield Button("Cancel", id="btn-cancel", variant="default")

    @on(ListView.Selected)
    def handle_selection(self, event: ListView.Selected) -> None:
        """Handle option selection."""
        event.stop()
        # Map list item to behavior
        index_to_behavior = {
            0: PersistentGraphOpenBehavior.ASK,
            1: PersistentGraphOpenBehavior.ALWAYS_REUSE,
            2: PersistentGraphOpenBehavior.ALWAYS_NEW,
        }
        self.selected_behavior = index_to_behavior.get(event.list_view.index)

    @on(Button.Pressed, "#btn-save")
    async def handle_save(self, event: Button.Pressed) -> None:
        """Save the selected behavior and dismiss."""
        event.stop()

        # Only save if selection changed
        if self.selected_behavior != self.current_behavior:
            if self.selected_behavior is not None:
                await self.config_manager.set_persistent_graph_behavior(
                    self.selected_behavior
                )
                self.dismiss(True)
            else:
                # No selection made, dismiss without saving
                self.dismiss(False)
        else:
            # No change, dismiss without saving
            self.dismiss(False)

    @on(Button.Pressed, "#btn-cancel")
    def handle_cancel(self, event: Button.Pressed) -> None:
        """Cancel without saving."""
        event.stop()
        self.dismiss(False)

    def on_key(self, event) -> None:
        """Handle keyboard shortcuts."""
        if event.key == "escape":
            event.stop()
            self.dismiss(False)
