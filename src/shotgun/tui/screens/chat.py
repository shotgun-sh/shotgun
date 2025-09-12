from textual import on
from textual.app import ComposeResult
from textual.containers import Container
from textual.reactive import reactive
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import Markdown

from ..components.prompt_input import PromptInput
from ..components.vertical_tail import VerticalTail


class PromptHistory:
    def __init__(self) -> None:
        self.prompts: list[str] = ["Hello there!"]
        self.curr: int | None = None

    def next(self) -> str:
        if self.curr is None:
            self.curr = -1
        else:
            self.curr = -1
        return self.prompts[self.curr]

    def prev(self) -> str:
        if self.curr is None:
            raise Exception("current entry is none")
        if self.curr == -1:
            self.curr = None
            return ""
        self.curr += 1
        return ""

    def append(self, text: str) -> None:
        self.prompts.append(text)
        self.curr = None


class ChatHistory(Widget):
    DEFAULT_CSS = """
        VerticalTail {
            align: left bottom;
        }
    """

    def __init__(self, items: list[str]) -> None:
        super().__init__()
        self.items = items

    def render_history(self) -> ComposeResult:
        for item in self.items:
            yield Markdown(markdown=item)

    def compose(self) -> ComposeResult:
        yield VerticalTail(*self.render_history())


class StatusBar(Widget):
    DEFAULT_CSS = """
        StatusBar {
            text-wrap: wrap;
        }
    """

    def render(self) -> str:
        return """[$foreground-muted]Press [bold $text]Enter[/] to send • Ctrl+T to view artifacts • Ctrl+O for web preview • /help for commands[/]"""


class ChatScreen(Screen[None]):
    CSS_PATH = "chat.tcss"

    value = reactive("")
    history: PromptHistory = PromptHistory()
    prompts = reactive(list[str](), recompose=True)

    def __init__(self) -> None:
        super().__init__()
        self.prompts = self.history.prompts.copy()

    def on_mount(self) -> None:
        self.query_one(PromptInput).focus(scroll_visible=True)

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        with Container(id="window"):
            yield ChatHistory(self.prompts)
            with Container(id="footer"):
                yield StatusBar()
                yield PromptInput(
                    text=self.value,
                    highlight_cursor_line=False,
                    id="prompt-input",
                    placeholder="Type your message",
                )

    @on(PromptInput.Submitted)
    def handle_submit(self, message: PromptInput.Submitted) -> None:
        self.history.append(message.text)
        self.prompts = self.history.prompts.copy()

        # Clear the input
        self.value = ""
        prompt_input = self.query_one(PromptInput)
        prompt_input.clear()
        prompt_input.focus()
