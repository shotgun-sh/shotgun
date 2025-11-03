"""Modal dialog for codebase indexing prompts."""

from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static


class CodebaseIndexPromptScreen(ModalScreen[bool]):
    """Modal dialog asking whether to index the detected codebase."""

    DEFAULT_CSS = """
        CodebaseIndexPromptScreen {
            align: center middle;
            background: rgba(0, 0, 0, 0.0);
        }

        CodebaseIndexPromptScreen > #index-prompt-dialog {
            width: 60%;
            max-width: 60;
            height: auto;
            border: wide $primary;
            padding: 1 2;
            layout: vertical;
            background: $surface;
            height: auto;
        }

        #index-prompt-buttons {
            layout: horizontal;
            align-horizontal: right;
            height: auto;
        }
    """

    def compose(self) -> ComposeResult:
        with Container(id="index-prompt-dialog"):
            yield Label("Index this codebase?", id="index-prompt-title")
            yield Static(
                f"Would you like to index the codebase at:\n{Path.cwd()}\n\n"
                "This is required for the agent to understand your code and answer "
                "questions about it. Without indexing, the agent cannot analyze "
                "your codebase."
            )
            with Container(id="index-prompt-buttons"):
                yield Button(
                    "Index now",
                    id="index-prompt-confirm",
                    variant="primary",
                )
                yield Button("Not now", id="index-prompt-cancel")

    @on(Button.Pressed, "#index-prompt-cancel")
    def handle_cancel(self, event: Button.Pressed) -> None:
        event.stop()
        self.dismiss(False)

    @on(Button.Pressed, "#index-prompt-confirm")
    def handle_confirm(self, event: Button.Pressed) -> None:
        event.stop()
        self.dismiss(True)
