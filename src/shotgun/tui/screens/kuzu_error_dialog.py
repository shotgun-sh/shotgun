"""Error dialog for Windows kuzu/graph database import failures."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

from shotgun.codebase.core.kuzu_compat import (
    _VC_INSTALL_SCRIPT,
    _VC_REDIST_URL,
    copy_vcpp_script_to_clipboard,
    open_vcpp_download_page,
)
from shotgun.logging_config import get_logger

logger = get_logger(__name__)


class KuzuErrorDialog(ModalScreen[bool]):
    """Error dialog for Windows kuzu import failures with copy/open buttons."""

    DEFAULT_CSS = """
        KuzuErrorDialog {
            align: center middle;
            background: rgba(0, 0, 0, 0.5);
        }

        KuzuErrorDialog > #dialog-container {
            width: 90%;
            max-width: 100;
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

        #script-display {
            padding: 1;
            margin: 1 0;
            background: $surface-darken-1;
            border: round $primary;
            overflow-x: auto;
        }

        #status-label {
            color: $success;
            padding: 1 0;
            min-height: 1;
        }

        #dialog-buttons {
            layout: horizontal;
            align-horizontal: center;
            height: auto;
            padding-top: 1;
        }

        #dialog-buttons Button {
            margin: 0 1;
        }
    """

    BINDINGS = [
        ("escape", "close", "Close"),
    ]

    def compose(self) -> ComposeResult:
        with Container(id="dialog-container"):
            yield Label("Code Indexing Requires Visual C++", id="error-title")
            yield Static(
                "The graph database library requires the Visual C++ Redistributable "
                "to be installed on Windows.\n\n"
                "Run this PowerShell script as Administrator:",
                id="error-message",
            )
            yield Static(_VC_INSTALL_SCRIPT, id="script-display")
            yield Static("", id="status-label")
            with Horizontal(id="dialog-buttons"):
                yield Button(
                    "Copy Script to Clipboard", id="copy-btn", variant="primary"
                )
                yield Button("Open Download Page", id="open-btn", variant="default")
                yield Button("Close", id="close-btn", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        event.stop()

        if event.button.id == "copy-btn":
            self._copy_script()
        elif event.button.id == "open-btn":
            self._open_download()
        elif event.button.id == "close-btn":
            self.dismiss(True)

    def _copy_script(self) -> None:
        """Copy the PowerShell installation script to clipboard."""
        status_label = self.query_one("#status-label", Static)

        if copy_vcpp_script_to_clipboard():
            status_label.update("Copied script to clipboard!")
            self.query_one("#copy-btn", Button).label = "Copied!"
            logger.debug("Copied VC++ installation script to clipboard")
        else:
            status_label.update(f"Could not copy. Download from: {_VC_REDIST_URL}")
            logger.warning("Failed to copy VC++ script to clipboard")

    def _open_download(self) -> None:
        """Open the download page in the default browser."""
        status_label = self.query_one("#status-label", Static)

        if open_vcpp_download_page():
            status_label.update("Opened download page in browser")
            logger.debug(f"Opened VC++ download page: {_VC_REDIST_URL}")
        else:
            status_label.update(f"Could not open browser. URL: {_VC_REDIST_URL}")
            logger.warning("Failed to open VC++ download page")

    def action_close(self) -> None:
        """Close the dialog."""
        self.dismiss(True)
