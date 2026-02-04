"""Stage approval widget for Autopilot workflow.

This widget displays after a stage completes its workflow, showing the PR
and allowing the user to Accept (continue) or Reject (request changes).
"""

from textual import events, on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.widget import Widget
from textual.widgets import Button, Static

from shotgun.agents.autopilot.models import Stage
from shotgun.tui.screens.chat_screen.messages import (
    AutopilotAccept,
    AutopilotReject,
    AutopilotStop,
)


class StageApprovalWidget(Widget):
    """Widget for stage approval in Autopilot workflow.

    Shows the completed stage with PR link and Accept/Reject buttons.
    The input box is disabled while this widget is shown.

    Attributes:
        completed_stage: The stage that completed the workflow.
        next_stage: The next stage to execute, or None if all complete.
    """

    DEFAULT_CSS = """
        StageApprovalWidget {
            background: $surface;
            height: auto;
            margin: 0 1;
            padding: 1 2;
            border: solid $success;
        }

        StageApprovalWidget .approval-header {
            text-align: center;
            margin-bottom: 1;
        }

        StageApprovalWidget .stage-info {
            margin-bottom: 1;
        }

        StageApprovalWidget .pr-link {
            color: $primary;
            text-style: bold;
            margin: 1 0;
        }

        StageApprovalWidget .next-preview {
            color: $text-muted;
            margin-top: 1;
        }

        StageApprovalWidget .button-row {
            height: auto;
            width: 100%;
            align: center middle;
            margin-top: 1;
        }

        StageApprovalWidget Button {
            margin: 0 2;
            min-width: 16;
        }

        StageApprovalWidget #btn-accept {
            background: $success;
        }

        StageApprovalWidget #btn-reject {
            background: $warning;
        }

        StageApprovalWidget #btn-stop {
            background: $error;
        }

        StageApprovalWidget .all-done {
            color: $success;
            text-style: bold;
            text-align: center;
        }
    """

    def __init__(self, completed_stage: Stage, next_stage: Stage | None) -> None:
        """Initialize the approval widget.

        Args:
            completed_stage: The stage that completed.
            next_stage: The next stage, or None if all done.
        """
        super().__init__()
        self.completed_stage = completed_stage
        self.next_stage = next_stage

    def compose(self) -> ComposeResult:
        """Compose the approval widget layout."""
        with Vertical():
            # Header
            yield Static(
                f"[bold]Stage {self.completed_stage.number} Complete[/bold]",
                classes="approval-header",
            )

            # Stage info
            yield Static(
                f"{self.completed_stage.name} - "
                f"{self.completed_stage.completed_count}/{self.completed_stage.task_count} tasks done",
                classes="stage-info",
            )

            # PR Link (prominent)
            if self.completed_stage.pr_url:
                yield Static(
                    f"PR: {self.completed_stage.pr_url}",
                    classes="pr-link",
                )
            else:
                yield Static(
                    "[dim]No PR created[/dim]",
                    classes="pr-link",
                )

            # Next stage preview
            if self.next_stage:
                yield Static(
                    f"[dim]Next: Stage {self.next_stage.number}: {self.next_stage.name}[/dim]",
                    classes="next-preview",
                )
            else:
                yield Static(
                    "[green]This is the final stage![/green]",
                    classes="all-done",
                )

            # Buttons
            with Horizontal(classes="button-row"):
                if self.next_stage:
                    yield Button("Accept", id="btn-accept", variant="success")
                    yield Button("Reject", id="btn-reject", variant="warning")
                else:
                    # Final stage - just Done button
                    yield Button("Done", id="btn-accept", variant="success")

    def on_mount(self) -> None:
        """Focus the Accept button on mount."""
        try:
            btn = self.query_one("#btn-accept", Button)
            btn.focus()
        except NoMatches:
            pass

    @on(Button.Pressed, "#btn-accept")
    def handle_accept(self) -> None:
        """Handle Accept button - approve and continue."""
        self.post_message(AutopilotAccept())

    @on(Button.Pressed, "#btn-reject")
    def handle_reject(self) -> None:
        """Handle Reject button - request changes."""
        # Post reject message - the TUI will show prompt input for feedback
        self.post_message(AutopilotReject())

    @on(Button.Pressed, "#btn-stop")
    def handle_stop(self) -> None:
        """Handle Stop button."""
        self.post_message(AutopilotStop())

    def on_key(self, event: events.Key) -> None:
        """Handle keyboard shortcuts.

        Shortcuts:
            A/Enter: Accept
            R: Reject
            Escape: Stop
        """
        if event.key in ("a", "A", "enter"):
            self.post_message(AutopilotAccept())
            event.stop()
        elif event.key in ("r", "R"):
            if self.next_stage:  # Only allow reject if not final stage
                self.post_message(AutopilotReject())
            event.stop()
        elif event.key == "escape":
            self.post_message(AutopilotStop())
            event.stop()
