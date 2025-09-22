"""Screen for setting up the local .shotgun directory."""

from __future__ import annotations

from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Static

from shotgun.utils.file_system_utils import ensure_shotgun_directory_exists


class DirectorySetupScreen(Screen[None]):
    """Prompt the user to initialize the .shotgun directory."""

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
    """

    BINDINGS = [
        ("enter", "confirm", "Initialize"),
        ("escape", "cancel", "Exit"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="titlebox"):
            yield Static("Directory setup", id="directory-setup-title")
            yield Static("Shotgun keeps workspace data in a .shotgun directory.\n")
            yield Static("Initialize it in the current directory?\n")
            yield Static(f"[$foreground-muted]({Path.cwd().resolve()})[/]")
        with Horizontal(id="directory-actions"):
            yield Button(
                "Initialize and proceed \\[ENTER]", variant="primary", id="initialize"
            )
            yield Button("Exit without setup \\[ESC]", variant="default", id="exit")

    def on_mount(self) -> None:
        self.set_focus(self.query_one("#initialize", Button))

    def action_confirm(self) -> None:
        self._initialize_directory()

    def action_cancel(self) -> None:
        self._exit_application()

    @on(Button.Pressed, "#initialize")
    def _on_initialize_pressed(self) -> None:
        self._initialize_directory()

    @on(Button.Pressed, "#exit")
    def _on_exit_pressed(self) -> None:
        self._exit_application()

    def _initialize_directory(self) -> None:
        try:
            path = ensure_shotgun_directory_exists()
        except Exception as exc:  # pragma: no cover - defensive; textual path
            self.notify(f"Failed to initialize directory: {exc}", severity="error")
            return

        # Double-check a directory now exists; guard against unexpected filesystem state.
        if not path.is_dir():
            self.notify(
                "Unable to initialize .shotgun directory due to filesystem conflict.",
                severity="error",
            )
            return

        self.dismiss()

    def _exit_application(self) -> None:
        self.app.exit()
