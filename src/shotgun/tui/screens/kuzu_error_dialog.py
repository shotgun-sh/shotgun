"""Error dialog for Windows kuzu/graph database import failures."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

from shotgun.codebase.core.kuzu_compat import (
    _VC_REDIST_URL,
    _WINDOWS_INSTALL_INSTRUCTIONS,
    copy_vcpp_instructions_to_clipboard,
)
from shotgun.logging_config import get_logger

logger = get_logger(__name__)


class KuzuErrorDialog(ModalScreen[bool]):
    """Error dialog for Windows kuzu import failures with copy button."""

    DEFAULT_CSS = """
        KuzuErrorDialog {
            align: center middle;
            background: rgba(0, 0, 0, 0.5);
        }

        KuzuErrorDialog > #dialog-container {
            width: 80%;
            max-width: 90;
            height: auto;
            max-height: 90%;
            border: wide $error;
            padding: 1 2;
            layout: vertical;
            background: $surface;
        }

        #error-title {
            text-style: bold;
            color: $error;
            padding-bottom: 1;
        }

        #error-message {
            padding: 1 0;
        }

        #instructions {
            padding: 1 0;
            color: $text-muted;
        }

        #url-display {
            padding: 1;
            background: $surface-darken-1;
            border: round $primary;
        }

        #status-label {
            color: $success;
            padding: 1 0;
        }

        #dialog-buttons {
            layout: horizontal;
            align-horizontal: right;
            height: auto;
            padding-top: 1;
        }

        #dialog-buttons Button {
            margin-left: 1;
        }
    """

    BINDINGS = [
        ("escape", "close", "Close"),
    ]

    def compose(self) -> ComposeResult:
        with Container(id="dialog-container"):
            yield Label("⚠ Graph Database Import Failed", id="error-title")
            yield Static(
                "The graph database library failed to load. "
                "This typically occurs on Windows when the Visual C++ "
                "Redistributable is not installed.\n\n"
                "Install instructions:",
                id="error-message",
            )
            yield Static(_WINDOWS_INSTALL_INSTRUCTIONS.strip(), id="instructions")
            yield Static(f"Download URL: {_VC_REDIST_URL}", id="url-display")
            yield Static("", id="status-label")
            with Horizontal(id="dialog-buttons"):
                yield Button(
                    "Copy Download URL", id="copy-btn", variant="primary"
                )
                yield Button("Close", id="close-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        event.stop()

        if event.button.id == "copy-btn":
            self._copy_url()
        elif event.button.id == "close-btn":
            self.dismiss(True)

    def _copy_url(self) -> None:
        """Copy the VC++ download URL to clipboard."""
        status_label = self.query_one("#status-label", Static)

        if copy_vcpp_instructions_to_clipboard():
            status_label.update("✓ Copied URL to clipboard!")
            self.query_one("#copy-btn", Button).label = "Copied!"
            logger.debug(f"Copied VC++ URL to clipboard: {_VC_REDIST_URL}")
        else:
            status_label.update(
                f"⚠ Could not copy. Please manually copy: {_VC_REDIST_URL}"
            )
            logger.warning("Failed to copy VC++ URL to clipboard")

    def action_close(self) -> None:
        """Close the dialog."""
        self.dismiss(True)
