"""Cascade confirmation widget for Planning mode.

This widget displays after a file with dependents is updated,
allowing the user to choose which dependent files should also be updated.
"""

from textual import events, on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.css.query import NoMatches
from textual.widget import Widget
from textual.widgets import Button, Static

from shotgun.agents.router.models import CascadeScope
from shotgun.tui.screens.chat_screen.messages import (
    CascadeConfirmed,
    CascadeDeclined,
)

# File descriptions for cascade confirmation UI
FILE_DESCRIPTIONS: dict[str, str] = {
    "specification.md": "may need updated requirements",
    "plan.md": "may need new implementation steps",
    "tasks.md": "may need new tasks",
}


class CascadeConfirmationWidget(Widget):
    """Widget for cascade confirmation in Planning mode.

    Displays information about the updated file and its dependents,
    providing action buttons for the user to choose the cascade scope.

    Attributes:
        updated_file: The file that was just updated.
        dependent_files: List of files that depend on the updated file.
    """

    DEFAULT_CSS = """
        CascadeConfirmationWidget {
            background: $secondary-background-darken-1;
            height: auto;
            margin: 1;
            padding: 1;
        }

        CascadeConfirmationWidget .cascade-header {
            margin-bottom: 1;
        }

        CascadeConfirmationWidget .cascade-info {
            color: $text-muted;
            margin-bottom: 1;
        }

        CascadeConfirmationWidget .dependent-file {
            color: $text;
            margin-left: 2;
        }

        CascadeConfirmationWidget .cascade-question {
            margin-top: 1;
            margin-bottom: 1;
        }

        CascadeConfirmationWidget .cascade-buttons {
            height: auto;
            width: 100%;
            margin-top: 1;
        }

        CascadeConfirmationWidget Button {
            margin-right: 1;
            min-width: 14;
        }

        CascadeConfirmationWidget #btn-update-all {
            background: $success;
        }

        CascadeConfirmationWidget #btn-plan-only {
            background: $primary;
        }

        CascadeConfirmationWidget #btn-tasks-only {
            background: $primary;
        }

        CascadeConfirmationWidget #btn-decline {
            background: $error;
        }
    """

    def __init__(self, updated_file: str, dependent_files: list[str]) -> None:
        """Initialize the cascade confirmation widget.

        Args:
            updated_file: The file that was just updated.
            dependent_files: List of files that depend on the updated file.
        """
        super().__init__()
        self.updated_file = updated_file
        self.dependent_files = dependent_files

    def compose(self) -> ComposeResult:
        """Compose the cascade confirmation widget layout."""
        # Header showing updated file
        file_name = self.updated_file.split("/")[-1]
        yield Static(
            f"[bold green]✅ Updated {file_name}[/]",
            classes="cascade-header",
        )

        # Show dependent files
        if self.dependent_files:
            yield Static(
                "[dim]This affects dependent files:[/]",
                classes="cascade-info",
            )
            for dep_file in self.dependent_files:
                dep_name = dep_file.split("/")[-1]
                description = FILE_DESCRIPTIONS.get(dep_name, "may need updates")
                yield Static(
                    f"• {dep_name} - {description}",
                    classes="dependent-file",
                )

            yield Static(
                "Should I update these to match?",
                classes="cascade-question",
            )

        # Action buttons based on dependent files
        with Horizontal(classes="cascade-buttons"):
            if self.dependent_files:
                # Update all button
                yield Button("Update all", id="btn-update-all")

                # Selective buttons if multiple dependents
                if "plan.md" in self.dependent_files and len(self.dependent_files) > 1:
                    yield Button("Just plan.md", id="btn-plan-only")
                if "tasks.md" in self.dependent_files and len(self.dependent_files) > 1:
                    yield Button("Just tasks.md", id="btn-tasks-only")

            # Always show decline button
            yield Button("No, I'll handle it", id="btn-decline")

    def on_mount(self) -> None:
        """Auto-focus the Update all button on mount."""
        try:
            update_btn = self.query_one("#btn-update-all", Button)
            update_btn.focus()
        except NoMatches:
            try:
                decline_btn = self.query_one("#btn-decline", Button)
                decline_btn.focus()
            except NoMatches:
                pass  # No buttons to focus

    @on(Button.Pressed, "#btn-update-all")
    def handle_update_all(self) -> None:
        """Handle Update all button press."""
        self.post_message(CascadeConfirmed(CascadeScope.ALL))

    @on(Button.Pressed, "#btn-plan-only")
    def handle_plan_only(self) -> None:
        """Handle Just plan.md button press."""
        self.post_message(CascadeConfirmed(CascadeScope.PLAN_ONLY))

    @on(Button.Pressed, "#btn-tasks-only")
    def handle_tasks_only(self) -> None:
        """Handle Just tasks.md button press."""
        self.post_message(CascadeConfirmed(CascadeScope.TASKS_ONLY))

    @on(Button.Pressed, "#btn-decline")
    def handle_decline(self) -> None:
        """Handle No button press."""
        self.post_message(CascadeDeclined())

    def on_key(self, event: events.Key) -> None:
        """Handle keyboard shortcuts for cascade actions.

        Shortcuts:
            Enter/A: Update all dependent files
            P: Just update plan.md (if available)
            T: Just update tasks.md (if available)
            N/Escape: No, I'll handle it
        """
        if event.key in ("enter", "a", "A"):
            if self.dependent_files:
                self.post_message(CascadeConfirmed(CascadeScope.ALL))
                event.stop()
        elif event.key in ("p", "P"):
            if "plan.md" in self.dependent_files and len(self.dependent_files) > 1:
                self.post_message(CascadeConfirmed(CascadeScope.PLAN_ONLY))
                event.stop()
        elif event.key in ("t", "T"):
            if "tasks.md" in self.dependent_files and len(self.dependent_files) > 1:
                self.post_message(CascadeConfirmed(CascadeScope.TASKS_ONLY))
                event.stop()
        elif event.key in ("n", "N", "escape"):
            self.post_message(CascadeDeclined())
            event.stop()
