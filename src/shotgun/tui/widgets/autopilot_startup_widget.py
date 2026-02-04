"""Autopilot startup widget for mode selection and stage preview.

This widget displays when the user invokes /autopilot, allowing them
to select the execution mode and preview stages before starting.
"""

from textual import events, on
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.css.query import NoMatches
from textual.widget import Widget
from textual.widgets import Button, RadioButton, RadioSet, Static

from shotgun.agents.autopilot.models import AutopilotMode, Stage
from shotgun.tui.screens.chat_screen.messages import (
    AutopilotCancel,
    AutopilotStart,
)


class AutopilotStartupWidget(Widget):
    """Widget for autopilot mode selection and stage preview.

    Displays:
    - Mode selection toggle (pause vs auto-continue)
    - List of stages parsed from tasks.md
    - Start and Cancel buttons

    Attributes:
        stages: List of stages parsed from tasks.md.
        selected_mode: Currently selected execution mode.
    """

    DEFAULT_CSS = """
        AutopilotStartupWidget {
            background: $secondary-background-darken-1;
            height: auto;
            max-height: 24;
            margin: 0 1;
            padding: 1;
            border: solid $primary;
        }

        AutopilotStartupWidget .startup-header {
            height: auto;
            text-align: center;
            margin-bottom: 1;
        }

        AutopilotStartupWidget .mode-section {
            height: auto;
            margin: 1 0;
        }

        AutopilotStartupWidget .mode-label {
            color: $text;
            margin-bottom: 1;
        }

        AutopilotStartupWidget RadioSet {
            height: auto;
            margin-left: 2;
        }

        AutopilotStartupWidget RadioButton {
            height: auto;
            margin-bottom: 0;
        }

        AutopilotStartupWidget .stages-section {
            height: auto;
            margin: 1 0;
        }

        AutopilotStartupWidget .stages-label {
            color: $text;
            margin-bottom: 1;
        }

        AutopilotStartupWidget .stages-scroll {
            height: auto;
            max-height: 8;
            margin-left: 2;
        }

        AutopilotStartupWidget .stage-item {
            color: $text;
        }

        AutopilotStartupWidget .stage-item-complete {
            color: $success;
        }

        AutopilotStartupWidget .startup-buttons {
            height: auto;
            width: 100%;
            margin-top: 1;
            align: center middle;
        }

        AutopilotStartupWidget Button {
            margin: 0 1;
            min-width: 12;
        }

        AutopilotStartupWidget #btn-start {
            background: $success;
        }

        AutopilotStartupWidget #btn-cancel {
            background: $error;
        }

        AutopilotStartupWidget .error-message {
            color: $error;
            margin: 1 0;
        }
    """

    def __init__(self, stages: list[Stage], error_message: str | None = None) -> None:
        """Initialize the startup widget.

        Args:
            stages: List of stages parsed from tasks.md.
            error_message: Optional error message to display.
        """
        super().__init__()
        self.stages = stages
        self.error_message = error_message
        self.selected_mode = AutopilotMode.PAUSE_BETWEEN

    def compose(self) -> ComposeResult:
        """Compose the startup widget layout."""
        # Header
        yield Static(
            "[bold]Autopilot - Stage Executor[/]",
            classes="startup-header",
        )

        # Error message if any
        if self.error_message:
            yield Static(
                f"[bold red]Error:[/] {self.error_message}",
                classes="error-message",
            )
            with Horizontal(classes="startup-buttons"):
                yield Button("Close", id="btn-cancel")
            return

        # Mode selection section
        yield Static("[dim]Execution Mode:[/]", classes="mode-label")
        with RadioSet(id="mode-select"):
            yield RadioButton(
                "Pause after each stage (review PRs)",
                id="mode-pause",
                value=True,
            )
            yield RadioButton(
                "Auto-continue (stacked PRs)",
                id="mode-auto",
            )

        # Stages preview section
        total_tasks = sum(s.task_count for s in self.stages)
        completed_tasks = sum(s.completed_count for s in self.stages)

        yield Static(
            f"[dim]Stages found in .shotgun/tasks.md: ({completed_tasks}/{total_tasks} tasks done)[/]",
            classes="stages-label",
        )

        with VerticalScroll(classes="stages-scroll"):
            for stage in self.stages:
                status_icon = ""
                css_class = "stage-item"

                if stage.is_complete:
                    status_icon = "[green]✓[/] "
                    css_class = "stage-item-complete"
                elif stage.completed_count > 0:
                    status_icon = "[yellow]◐[/] "

                yield Static(
                    f"{status_icon}{stage.number}. {stage.name} "
                    f"[dim]({stage.completed_count}/{stage.task_count} tasks)[/]",
                    classes=css_class,
                )

        # Action buttons
        with Horizontal(classes="startup-buttons"):
            yield Button("Start", id="btn-start")
            yield Button("Cancel", id="btn-cancel")

    def on_mount(self) -> None:
        """Auto-focus the Start button on mount."""
        try:
            start_btn = self.query_one("#btn-start", Button)
            start_btn.focus()
        except NoMatches:
            try:
                cancel_btn = self.query_one("#btn-cancel", Button)
                cancel_btn.focus()
            except NoMatches:
                pass

    @on(RadioSet.Changed, "#mode-select")
    def handle_mode_change(self, event: RadioSet.Changed) -> None:
        """Handle mode selection change."""
        if event.pressed.id == "mode-pause":
            self.selected_mode = AutopilotMode.PAUSE_BETWEEN
        elif event.pressed.id == "mode-auto":
            self.selected_mode = AutopilotMode.AUTO_CONTINUE

    @on(Button.Pressed, "#btn-start")
    def handle_start(self) -> None:
        """Handle Start button press."""
        self.post_message(AutopilotStart(self.selected_mode, self.stages))

    @on(Button.Pressed, "#btn-cancel")
    def handle_cancel(self) -> None:
        """Handle Cancel button press."""
        self.post_message(AutopilotCancel())

    def on_key(self, event: events.Key) -> None:
        """Handle keyboard shortcuts.

        Shortcuts:
            Enter: Start autopilot
            Escape: Cancel
            P: Select pause mode
            A: Select auto-continue mode
        """
        if event.key == "enter":
            if not self.error_message:
                self.post_message(AutopilotStart(self.selected_mode, self.stages))
            else:
                self.post_message(AutopilotCancel())
            event.stop()
        elif event.key == "escape":
            self.post_message(AutopilotCancel())
            event.stop()
        elif event.key in ("p", "P"):
            self.selected_mode = AutopilotMode.PAUSE_BETWEEN
            try:
                radio = self.query_one("#mode-pause", RadioButton)
                radio.value = True
            except NoMatches:
                pass
            event.stop()
        elif event.key in ("a", "A"):
            self.selected_mode = AutopilotMode.AUTO_CONTINUE
            try:
                radio = self.query_one("#mode-auto", RadioButton)
                radio.value = True
            except NoMatches:
                pass
            event.stop()
