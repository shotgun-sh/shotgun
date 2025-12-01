"""Dialog for creating a new spec."""

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.events import Resize
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static, TextArea

from shotgun.logging_config import get_logger
from shotgun.tui.layout import COMPACT_HEIGHT_THRESHOLD
from shotgun.tui.screens.shared_specs.models import CreateSpecResult

logger = get_logger(__name__)


class CreateSpecDialog(ModalScreen[CreateSpecResult | None]):
    """Dialog for creating a new spec.

    Shows a form with:
    - Name input (required)
    - Description textarea (optional)
    - "Make public?" toggle (default: off)

    Returns CreateSpecResult or None if cancelled.
    """

    DEFAULT_CSS = """
        CreateSpecDialog {
            align: center middle;
            background: rgba(0, 0, 0, 0.0);
        }

        CreateSpecDialog > #dialog-container {
            width: 70%;
            max-width: 80;
            height: auto;
            border: wide $primary;
            padding: 1 2;
            layout: vertical;
            background: $surface;
        }

        #dialog-title {
            text-style: bold;
            color: $text-accent;
            padding-bottom: 1;
            text-align: center;
        }

        .form-row {
            height: auto;
            padding: 1 0;
        }

        .form-label {
            padding-bottom: 0;
        }

        .form-hint {
            color: $text-muted;
            padding-top: 0;
        }

        #name-input {
            width: 100%;
        }

        #description-input {
            width: 100%;
            height: 5;
        }

        .switch-row {
            layout: horizontal;
            height: auto;
            padding: 1 0;
            align-vertical: middle;
        }

        .switch-row Switch {
            margin-right: 1;
        }

        .switch-label {
            padding-left: 1;
        }

        .switch-hint {
            color: $text-muted;
            padding-left: 1;
        }

        #error-label {
            color: $error;
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

        /* Compact styles for short terminals */
        CreateSpecDialog.compact #dialog-container {
            padding: 0 2;
            max-height: 98%;
        }

        CreateSpecDialog.compact #dialog-title {
            padding-bottom: 0;
        }

        CreateSpecDialog.compact .form-row {
            padding: 0;
        }

        CreateSpecDialog.compact .form-hint {
            display: none;
        }

        CreateSpecDialog.compact #description-input {
            height: 3;
        }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self) -> None:
        """Initialize the dialog."""
        super().__init__()

    def compose(self) -> ComposeResult:
        """Compose the dialog widgets."""
        with Container(id="dialog-container"):
            yield Label("Create new spec", id="dialog-title")

            # Name field
            with Container(classes="form-row"):
                yield Label("Name", classes="form-label")
                yield Input(
                    placeholder="My Spec",
                    id="name-input",
                )
                yield Static(
                    "A unique name for your spec (1-255 characters)",
                    classes="form-hint",
                )

            # Description field
            with Container(classes="form-row"):
                yield Label("Description (optional)", classes="form-label")
                yield TextArea(
                    id="description-input",
                )
                yield Static(
                    "Describe what this spec contains",
                    classes="form-hint",
                )

            # Public toggle - hidden for now
            # with Container(classes="switch-row"):
            #     yield Switch(value=False, id="public-switch")
            #     yield Label("Make public", classes="switch-label")
            # yield Static(
            #     "Public specs can be viewed by anyone with the link",
            #     classes="switch-hint",
            # )

            # Error label
            yield Static("", id="error-label")

            # Buttons
            with Horizontal(id="dialog-buttons"):
                yield Button("Create", variant="primary", id="create")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        """Focus name input when dialog is mounted."""
        self.query_one("#name-input", Input).focus()
        self.query_one("#error-label", Static).display = False

        # Apply compact layout if starting in a short terminal
        self._apply_compact_layout(self.app.size.height < COMPACT_HEIGHT_THRESHOLD)

    @on(Resize)
    def handle_resize(self, event: Resize) -> None:
        """Adjust layout based on terminal height."""
        self._apply_compact_layout(event.size.height < COMPACT_HEIGHT_THRESHOLD)

    def _apply_compact_layout(self, compact: bool) -> None:
        """Apply or remove compact layout class for short terminals."""
        if compact:
            self.add_class("compact")
        else:
            self.remove_class("compact")

    def _validate(self) -> str | None:
        """Validate the form.

        Returns:
            Error message if validation fails, None if valid.
        """
        name = self.query_one("#name-input", Input).value.strip()

        if not name:
            return "Name is required"

        if len(name) > 255:
            return "Name must be 255 characters or less"

        return None

    def _show_error(self, message: str) -> None:
        """Show an error message."""
        error_label = self.query_one("#error-label", Static)
        error_label.update(f"Error: {message}")
        error_label.display = True

    def _hide_error(self) -> None:
        """Hide the error message."""
        self.query_one("#error-label", Static).display = False

    @on(Button.Pressed, "#create")
    def _on_create(self, event: Button.Pressed) -> None:
        """Handle create button."""
        event.stop()

        # Validate
        error = self._validate()
        if error:
            self._show_error(error)
            return

        self._hide_error()

        # Get values
        name = self.query_one("#name-input", Input).value.strip()
        description = self.query_one("#description-input", TextArea).text.strip()
        # Public toggle is hidden for now - always create as team-only
        is_public = False

        self.dismiss(
            CreateSpecResult(
                name=name,
                description=description if description else None,
                is_public=is_public,
            )
        )

    @on(Button.Pressed, "#cancel")
    def _on_cancel(self, event: Button.Pressed) -> None:
        """Handle cancel button."""
        event.stop()
        self.dismiss(None)

    @on(Input.Submitted, "#name-input")
    def _on_name_submitted(self, event: Input.Submitted) -> None:
        """Move to description when name is submitted."""
        del event  # unused
        self.query_one("#description-input", TextArea).focus()

    def action_cancel(self) -> None:
        """Handle escape key."""
        self.dismiss(None)
