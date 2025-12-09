"""Plan approval widget for Planning mode.

This widget displays when a multi-step plan is created in Planning mode,
allowing the user to approve or reject the plan before execution begins.
"""

from textual import events, on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.css.query import NoMatches
from textual.widget import Widget
from textual.widgets import Button, Static

from shotgun.agents.router.models import ExecutionPlan
from shotgun.tui.screens.chat_screen.messages import (
    PlanApproved,
    PlanRejected,
)


class PlanApprovalWidget(Widget):
    """Widget for plan approval in Planning mode.

    Displays the execution plan summary with goal and steps,
    and provides action buttons for the user to approve or reject.

    Attributes:
        plan: The execution plan that needs user approval.
    """

    DEFAULT_CSS = """
        PlanApprovalWidget {
            background: $secondary-background-darken-1;
            height: auto;
            margin: 1;
            padding: 1;
        }

        PlanApprovalWidget .approval-header {
            margin-bottom: 1;
        }

        PlanApprovalWidget .plan-goal {
            color: $text;
            margin-bottom: 1;
        }

        PlanApprovalWidget .plan-steps-label {
            color: $text-muted;
        }

        PlanApprovalWidget .step-item {
            color: $text;
            margin-left: 2;
        }

        PlanApprovalWidget .approval-buttons {
            height: auto;
            width: 100%;
            margin-top: 1;
        }

        PlanApprovalWidget Button {
            margin-right: 1;
            min-width: 18;
        }

        PlanApprovalWidget #btn-approve {
            background: $success;
        }

        PlanApprovalWidget #btn-reject {
            background: $error;
        }
    """

    def __init__(self, plan: ExecutionPlan) -> None:
        """Initialize the approval widget.

        Args:
            plan: The execution plan that needs user approval.
        """
        super().__init__()
        self.plan = plan

    def compose(self) -> ComposeResult:
        """Compose the approval widget layout."""
        # Header with step count
        yield Static(
            f"[bold]📋 Plan created with {len(self.plan.steps)} steps[/]",
            classes="approval-header",
        )

        # Goal
        yield Static(
            f"[dim]Goal:[/] {self.plan.goal}",
            classes="plan-goal",
        )

        # Steps list
        yield Static("[dim]Steps:[/]", classes="plan-steps-label")
        for i, step in enumerate(self.plan.steps, 1):
            yield Static(
                f"{i}. {step.title}",
                classes="step-item",
            )

        # Action buttons
        with Horizontal(classes="approval-buttons"):
            yield Button("✓ Go Ahead", id="btn-approve")
            yield Button("✗ No, Let Me Clarify", id="btn-reject")

    def on_mount(self) -> None:
        """Auto-focus the Go Ahead button on mount."""
        try:
            approve_btn = self.query_one("#btn-approve", Button)
            approve_btn.focus()
        except NoMatches:
            pass

    @on(Button.Pressed, "#btn-approve")
    def handle_approve(self) -> None:
        """Handle Go Ahead button press."""
        self.post_message(PlanApproved())

    @on(Button.Pressed, "#btn-reject")
    def handle_reject(self) -> None:
        """Handle No, Let Me Clarify button press."""
        self.post_message(PlanRejected())

    def on_key(self, event: events.Key) -> None:
        """Handle keyboard shortcuts for approval actions.

        Shortcuts:
            Enter/Y: Approve plan (Go Ahead)
            Escape/N: Reject plan (No, Let Me Clarify)
        """
        if event.key in ("enter", "y", "Y"):
            self.post_message(PlanApproved())
            event.stop()
        elif event.key in ("escape", "n", "N"):
            self.post_message(PlanRejected())
            event.stop()
