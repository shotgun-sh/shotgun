"""Stage approval widget for Autopilot pause mode.

This widget displays between stages in pause mode, allowing the user
to review the completed stage and choose whether to continue.
"""

from textual import events, on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.css.query import NoMatches
from textual.widget import Widget
from textual.widgets import Button, Static

from shotgun.agents.autopilot.models import Stage
from shotgun.tui.screens.chat_screen.messages import (
    AutopilotContinue,
    AutopilotStop,
)


class StageApprovalWidget(Widget):
    """Widget for stage completion approval in Autopilot pause mode.

    Displays information about the completed stage and provides
    action buttons for the user to continue or stop.

    Attributes:
        completed_stage: The stage that was just completed.
        next_stage: The next stage to execute, or None if all complete.
    """

    DEFAULT_CSS = """
        StageApprovalWidget {
            background: $secondary-background-darken-1;
            height: auto;
            margin: 1;
            padding: 1;
            border: solid $success;
        }

        StageApprovalWidget .stage-header {
            margin-bottom: 1;
        }

        StageApprovalWidget .completed-info {
            color: $success;
            margin-bottom: 1;
        }

        StageApprovalWidget .next-stage-preview {
            color: $text-muted;
        }

        StageApprovalWidget .pr-info {
            color: $primary;
            margin: 1 0;
        }

        StageApprovalWidget .stage-buttons {
            height: auto;
            width: 100%;
            margin-top: 1;
        }

        StageApprovalWidget Button {
            margin-right: 1;
            min-width: 14;
        }

        StageApprovalWidget #btn-continue {
            background: $success;
        }

        StageApprovalWidget #btn-stop {
            background: $error;
        }

        StageApprovalWidget #btn-done {
            background: $success;
        }
    """

    def __init__(self, completed_stage: Stage, next_stage: Stage | None) -> None:
        """Initialize the approval widget.

        Args:
            completed_stage: The stage that was just completed.
            next_stage: The next stage to execute, or None if last stage.
        """
        super().__init__()
        self.completed_stage = completed_stage
        self.next_stage = next_stage

    def compose(self) -> ComposeResult:
        """Compose the approval widget layout."""
        if self.next_stage:
            # Mid-execution: show completed stage with next stage preview
            yield Static(
                f"[bold green]Stage {self.completed_stage.number} completed[/]",
                classes="stage-header",
            )
            yield Static(
                f"[green]{self.completed_stage.name}[/] - "
                f"{self.completed_stage.completed_count}/{self.completed_stage.task_count} tasks",
                classes="completed-info",
            )

            # Show PR URL if available
            if self.completed_stage.pr_url:
                yield Static(
                    f"[dim]PR:[/] {self.completed_stage.pr_url}",
                    classes="pr-info",
                )

            yield Static(
                f"[dim]Next:[/] Stage {self.next_stage.number}: {self.next_stage.name} "
                f"({self.next_stage.task_count} tasks)",
                classes="next-stage-preview",
            )

            with Horizontal(classes="stage-buttons"):
                yield Button("Continue", id="btn-continue")
                yield Button("Stop here", id="btn-stop")
        else:
            # All stages complete
            yield Static(
                "[bold green]All stages completed![/]",
                classes="stage-header",
            )
            yield Static(
                f"[green]Final stage:[/] {self.completed_stage.name}",
                classes="completed-info",
            )

            # Show PR URL if available
            if self.completed_stage.pr_url:
                yield Static(
                    f"[dim]PR:[/] {self.completed_stage.pr_url}",
                    classes="pr-info",
                )

            with Horizontal(classes="stage-buttons"):
                yield Button("Done", id="btn-done")

    def on_mount(self) -> None:
        """Auto-focus the appropriate button on mount."""
        try:
            continue_btn = self.query_one("#btn-continue", Button)
            continue_btn.focus()
        except NoMatches:
            try:
                done_btn = self.query_one("#btn-done", Button)
                done_btn.focus()
            except NoMatches:
                pass

    @on(Button.Pressed, "#btn-continue")
    def handle_continue(self) -> None:
        """Handle Continue button press."""
        self.post_message(AutopilotContinue())

    @on(Button.Pressed, "#btn-stop")
    def handle_stop(self) -> None:
        """Handle Stop button press."""
        self.post_message(AutopilotStop())

    @on(Button.Pressed, "#btn-done")
    def handle_done(self) -> None:
        """Handle Done button press (all stages complete)."""
        self.post_message(AutopilotStop())

    def on_key(self, event: events.Key) -> None:
        """Handle keyboard shortcuts.

        Shortcuts:
            Enter/C: Continue to next stage (or dismiss if complete)
            Escape/S: Stop execution
        """
        if event.key in ("enter", "c", "C"):
            if self.next_stage:
                self.post_message(AutopilotContinue())
            else:
                # All complete - dismiss
                self.post_message(AutopilotStop())
            event.stop()
        elif event.key in ("escape", "s", "S"):
            self.post_message(AutopilotStop())
            event.stop()
