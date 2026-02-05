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
            margin: 1 2;
            padding: 1 2;
            border: tall $success;
        }

        StageApprovalWidget .approval-content {
            width: 100%;
            height: auto;
        }

        StageApprovalWidget .approval-header {
            text-align: center;
            text-style: bold;
            color: $success;
            padding-bottom: 1;
        }

        StageApprovalWidget .stage-info {
            text-align: center;
            color: $text;
        }

        StageApprovalWidget .pr-link {
            text-align: center;
            color: $text-muted;
            padding: 0;
        }

        StageApprovalWidget .next-preview {
            text-align: center;
            color: $text-muted;
            padding-top: 1;
        }

        StageApprovalWidget .button-row {
            height: auto;
            width: 100%;
            align: center middle;
            padding-top: 1;
        }

        StageApprovalWidget Button {
            margin: 0 1;
            min-width: 20;
        }

        StageApprovalWidget #btn-accept {
            background: $success;
        }

        StageApprovalWidget #btn-reject {
            background: $warning;
        }

        StageApprovalWidget #btn-stop {
            background: $error-darken-1;
        }

        StageApprovalWidget .all-done {
            color: $success;
            text-style: bold;
            text-align: center;
        }

        StageApprovalWidget .shortcut-hint {
            text-align: center;
            color: $text-muted;
            padding-top: 1;
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
        with Vertical(classes="approval-content"):
            # Header
            yield Static(
                f"✅ Stage {self.completed_stage.number} Complete",
                classes="approval-header",
            )

            # Stage info
            yield Static(
                f"{self.completed_stage.name} — "
                f"{self.completed_stage.completed_count}/{self.completed_stage.task_count} tasks done",
                classes="stage-info",
            )

            # PR Link
            if self.completed_stage.pr_url:
                yield Static(
                    f"[link={self.completed_stage.pr_url}]{self.completed_stage.pr_url}[/link]",
                    classes="pr-link",
                )
            else:
                yield Static(
                    "[dim]No PR created (local only)[/dim]",
                    classes="pr-link",
                )

            # Next stage preview
            if self.next_stage:
                yield Static(
                    f"Next: Stage {self.next_stage.number} — {self.next_stage.name}",
                    classes="next-preview",
                )
            else:
                yield Static(
                    "🎉 This is the final stage!",
                    classes="all-done",
                )

            # Buttons
            with Horizontal(classes="button-row"):
                if self.next_stage:
                    yield Button(
                        f"Continue to Stage {self.next_stage.number}",
                        id="btn-accept",
                        variant="success",
                    )
                    yield Button("Request Changes", id="btn-reject", variant="warning")
                    yield Button("Exit Autopilot", id="btn-stop", variant="error")
                else:
                    # Final stage - just Finish button
                    yield Button("Finish Autopilot", id="btn-accept", variant="success")
                    yield Button("Exit", id="btn-stop", variant="error")

            # Shortcut hints
            yield Static(
                "[dim]Press [bold]Enter[/] to continue, [bold]R[/] to request changes, [bold]Esc[/] to exit[/]",
                classes="shortcut-hint",
            )

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
            Enter: Accept/Continue
            R: Request changes (Reject)
            Escape: Stop/Exit autopilot
        """
        if event.key == "enter":
            self.post_message(AutopilotAccept())
            event.stop()
        elif event.key in ("r", "R"):
            if self.next_stage:  # Only allow reject if not final stage
                self.post_message(AutopilotReject())
            event.stop()
        elif event.key == "escape":
            self.post_message(AutopilotStop())
            event.stop()
