"""User question widget for chat history."""

from collections.abc import Sequence

from pydantic_ai.messages import (
    ModelRequest,
    ModelRequestPart,
    ToolReturnPart,
    UserPromptPart,
)
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Markdown


class UserQuestionWidget(Widget):
    """Widget that displays user prompts in the chat history."""

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
        """Format user prompt parts into markdown."""
        acc = ""
        for part in parts:
            if isinstance(part, UserPromptPart):
                acc += (
                    f"**>** {part.content if isinstance(part.content, str) else ''}\n\n"
                )
            elif isinstance(part, ToolReturnPart):
                # Don't show tool return parts in the UI
                pass
        return acc
