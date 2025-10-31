"""Partial response widget for streaming chat messages."""

from pydantic_ai.messages import ModelMessage
from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget

from .agent_response import AgentResponseWidget
from .user_question import UserQuestionWidget


class PartialResponseWidget(Widget):  # TODO: doesn't work lol
    """Widget that displays a streaming/partial response in the chat history."""

    DEFAULT_CSS = """
        PartialResponseWidget {
            height: auto;
        }
        Markdown, AgentResponseWidget, UserQuestionWidget {
            height: auto;
        }
    """

    item: reactive[ModelMessage | None] = reactive(None, recompose=True)

    def __init__(self, item: ModelMessage | None) -> None:
        super().__init__()
        self.item = item

    def compose(self) -> ComposeResult:
        if self.item is None:
            pass
        elif self.item.kind == "response":
            yield AgentResponseWidget(self.item)
        elif self.item.kind == "request":
            yield UserQuestionWidget(self.item)

    def watch_item(self, item: ModelMessage | None) -> None:
        """React to changes in the item."""
        if item is None:
            self.display = False
        else:
            self.display = True
