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

from shotgun.agents.messages import InternalPromptPart


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
                # Skip internal prompts (system-generated, not user input)
                if isinstance(part, InternalPromptPart):
                    continue
                content = self._extract_text_content(part.content)
                if content:
                    acc += f"**>** {content}\n\n"
                # Skip if no displayable text (e.g., only binary files)
            elif isinstance(part, ToolReturnPart):
                # Don't show tool return parts in the UI
                pass
        return acc

    def _extract_text_content(self, content: object) -> str:
        """Extract displayable text from UserPromptPart content.

        Content can be:
        - str: Return directly
        - list: Extract text strings, skip binary content (BinaryContent, ImageUrl, etc.)
        - other: Return empty string
        """
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            # Multimodal content - extract only text strings
            text_parts = [item for item in content if isinstance(item, str)]
            return " ".join(text_parts) if text_parts else ""
        return ""
