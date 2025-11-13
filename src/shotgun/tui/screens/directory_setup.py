"""Screen for displaying .shotgun directory creation errors."""

from __future__ import annotations

from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Label, Static


class DirectorySetupScreen(Screen[None]):
    """Display an error when .shotgun directory creation fails."""

    def __init__(self, error_message: str) -> None:
        """Initialize the error screen.

        Args:
            error_message: The error message to display to the user.
        """
        super().__init__()
        self.error_message = error_message

    CSS = """
        DirectorySetupScreen {
            layout: vertical;
        }

        DirectorySetupScreen > * {
            height: auto;
        }

        #titlebox {
            height: auto;
            margin: 2 0;
            padding: 1;
            border: hkey $border;
            content-align: center middle;

            & > * {
                text-align: center;
            }
        }

        #directory-setup-title {
            padding: 1 0;
            text-style: bold;
            color: $text-accent;
        }

        #directory-setup-summary {
            padding: 0 1;
        }

        #directory-actions {
            padding: 1;
            content-align: center middle;
            align: center middle;
        }

        #directory-actions > * {
            margin-right: 2;
        }

        #directory-status {
            height: auto;
            padding: 0 1;
            min-height: 1;
            color: $error;
            text-align: center;
        }
    """

    BINDINGS = [
        ("enter", "retry", "Retry"),
        ("escape", "cancel", "Exit"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="titlebox"):
            yield Static(
                "Failed to create .shotgun directory", id="directory-setup-title"
            )
            yield Static("Shotgun was unable to create the .shotgun directory in:\n")
            yield Static(f"[$foreground-muted]({Path.cwd().resolve()})[/]\n")
            yield Static(f"[bold red]Error:[/] {self.error_message}\n")
            yield Static(
                "This directory is required for storing workspace data. "
                "Please check permissions and try again."
            )
        yield Label("", id="directory-status")
        with Horizontal(id="directory-actions"):
            yield Button("Retry \\[ENTER]", variant="primary", id="retry")
            yield Button("Exit \\[ESC]", variant="default", id="exit")

    def on_mount(self) -> None:
        self.set_focus(self.query_one("#retry", Button))

    def action_retry(self) -> None:
        """Retry by dismissing the screen, which will trigger refresh_startup_screen."""
        self.dismiss()

    def action_cancel(self) -> None:
        """Exit the application."""
        self.app.exit()

    @on(Button.Pressed, "#retry")
    def _on_retry_pressed(self) -> None:
        """Retry by dismissing the screen."""
        self.dismiss()

    @on(Button.Pressed, "#exit")
    def _on_exit_pressed(self) -> None:
        """Exit the application."""
        self.app.exit()
