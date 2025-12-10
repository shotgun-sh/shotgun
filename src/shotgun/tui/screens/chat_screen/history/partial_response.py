"""Partial response widget for streaming chat messages."""

from pydantic_ai.messages import ModelMessage
from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget

from shotgun.tui.protocols import ActiveSubAgentProvider

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

    def _is_sub_agent_active(self) -> bool:
        """Check if a sub-agent is currently active."""
        if isinstance(self.screen, ActiveSubAgentProvider):
            return self.screen.active_sub_agent is not None
        return False

    def compose(self) -> ComposeResult:
        if self.item is None:
            pass
        elif self.item.kind == "response":
            yield AgentResponseWidget(
                self.item, is_sub_agent=self._is_sub_agent_active()
            )
        elif self.item.kind == "request":
            yield UserQuestionWidget(self.item)

    def watch_item(self, item: ModelMessage | None) -> None:
        """React to changes in the item."""
        if item is None:
            self.display = False
        else:
            self.display = True
