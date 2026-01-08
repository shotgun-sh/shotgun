"""Dialog shown when the database is locked by another process."""

import webbrowser

import pyperclip  # type: ignore[import-untyped]
from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.events import Resize
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

from shotgun.exceptions import SHOTGUN_CONTACT_EMAIL
from shotgun.posthog_telemetry import track_event
from shotgun.tui.layout import COMPACT_HEIGHT_THRESHOLD

# Discord invite link for support
DISCORD_LINK = "https://discord.gg/5RmY6J2N7s"


class DatabaseLockedDialog(ModalScreen[bool]):
    """Dialog shown when the database is locked by another process.

    This modal informs the user that another shotgun instance has the database
    open, and offers options to retry (after closing the other instance) or cancel.

    Returns:
        True if user wants to retry, False if user cancels
    """

    DEFAULT_CSS = """
        DatabaseLockedDialog {
            align: center middle;
            background: rgba(0, 0, 0, 0.0);
        }

        DatabaseLockedDialog > #dialog-container {
            width: 70%;
            max-width: 80;
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

        #support-buttons {
            layout: horizontal;
            height: auto;
            padding-bottom: 1;
        }

        #support-buttons Button {
            margin-right: 1;
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

    def compose(self) -> ComposeResult:
        """Compose the dialog widgets."""
        with Container(id="dialog-container"):
            yield Label("Codebase Index Unavailable", id="dialog-title")
            message = (
                "Unable to access the codebase index because another shotgun "
                "instance appears to be running.\n\n"
                "To resolve this:\n"
                "1. Close any other shotgun instances and click Retry\n"
                "2. If no other instance is running and you still see this error, "
                "contact support:"
            )
            yield Static(message, id="dialog-message")
            with Horizontal(id="support-buttons"):
                yield Button(
                    f"Copy Support Email [{SHOTGUN_CONTACT_EMAIL}]", id="copy-email"
                )
                yield Button("Open Support Discord", id="open-discord")
            with Container(id="dialog-buttons"):
                yield Button("Retry", id="retry", variant="primary")
                yield Button("Quit", id="cancel")

    def on_mount(self) -> None:
        """Set up the dialog after mounting."""
        # Track this event in PostHog
        track_event("database_locked_dialog_shown", {})

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

    @on(Button.Pressed, "#copy-email")
    def handle_copy_email(self, event: Button.Pressed) -> None:
        """Copy support email to clipboard."""
        event.stop()
        pyperclip.copy(SHOTGUN_CONTACT_EMAIL)
        track_event("database_locked_dialog_copy_email", {})
        self.notify("Email copied to clipboard", severity="information")

    @on(Button.Pressed, "#open-discord")
    def handle_open_discord(self, event: Button.Pressed) -> None:
        """Open Discord link in browser."""
        event.stop()
        webbrowser.open(DISCORD_LINK)
        track_event("database_locked_dialog_open_discord", {})
