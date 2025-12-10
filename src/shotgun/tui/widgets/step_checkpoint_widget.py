"""Step checkpoint widget for Planning mode.

This widget displays after each step completes in Planning mode,
allowing the user to continue, modify the plan, or stop execution.
"""

from textual import events, on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.css.query import NoMatches
from textual.widget import Widget
from textual.widgets import Button, Static

from shotgun.agents.router.models import ExecutionStep
from shotgun.tui.screens.chat_screen.messages import (
    CheckpointContinue,
    CheckpointModify,
    CheckpointStop,
)


class StepCheckpointWidget(Widget):
    """Widget for step completion checkpoints in Planning mode.

    Displays information about the completed step and provides
    action buttons for the user to choose how to proceed.

    Attributes:
        step: The step that was just completed.
        next_step: The next step to execute, or None if this was the last step.
    """

    DEFAULT_CSS = """
        StepCheckpointWidget {
            background: $secondary-background-darken-1;
            height: auto;
            margin: 1;
            padding: 1;
        }

        StepCheckpointWidget .checkpoint-header {
            margin-bottom: 1;
        }

        StepCheckpointWidget .next-step-preview {
            color: $text-muted;
        }

        StepCheckpointWidget .checkpoint-buttons {
            height: auto;
            width: 100%;
            margin-top: 1;
        }

        StepCheckpointWidget Button {
            margin-right: 1;
            min-width: 14;
        }

        StepCheckpointWidget #btn-continue {
            background: $success;
        }

        StepCheckpointWidget #btn-modify {
            background: $warning;
        }

        StepCheckpointWidget #btn-stop {
            background: $error;
        }

        StepCheckpointWidget #btn-done {
            background: $success;
        }
    """

    def __init__(self, step: ExecutionStep, next_step: ExecutionStep | None) -> None:
        """Initialize the checkpoint widget.

        Args:
            step: The step that was just completed.
            next_step: The next step to execute, or None if last step.
        """
        super().__init__()
        self.step = step
        self.next_step = next_step

    def compose(self) -> ComposeResult:
        """Compose the checkpoint widget layout."""
        if self.next_step:
            # Mid-plan checkpoint: show step completed with next step preview
            yield Static(
                f"[bold green]✅ Step completed:[/] {self.step.title}",
                classes="checkpoint-header",
            )
            yield Static(
                f"[dim]Next:[/] {self.next_step.title}",
                classes="next-step-preview",
            )
            with Horizontal(classes="checkpoint-buttons"):
                yield Button("Continue", id="btn-continue")
                yield Button("Modify plan", id="btn-modify")
                yield Button("Stop here", id="btn-stop")
        else:
            # Plan completed: show completion message with Done button only
            yield Static(
                "[bold green]✅ Plan completed![/]",
                classes="checkpoint-header",
            )
            yield Static(
                f"[dim]Final step:[/] {self.step.title}",
                classes="next-step-preview",
            )
            with Horizontal(classes="checkpoint-buttons"):
                yield Button("Done", id="btn-done")

    def on_mount(self) -> None:
        """Auto-focus the appropriate button on mount."""
        # Auto-focus Continue button if available, otherwise Done, then Modify
        try:
            continue_btn = self.query_one("#btn-continue", Button)
            continue_btn.focus()
        except NoMatches:
            try:
                done_btn = self.query_one("#btn-done", Button)
                done_btn.focus()
            except NoMatches:
                try:
                    modify_btn = self.query_one("#btn-modify", Button)
                    modify_btn.focus()
                except NoMatches:
                    pass  # No buttons to focus

    @on(Button.Pressed, "#btn-continue")
    def handle_continue(self) -> None:
        """Handle Continue button press."""
        self.post_message(CheckpointContinue())

    @on(Button.Pressed, "#btn-modify")
    def handle_modify(self) -> None:
        """Handle Modify plan button press."""
        self.post_message(CheckpointModify())

    @on(Button.Pressed, "#btn-stop")
    def handle_stop(self) -> None:
        """Handle Stop here button press."""
        self.post_message(CheckpointStop())

    @on(Button.Pressed, "#btn-done")
    def handle_done(self) -> None:
        """Handle Done button press (plan completed)."""
        self.post_message(CheckpointStop())

    def on_key(self, event: events.Key) -> None:
        """Handle keyboard shortcuts for checkpoint actions.

        Shortcuts:
            Enter/C: Continue to next step (if available), or Done (if plan complete)
            M: Modify the plan (only if not complete)
            S/Escape: Stop execution (only if not complete)
        """
        if event.key in ("enter", "c", "C"):
            if self.next_step:
                self.post_message(CheckpointContinue())
            else:
                # Plan complete - Enter dismisses
                self.post_message(CheckpointStop())
            event.stop()
        elif event.key in ("m", "M"):
            if self.next_step:
                self.post_message(CheckpointModify())
                event.stop()
        elif event.key in ("s", "S", "escape"):
            if self.next_step:
                self.post_message(CheckpointStop())
                event.stop()
            else:
                # Plan complete - Escape also dismisses
                self.post_message(CheckpointStop())
                event.stop()
