import json
from collections.abc import Sequence

from pydantic_ai.messages import (
    BuiltinToolCallPart,
    BuiltinToolReturnPart,
    ModelMessage,
    ModelRequest,
    ModelRequestPart,
    ModelResponse,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
)
from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Markdown

from shotgun.tui.components.vertical_tail import VerticalTail


class PartialResponseWidget(Widget):  # TODO: doesn't work lol
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
        if item is None:
            self.display = False
        else:
            self.display = True


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
    partial_response: reactive[ModelMessage | None] = reactive(None)

    def __init__(self) -> None:
        super().__init__()
        self.items: list[ModelMessage] = []
        self.vertical_tail: VerticalTail | None = None
        self.partial_response = None

    def compose(self) -> ComposeResult:
        self.vertical_tail = VerticalTail()
        with self.vertical_tail:
            for item in self.items:
                if isinstance(item, ModelRequest):
                    yield UserQuestionWidget(item)
                elif isinstance(item, ModelResponse):
                    yield AgentResponseWidget(item)
            yield PartialResponseWidget(self.partial_response).data_bind(
                item=ChatHistory.partial_response
            )

    def watch_partial_response(self, _partial_response: ModelMessage | None) -> None:
        self.call_after_refresh(self.autoscroll)

    def update_messages(self, messages: list[ModelMessage]) -> None:
        """Update the displayed messages without recomposing."""
        if not self.vertical_tail:
            return

        self.items = messages
        self.refresh(recompose=True)

        self.autoscroll()

    def autoscroll(self) -> None:
        if self.vertical_tail:
            self.vertical_tail.scroll_end(animate=False)


class UserQuestionWidget(Widget):
    def __init__(self, item: ModelRequest | None) -> None:
        super().__init__()
        self.item = item

    def compose(self) -> ComposeResult:
        self.display = self.item is not None
        if self.item is None:
            yield Markdown(markdown="")
        else:
            prompt = "".join(
                str(part.content) for part in self.item.parts if part.content
            )
            yield Markdown(markdown=f"**>** {prompt}")

    def format_prompt_parts(self, parts: Sequence[ModelRequestPart]) -> str:
        acc = ""
        for part in parts:
            if isinstance(part, TextPart):
                acc += (
                    f"**>** {part.content if isinstance(part.content, str) else ''}\n\n"
                )
            elif isinstance(part, ToolCallPart):
                if part.tool_name == "ask_user" and isinstance(part.content, dict):
                    acc += f"**>** {part.content['answer']}\n\n"
                else:
                    acc += "∟ finished\n\n"  # let's not show anything yet
        return acc


class AgentResponseWidget(Widget):
    def __init__(self, item: ModelResponse | None) -> None:
        super().__init__()
        self.item = item

    def compose(self) -> ComposeResult:
        self.display = self.item is not None
        if self.item is None:
            yield Markdown(markdown="")
        else:
            yield Markdown(markdown=f"**⏺** {self.compute_output()}")

    def compute_output(self) -> str:
        acc = ""
        if self.item is None:
            return ""
        for idx, part in enumerate(self.item.parts):
            if isinstance(part, TextPart):
                acc += part.content + "\n\n"
            elif isinstance(part, ToolCallPart):
                parts_str = self._format_tool_call_part(part)
                acc += parts_str + "\n\n"
            elif isinstance(part, ToolReturnPart):
                acc += (
                    f"tool ({part.tool_name}) return: "
                    + self._format_tool_return_call_part(part)
                    + "\n\n"
                )
            elif isinstance(part, BuiltinToolCallPart):
                acc += f"builtin tool ({part.tool_name}): {part.args}\n\n"
            elif isinstance(part, BuiltinToolReturnPart):
                acc += f"builtin tool ({part.tool_name}) return: {part.content}\n\n"
            elif isinstance(part, ThinkingPart):
                if (
                    idx == len(self.item.parts) - 1
                ):  # show the thinking part only if it's the last part
                    acc += (
                        f"thinking: {part.content}\n\n"
                        if part.content
                        else "Thinking..."
                    )
                else:
                    continue
        return acc.strip()

    def _format_tool_call_part(self, part: ToolCallPart) -> str:
        if part.tool_name == "ask_user":
            return self._format_ask_user_part(part)
        # write_file
        if part.tool_name == "write_file" or part.tool_name == "append_file":
            if isinstance(part.args, dict) and "filename" in part.args:
                return f"{part.tool_name}({part.args['filename']})"
            else:
                return f"{part.tool_name}()"
        if part.tool_name == "write_artifact_section":
            if isinstance(part.args, dict) and "section_title" in part.args:
                return f"{part.tool_name}({part.args['section_title']})"
            else:
                return f"{part.tool_name}()"
        if part.tool_name == "create_artifact":
            if isinstance(part.args, dict) and "name" in part.args:
                return f"{part.tool_name}({part.args['name']})"
            else:
                return f"▪ {part.tool_name}()"

        return f"{part.tool_name}({part.args})"

    def _format_ask_user_part(
        self,
        part: ToolCallPart,
    ) -> str:
        if isinstance(part.args, str):
            try:
                _args = json.loads(part.args) if part.args.strip() else {}
            except json.JSONDecodeError:
                _args = {}
        else:
            _args = part.args

        if isinstance(_args, dict) and "question" in _args:
            return f"{_args['question']}"
        else:
            return "❓ "

    def _format_tool_return_call_part(self, part: ToolReturnPart) -> str:
        content = part.content
        if part.tool_name == "ask_user":
            response = content.get("answer", "") if isinstance(content, dict) else ""
            return f"**⏺** {response}"
        return f"∟ {content}"
