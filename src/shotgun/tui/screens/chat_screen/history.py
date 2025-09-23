from pydantic_ai.messages import (
    BuiltinToolCallPart,
    BuiltinToolReturnPart,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ThinkingPart,
    ToolCallPart,
)
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Markdown

from shotgun.tui.components.vertical_tail import VerticalTail


class ChatHistory(Widget):
    DEFAULT_CSS = """
        VerticalTail {
            align: left bottom;

        }
        VerticalTail > * {
            height: auto;
        }

        Horizontal {
            height: auto;
            background: $secondary-muted;
        }

        Markdown {
            height: auto;
        }
    """

    def __init__(self) -> None:
        super().__init__()
        self.items: list[ModelMessage] = []
        self.vertical_tail: VerticalTail | None = None

    def compose(self) -> ComposeResult:
        self.vertical_tail = VerticalTail()
        yield self.vertical_tail

    def update_messages(self, messages: list[ModelMessage]) -> None:
        """Update the displayed messages without recomposing."""
        if not self.vertical_tail:
            return

        # Clear existing widgets
        self.vertical_tail.remove_children()

        # Add new message widgets
        for item in messages:
            if isinstance(item, ModelRequest):
                self.vertical_tail.mount(UserQuestionWidget(item))
            elif isinstance(item, ModelResponse):
                self.vertical_tail.mount(AgentResponseWidget(item))

        self.items = messages


class UserQuestionWidget(Widget):
    def __init__(self, item: ModelRequest) -> None:
        super().__init__()
        self.item = item

    def compose(self) -> ComposeResult:
        prompt = "".join(str(part.content) for part in self.item.parts if part.content)
        yield Markdown(markdown=f"**>** {prompt}")


class AgentResponseWidget(Widget):
    def __init__(self, item: ModelResponse) -> None:
        super().__init__()
        self.item = item

    def compose(self) -> ComposeResult:
        yield Markdown(markdown=f"**⏺** {self.compute_output()}")

    def compute_output(self) -> str:
        acc = ""
        for part in self.item.parts:  # TextPart | ToolCallPart | BuiltinToolCallPart | BuiltinToolReturnPart | ThinkingPart
            if isinstance(part, TextPart):
                acc += part.content
            elif isinstance(part, ToolCallPart):
                acc += f"{part.tool_name}({part.args})\n"
            elif isinstance(part, BuiltinToolCallPart):
                acc += f"{part.tool_name}({part.args})\n"
            elif isinstance(part, BuiltinToolReturnPart):
                acc += f"{part.tool_name}()\n"
            elif isinstance(part, ThinkingPart):
                acc += f"{part.content}\n"
        return acc
