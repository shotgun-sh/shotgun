"""Plan panel widget for displaying the current execution plan.

This widget displays the current RouterDeps execution plan.
It auto-shows when a plan exists and can be closed with × button.
"""

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Button, Static

from shotgun.agents.router.models import ExecutionPlan
from shotgun.tui.screens.chat_screen.messages import PlanPanelClosed


class PlanPanelWidget(Widget):
    """Widget for displaying the current execution plan.

    Displays the plan goal and steps with status indicators.
    Provides a close button to dismiss the panel.

    Attributes:
        plan: The execution plan to display.
    """

    DEFAULT_CSS = """
        PlanPanelWidget {
            background: $secondary-background-darken-1;
            height: auto;
            max-height: 10;
            margin: 0 1;
            padding: 1;
            border: solid $primary-darken-2;
        }

        PlanPanelWidget .panel-header-row {
            height: auto;
            margin-bottom: 1;
        }

        PlanPanelWidget .panel-header {
            color: $text-accent;
        }

        PlanPanelWidget #btn-close {
            dock: right;
            min-width: 3;
            height: 1;
            background: transparent;
            border: none;
            color: $text-muted;
        }

        PlanPanelWidget #btn-close:hover {
            color: $error;
        }

        PlanPanelWidget .plan-goal {
            color: $text;
            margin-bottom: 1;
        }

        PlanPanelWidget .step-item {
            color: $text;
            margin-left: 2;
        }

        PlanPanelWidget .step-done {
            color: $text-muted;
            margin-left: 2;
        }

        PlanPanelWidget .step-current {
            color: $text-accent;
            margin-left: 2;
        }
    """

    def __init__(self, plan: ExecutionPlan) -> None:
        """Initialize the plan panel widget.

        Args:
            plan: The execution plan to display.
        """
        super().__init__()
        self._plan = plan

    @property
    def plan(self) -> ExecutionPlan:
        """Get the current plan."""
        return self._plan

    def update_plan(self, plan: ExecutionPlan) -> None:
        """Update the displayed plan and refresh the widget.

        Args:
            plan: The new plan to display.
        """
        self._plan = plan
        self.refresh(layout=True)

    def compose(self) -> ComposeResult:
        """Compose the plan panel layout."""
        # Header with close button
        with Horizontal(classes="panel-header-row"):
            yield Static("[bold]📋 Execution Plan[/]", classes="panel-header")
            yield Button("×", id="btn-close")

        # Goal
        yield Static(f"[dim]Goal:[/] {self._plan.goal}", classes="plan-goal")

        # Steps
        for i, step in enumerate(self._plan.steps):
            marker = "✅" if step.done else "⬜"
            current = (
                " ◀" if i == self._plan.current_step_index and not step.done else ""
            )
            css_class = (
                "step-done"
                if step.done
                else ("step-current" if current else "step-item")
            )
            yield Static(f"{i + 1}. {marker} {step.title}{current}", classes=css_class)

    @on(Button.Pressed, "#btn-close")
    def handle_close(self) -> None:
        """Handle close button press."""
        self.post_message(PlanPanelClosed())
