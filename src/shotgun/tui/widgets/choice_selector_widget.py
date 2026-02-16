"""Choice selector widget for agent response choices.

This widget replaces the PromptInput when an agent returns choices,
showing a numbered list of options. The user can select by pressing
Enter (default), clicking, or pressing the option number.
"""

from textual import events, on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.css.query import NoMatches
from textual.widget import Widget
from textual.widgets import Button

from shotgun.agents.models import ResponseChoice
from shotgun.tui.screens.chat_screen.messages import ChoiceSelected


class ChoiceSelectorWidget(Widget):
    """Widget for displaying agent response choices.

    Replaces the PromptInput in the footer when an agent returns
    choices. Shows numbered options with keyboard and click support.

    Attributes:
        choices: The list of choices to display.
    """

    DEFAULT_CSS = """
        ChoiceSelectorWidget {
            background: $secondary-background-darken-1;
            height: auto;
            padding: 1 2;
        }

        ChoiceSelectorWidget .choice-buttons {
            height: auto;
            width: 100%;
        }

        ChoiceSelectorWidget Button {
            margin: 0 1 0 0;
            min-width: 16;
            height: 3;
        }

        ChoiceSelectorWidget .choice-default {
            background: $success;
        }

        ChoiceSelectorWidget .choice-secondary {
            background: $primary-darken-1;
        }
    """

    def __init__(self, choices: list[ResponseChoice]) -> None:
        super().__init__()
        self.choices = choices

    def compose(self) -> ComposeResult:
        with Vertical(classes="choice-buttons"):
            for i, choice in enumerate(self.choices):
                number = i + 1
                css_class = (
                    "choice-default" if choice.is_default else "choice-secondary"
                )
                yield Button(
                    f"{number}: {choice.label}",
                    id=f"btn-choice-{i}",
                    classes=css_class,
                )

    def on_mount(self) -> None:
        """Auto-focus the default choice button on mount."""
        # Find the default choice
        for i, choice in enumerate(self.choices):
            if choice.is_default:
                try:
                    btn = self.query_one(f"#btn-choice-{i}", Button)
                    btn.focus()
                    return
                except NoMatches:
                    pass

        # Fallback: focus the first button
        try:
            btn = self.query_one("#btn-choice-0", Button)
            btn.focus()
        except NoMatches:
            pass

    @on(Button.Pressed)
    def handle_button_pressed(self, event: Button.Pressed) -> None:
        """Handle any choice button press."""
        button_id = event.button.id
        if button_id and button_id.startswith("btn-choice-"):
            index = int(button_id.split("-")[-1])
            if 0 <= index < len(self.choices):
                self.post_message(ChoiceSelected(self.choices[index]))

    def on_key(self, event: events.Key) -> None:
        """Handle keyboard shortcuts for choice selection.

        Shortcuts:
            Enter: Select the default choice (or first if no default)
            1-9: Select choice by number
        """
        if event.key == "enter":
            # Find default choice, or use first
            for choice in self.choices:
                if choice.is_default:
                    self.post_message(ChoiceSelected(choice))
                    event.stop()
                    return
            # No default marked, use first
            if self.choices:
                self.post_message(ChoiceSelected(self.choices[0]))
                event.stop()
            return

        # Number key selection (1-9)
        if event.key.isdigit() and event.key != "0":
            index = int(event.key) - 1
            if 0 <= index < len(self.choices):
                self.post_message(ChoiceSelected(self.choices[index]))
                event.stop()
