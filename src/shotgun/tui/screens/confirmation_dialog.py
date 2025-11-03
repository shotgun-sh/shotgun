"""Reusable confirmation dialog for destructive actions in the TUI."""

from typing import Literal

from textual import on
from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

ButtonVariant = Literal["default", "primary", "success", "warning", "error"]


class ConfirmationDialog(ModalScreen[bool]):
    """Reusable confirmation dialog for destructive actions.

    This modal dialog presents a confirmation prompt with a title, explanatory
    message, and customizable confirm/cancel buttons. Useful for preventing
    accidental destructive actions like clearing data or deleting resources.

    Args:
        title: Dialog title text (e.g., "Clear conversation?")
        message: Detailed explanation of what will happen
        confirm_label: Label for the confirm button (default: "Confirm")
        cancel_label: Label for the cancel button (default: "Cancel")
        confirm_variant: Button variant for confirm button (default: "warning")
        danger: Whether this is a dangerous/destructive action (default: False)

    Returns:
        True if user confirms, False if user cancels

    Example:
        ```python
        should_delete = await self.app.push_screen_wait(
            ConfirmationDialog(
                title="Delete item?",
                message="This will permanently delete the item. This cannot be undone.",
                confirm_label="Delete",
                cancel_label="Keep",
                confirm_variant="warning",
                danger=True,
            )
        )
        if should_delete:
            # Proceed with deletion
            ...
        ```
    """

    DEFAULT_CSS = """
        ConfirmationDialog {
            align: center middle;
            background: rgba(0, 0, 0, 0.0);
        }

        ConfirmationDialog > #dialog-container {
            width: 60%;
            max-width: 70;
            height: auto;
            border: wide $warning;
            padding: 1 2;
            layout: vertical;
            background: $surface;
        }

        ConfirmationDialog.danger > #dialog-container {
            border: wide $error;
        }

        #dialog-title {
            text-style: bold;
            color: $text;
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
    """

    def __init__(
        self,
        title: str,
        message: str,
        confirm_label: str = "Confirm",
        cancel_label: str = "Cancel",
        confirm_variant: ButtonVariant = "warning",
        danger: bool = False,
    ) -> None:
        """Initialize the confirmation dialog.

        Args:
            title: Dialog title text
            message: Detailed explanation of what will happen
            confirm_label: Label for the confirm button
            cancel_label: Label for the cancel button
            confirm_variant: Button variant for confirm button
            danger: Whether this is a dangerous/destructive action
        """
        super().__init__()
        self.title_text = title
        self.message_text = message
        self.confirm_label = confirm_label
        self.cancel_label = cancel_label
        self.confirm_variant = confirm_variant
        self.is_danger = danger

    def compose(self) -> ComposeResult:
        """Compose the dialog widgets."""
        with Container(id="dialog-container"):
            yield Label(self.title_text, id="dialog-title")
            yield Static(self.message_text, id="dialog-message")
            with Container(id="dialog-buttons"):
                yield Button(
                    self.confirm_label,
                    id="confirm",
                    variant=self.confirm_variant,
                )
                yield Button(self.cancel_label, id="cancel")

    def on_mount(self) -> None:
        """Set up the dialog after mounting."""
        # Apply danger class if needed
        if self.is_danger:
            self.add_class("danger")

        # Focus cancel button by default for safety
        self.query_one("#cancel", Button).focus()

    @on(Button.Pressed, "#cancel")
    def handle_cancel(self, event: Button.Pressed) -> None:
        """Handle cancel button press."""
        event.stop()
        self.dismiss(False)

    @on(Button.Pressed, "#confirm")
    def handle_confirm(self, event: Button.Pressed) -> None:
        """Handle confirm button press."""
        event.stop()
        self.dismiss(True)
