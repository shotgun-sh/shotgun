"""Agent response widget for chat history."""

from pydantic_ai.messages import (
    BuiltinToolCallPart,
    BuiltinToolReturnPart,
    ModelResponse,
    TextPart,
    ThinkingPart,
    ToolCallPart,
)
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Markdown

from .formatters import ToolFormatter


class AgentResponseWidget(Widget):
    """Widget that displays agent responses in the chat history."""

    def __init__(self, item: ModelResponse | None, is_sub_agent: bool = False) -> None:
        super().__init__()
        self.item = item
        self.is_sub_agent = is_sub_agent

    def compose(self) -> ComposeResult:
        self.display = self.item is not None
        if self.item is None:
            yield Markdown(markdown="")
        else:
            yield Markdown(markdown=self.compute_output())

    def compute_output(self) -> str:
        """Compute the markdown output for the agent response."""
        acc = ""
        if self.item is None:
            return ""

        # Use different prefix for sub-agent responses
        prefix = "**⏺** " if not self.is_sub_agent else "  **↳** "

        for idx, part in enumerate(self.item.parts):
            if isinstance(part, TextPart):
                # Only show the prefix if there's actual content
                if part.content and part.content.strip():
                    acc += f"{prefix}{part.content}\n\n"
            elif isinstance(part, ToolCallPart):
                parts_str = ToolFormatter.format_tool_call_part(part)
                if parts_str:  # Only add if there's actual content
                    acc += parts_str + "\n\n"
            elif isinstance(part, BuiltinToolCallPart):
                # Format builtin tool calls using registry
                formatted = ToolFormatter.format_builtin_tool_call(part)
                if formatted:  # Only add if not hidden
                    acc += formatted + "\n\n"
            elif isinstance(part, BuiltinToolReturnPart):
                # Don't show tool return parts in the UI
                pass
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
