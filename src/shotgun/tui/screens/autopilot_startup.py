"""Full-screen autopilot startup modal for mode selection and stage preview.

This screen displays when the user invokes /autopilot, allowing them
to select the execution mode and preview stages before starting.
"""

from pydantic import BaseModel, Field
from textual import events, on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.css.query import NoMatches
from textual.screen import ModalScreen
from textual.widgets import Button, RadioButton, RadioSet, Static

from shotgun.agents.autopilot.models import AutopilotMode, Stage


class AutopilotStartResult(BaseModel):
    """Result from the autopilot startup screen."""

    started: bool = Field(description="Whether the user started the autopilot")
    mode: AutopilotMode | None = Field(
        default=None, description="Selected execution mode"
    )
    stages: list[Stage] | None = Field(
        default=None, description="Stages to execute"
    )


class AutopilotStartupScreen(ModalScreen[AutopilotStartResult]):
    """Full-screen modal for autopilot mode selection and stage preview.

    Displays:
    - Mode selection toggle (pause vs auto-continue)
    - List of stages parsed from tasks.md
    - Start and Cancel buttons

    Returns:
        AutopilotStartResult with started=True and mode/stages if user clicks Start,
        or started=False if user cancels.
    """

    DEFAULT_CSS = """
        AutopilotStartupScreen {
            align: center middle;
            background: $background 90%;
        }

        AutopilotStartupScreen > #autopilot-container {
            width: 100%;
            height: 100%;
            padding: 1;
            layout: vertical;
            background: $surface;
        }

        AutopilotStartupScreen .startup-header {
            height: auto;
            text-align: center;
            text-style: bold;
            color: $primary;
        }

        AutopilotStartupScreen .experimental-badge {
            text-align: center;
            color: $warning;
            margin-bottom: 1;
        }

        AutopilotStartupScreen .mode-section {
            height: auto;
            margin-bottom: 1;
        }

        AutopilotStartupScreen .mode-label {
            color: $text;
        }

        AutopilotStartupScreen RadioSet {
            height: auto;
            margin-left: 1;
        }

        AutopilotStartupScreen RadioButton {
            height: auto;
            margin-bottom: 0;
        }

        AutopilotStartupScreen .stages-label {
            color: $text;
            height: auto;
        }

        AutopilotStartupScreen .stages-scroll {
            height: 1fr;
            min-height: 5;
            margin-left: 1;
            scrollbar-gutter: stable;
        }

        AutopilotStartupScreen .stage-item {
            color: $text;
            height: auto;
        }

        AutopilotStartupScreen .stage-item-complete {
            color: $success;
            height: auto;
        }

        AutopilotStartupScreen .startup-buttons {
            height: auto;
            width: 100%;
            margin-top: 1;
            align: center middle;
        }

        AutopilotStartupScreen Button {
            margin: 0 1;
            min-width: 12;
        }

        AutopilotStartupScreen #btn-start {
            background: $success;
        }

        AutopilotStartupScreen #btn-cancel {
            background: $surface-lighten-2;
        }

        AutopilotStartupScreen .error-message {
            color: $error;
            padding: 1;
            text-align: center;
        }

        AutopilotStartupScreen .warning-message {
            color: $warning;
            margin-bottom: 1;
        }

        AutopilotStartupScreen .shortcut-hint {
            text-align: center;
            color: $text-muted;
            height: auto;
        }
    """

    def __init__(
        self,
        stages: list[Stage],
        error_message: str | None = None,
        *,
        is_warning: bool = False,
    ) -> None:
        """Initialize the startup screen.

        Args:
            stages: List of stages parsed from tasks.md.
            error_message: Optional error/warning message to display.
            is_warning: If True, treat as warning (can still start). If False, treat as error (blocks start).
        """
        super().__init__()
        self.stages = stages
        self.error_message = error_message
        self.is_warning = is_warning and len(stages) > 0  # Warnings only make sense if we have stages
        self.selected_mode = AutopilotMode.PAUSE_BETWEEN

    def compose(self) -> ComposeResult:
        """Compose the startup screen layout."""
        with Container(id="autopilot-container"):
            # Header
            yield Static(
                "Autopilot - Stage Executor",
                classes="startup-header",
            )
            yield Static(
                "[dim italic](experimental)[/]",
                classes="experimental-badge",
            )

            # Error message if any (blocking error - no stages)
            if self.error_message and not self.is_warning:
                yield Static(
                    f"[bold red]Error:[/] {self.error_message}",
                    classes="error-message",
                )
                with Horizontal(classes="startup-buttons"):
                    yield Button("Close", id="btn-cancel")
                return

            # Warning message (non-blocking - can still start)
            if self.error_message and self.is_warning:
                yield Static(
                    f"[yellow]{self.error_message}[/]",
                    classes="warning-message",
                )

            # Mode selection
            with Container(classes="mode-section"):
                yield Static("Mode:", classes="mode-label")
                with RadioSet(id="mode-select"):
                    yield RadioButton(
                        "Pause for human review after each stage",
                        id="mode-pause",
                        value=True,
                    )
                    yield RadioButton(
                        "Auto-continue with self-review (stacked PRs)",
                        id="mode-auto",
                    )
                    yield RadioButton(
                        "Cowboy (self-review, no human review, no PRs)",
                        id="mode-cowboy",
                    )

            # Stages preview section
            total_tasks = sum(s.task_count for s in self.stages)
            completed_tasks = sum(s.completed_count for s in self.stages)

            yield Static(
                f"Stages: [bold]{len(self.stages)}[/] ({completed_tasks}/{total_tasks} tasks done)",
                classes="stages-label",
            )

            with VerticalScroll(classes="stages-scroll"):
                for stage in self.stages:
                    status_icon = "  "
                    css_class = "stage-item"

                    if stage.is_complete:
                        status_icon = "[green]✓[/] "
                        css_class = "stage-item-complete"
                    elif stage.completed_count > 0:
                        status_icon = "[yellow]◐[/] "

                    yield Static(
                        f"{status_icon}{stage.number}. {stage.name} "
                        f"[dim]({stage.completed_count}/{stage.task_count})[/]",
                        classes=css_class,
                    )

            # Action buttons
            with Horizontal(classes="startup-buttons"):
                yield Button("Start", id="btn-start", variant="success")
                yield Button("Cancel", id="btn-cancel")

            # Shortcut hints
            yield Static(
                "[dim][bold]Enter[/]=start [bold]Esc[/]=cancel[/]",
                classes="shortcut-hint",
            )

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
        elif event.pressed.id == "mode-cowboy":
            self.selected_mode = AutopilotMode.COWBOY

    @on(Button.Pressed, "#btn-start")
    def handle_start(self, event: Button.Pressed) -> None:
        """Handle Start button press."""
        event.stop()
        self.dismiss(
            AutopilotStartResult(
                started=True,
                mode=self.selected_mode,
                stages=self.stages,
            )
        )

    @on(Button.Pressed, "#btn-cancel")
    def handle_cancel(self, event: Button.Pressed) -> None:
        """Handle Cancel button press."""
        event.stop()
        self.dismiss(AutopilotStartResult(started=False))

    def on_key(self, event: events.Key) -> None:
        """Handle keyboard shortcuts.

        Shortcuts:
            Enter: Start autopilot
            Escape: Cancel
            P: Select pause mode
            A: Select auto-continue mode
            C: Select cowboy mode
        """
        if event.key == "enter":
            if not self.error_message or self.is_warning:
                self.dismiss(
                    AutopilotStartResult(
                        started=True,
                        mode=self.selected_mode,
                        stages=self.stages,
                    )
                )
            else:
                self.dismiss(AutopilotStartResult(started=False))
            event.stop()
        elif event.key == "escape":
            self.dismiss(AutopilotStartResult(started=False))
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
        elif event.key in ("c", "C"):
            self.selected_mode = AutopilotMode.COWBOY
            try:
                radio = self.query_one("#mode-cowboy", RadioButton)
                radio.value = True
            except NoMatches:
                pass
            event.stop()
