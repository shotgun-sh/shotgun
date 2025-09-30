import json
from collections.abc import Generator, Sequence

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
    UserPromptPart,
)
from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Markdown

from shotgun.agents.models import UserAnswer
from shotgun.tui.components.vertical_tail import VerticalTail
from shotgun.tui.screens.chat_screen.hint_message import HintMessage, HintMessageWidget


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
        self.items: Sequence[ModelMessage | HintMessage] = []
        self.vertical_tail: VerticalTail | None = None
        self.partial_response = None
        self._rendered_count = 0  # Track how many messages have been mounted

    def compose(self) -> ComposeResult:
        self.vertical_tail = VerticalTail()

        filtered = list(self.filtered_items())
        with self.vertical_tail:
            for item in filtered:
                if isinstance(item, ModelRequest):
                    yield UserQuestionWidget(item)
                elif isinstance(item, HintMessage):
                    yield HintMessageWidget(item)
                elif isinstance(item, ModelResponse):
                    yield AgentResponseWidget(item)
            yield PartialResponseWidget(self.partial_response).data_bind(
                item=ChatHistory.partial_response
            )

        # Track how many messages were rendered during initial compose
        self._rendered_count = len(filtered)

    def filtered_items(self) -> Generator[ModelMessage | HintMessage, None, None]:
        for idx, next_item in enumerate(self.items):
            prev_item = self.items[idx - 1] if idx > 0 else None

            if isinstance(prev_item, ModelRequest) and isinstance(
                next_item, ModelResponse
            ):
                ask_user_tool_response_part = next(
                    (
                        part
                        for part in prev_item.parts
                        if isinstance(part, ToolReturnPart)
                        and part.tool_name == "ask_user"
                    ),
                    None,
                )

                ask_user_part = next(
                    (
                        part
                        for part in next_item.parts
                        if isinstance(part, ToolCallPart)
                        and part.tool_name == "ask_user"
                    ),
                    None,
                )

                if not ask_user_part or not ask_user_tool_response_part:
                    yield next_item
                    continue
                if (
                    ask_user_tool_response_part.tool_call_id
                    == ask_user_part.tool_call_id
                ):
                    continue  # don't emit tool call that happens after tool response

            yield next_item

    def update_messages(self, messages: list[ModelMessage | HintMessage]) -> None:
        """Update the displayed messages using incremental mounting."""
        if not self.vertical_tail:
            return

        self.items = messages
        filtered = list(self.filtered_items())

        # Only mount new messages that haven't been rendered yet
        if len(filtered) > self._rendered_count:
            new_messages = filtered[self._rendered_count :]
            for item in new_messages:
                widget: Widget
                if isinstance(item, ModelRequest):
                    widget = UserQuestionWidget(item)
                elif isinstance(item, HintMessage):
                    widget = HintMessageWidget(item)
                elif isinstance(item, ModelResponse):
                    widget = AgentResponseWidget(item)
                else:
                    continue

                # Mount before the PartialResponseWidget
                self.vertical_tail.mount(widget, before=self.vertical_tail.children[-1])

            self._rendered_count = len(filtered)


class UserQuestionWidget(Widget):
    def __init__(self, item: ModelRequest | None) -> None:
        super().__init__()
        self.item = item

    def compose(self) -> ComposeResult:
        self.display = self.item is not None
        if self.item is None:
            yield Markdown(markdown="")
        else:
            prompt = self.format_prompt_parts(self.item.parts)
            yield Markdown(markdown=prompt)

    def format_prompt_parts(self, parts: Sequence[ModelRequestPart]) -> str:
        acc = ""
        for part in parts:
            if isinstance(part, UserPromptPart):
                acc += (
                    f"**>** {part.content if isinstance(part.content, str) else ''}\n\n"
                )
            elif isinstance(part, ToolReturnPart):
                if part.tool_name == "ask_user":
                    acc += f"**>** {part.content.answer if isinstance(part.content, UserAnswer) else part.content['answer']}\n\n"
                else:
                    # acc += "  ∟ finished\n\n"  # let's not show anything yet
                    pass
            elif isinstance(part, UserPromptPart):
                acc += f"**>** {part.content}\n\n"
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
            yield Markdown(markdown=self.compute_output())

    def compute_output(self) -> str:
        acc = ""
        if self.item is None:
            return ""
        for idx, part in enumerate(self.item.parts):
            if isinstance(part, TextPart):
                acc += f"**⏺** {part.content}\n\n"
            elif isinstance(part, ToolCallPart):
                parts_str = self._format_tool_call_part(part)
                acc += parts_str + "\n\n"
            elif isinstance(part, BuiltinToolCallPart):
                acc += f"{part.tool_name}({part.args})\n\n"
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

    def _truncate(self, text: str, max_length: int = 100) -> str:
        """Truncate text to max_length characters, adding ellipsis if needed."""
        if len(text) <= max_length:
            return text
        return text[: max_length - 3] + "..."

    def _parse_args(self, args: dict[str, object] | str | None) -> dict[str, object]:
        """Parse tool call arguments, handling both dict and JSON string formats."""
        if args is None:
            return {}
        if isinstance(args, str):
            try:
                return json.loads(args) if args.strip() else {}
            except json.JSONDecodeError:
                return {}
        return args if isinstance(args, dict) else {}

    def _format_tool_call_part(self, part: ToolCallPart) -> str:
        if part.tool_name == "ask_user":
            return self._format_ask_user_part(part)

        # Parse args once (handles both JSON string and dict)
        args = self._parse_args(part.args)

        # Codebase tools - show friendly names
        if part.tool_name == "query_graph":
            if "query" in args:
                query = self._truncate(str(args["query"]))
                return f'Querying code: "{query}"'
            return "Querying code"

        if part.tool_name == "retrieve_code":
            if "qualified_name" in args:
                return f'Retrieving code: "{args["qualified_name"]}"'
            return "Retrieving code"

        if part.tool_name == "file_read":
            if "file_path" in args:
                return f'Reading file: "{args["file_path"]}"'
            return "Reading file"

        if part.tool_name == "directory_lister":
            if "directory" in args:
                return f'Listing directory: "{args["directory"]}"'
            return "Listing directory"

        if part.tool_name == "codebase_shell":
            command = args.get("command", "")
            cmd_args = args.get("args", [])
            # Handle cmd_args as list of strings
            if isinstance(cmd_args, list):
                args_str = " ".join(str(arg) for arg in cmd_args)
            else:
                args_str = ""
            full_cmd = f"{command} {args_str}".strip()
            if full_cmd:
                return f'Running shell: "{self._truncate(full_cmd)}"'
            return "Running shell"

        # File management tools
        if part.tool_name == "read_file":
            if "filename" in args:
                return f'Reading file: "{args["filename"]}"'
            return "Reading file"

        # Web search tools
        if part.tool_name in [
            "openai_web_search_tool",
            "anthropic_web_search_tool",
            "gemini_web_search_tool",
        ]:
            if "query" in args:
                query = self._truncate(str(args["query"]))
                return f'Searching web: "{query}"'
            return "Searching web"

        # write_file
        if part.tool_name == "write_file" or part.tool_name == "append_file":
            if "filename" in args:
                return f"{part.tool_name}({args['filename']})"
            return f"{part.tool_name}()"

        if part.tool_name == "write_artifact_section":
            if "section_title" in args:
                return f"{part.tool_name}({args['section_title']})"
            return f"{part.tool_name}()"

        if part.tool_name == "create_artifact":
            if "name" in args:
                return f"{part.tool_name}({args['name']})"
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
