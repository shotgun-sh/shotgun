"""Dialog shown when the database is locked by another process."""

from textual import on
from textual.app import ComposeResult
from textual.containers import Container
from textual.events import Resize
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

from shotgun.tui.layout import COMPACT_HEIGHT_THRESHOLD


class DatabaseLockedDialog(ModalScreen[bool]):
    """Dialog shown when the database is locked by another process.

    This modal informs the user that another shotgun instance has the database
    open, and offers options to retry (after closing the other instance) or cancel.

    Args:
        codebase_name: Name of the codebase that is locked

    Returns:
        True if user wants to retry, False if user cancels
    """

    DEFAULT_CSS = """
        DatabaseLockedDialog {
            align: center middle;
            background: rgba(0, 0, 0, 0.0);
        }

        DatabaseLockedDialog > #dialog-container {
            width: 60%;
            max-width: 70;
            height: auto;
            border: wide $warning;
            padding: 1 2;
            layout: vertical;
            background: $surface;
        }

        #dialog-title {
            text-style: bold;
            color: $warning;
            padding-bottom: 1;
        }

        #dialog-message {
            padding-bottom: 1;
            color: $text-muted;
        }

        #dialog-buttons {
            layout: horizontal;
            align-horizontal: right;
            height: auto;
        }

        #dialog-buttons Button {
            margin-left: 1;
        }

        /* Compact styles for short terminals */
        #dialog-container.compact {
            padding: 0 2;
            max-height: 98%;
        }

        #dialog-title.compact {
            padding-bottom: 0;
        }

        #dialog-message.compact {
            padding-bottom: 0;
        }
    """

    def __init__(self, codebase_name: str = "") -> None:
        """Initialize the dialog.

        Args:
            codebase_name: Name of the codebase that is locked
        """
        super().__init__()
        self.codebase_name = codebase_name

    def compose(self) -> ComposeResult:
        """Compose the dialog widgets."""
        with Container(id="dialog-container"):
            yield Label("Database In Use", id="dialog-title")
            message = (
                "Another shotgun instance has this codebase open.\n\n"
                "Only one shotgun instance can access a codebase at a time. "
                "Please close the other instance and try again."
            )
            if self.codebase_name:
                message = f"Codebase: {self.codebase_name}\n\n" + message
            yield Static(message, id="dialog-message")
            with Container(id="dialog-buttons"):
                yield Button("Retry", id="retry", variant="primary")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        """Set up the dialog after mounting."""
        # Focus retry button - user likely wants to retry after closing other instance
        self.query_one("#retry", Button).focus()

        # Apply compact layout if starting in a short terminal
        self._apply_compact_layout(self.app.size.height < COMPACT_HEIGHT_THRESHOLD)

    @on(Resize)
    def handle_resize(self, event: Resize) -> None:
        """Adjust layout based on terminal height."""
        self._apply_compact_layout(event.size.height < COMPACT_HEIGHT_THRESHOLD)

    def _apply_compact_layout(self, compact: bool) -> None:
        """Apply or remove compact layout classes for short terminals."""
        container = self.query_one("#dialog-container")
        title = self.query_one("#dialog-title")
        message = self.query_one("#dialog-message")

        if compact:
            container.add_class("compact")
            title.add_class("compact")
            message.add_class("compact")
        else:
            container.remove_class("compact")
            title.remove_class("compact")
            message.remove_class("compact")

    @on(Button.Pressed, "#cancel")
    def handle_cancel(self, event: Button.Pressed) -> None:
        """Handle cancel button press."""
        event.stop()
        self.dismiss(False)

    @on(Button.Pressed, "#retry")
    def handle_retry(self, event: Button.Pressed) -> None:
        """Handle retry button press."""
        event.stop()
        self.dismiss(True)
