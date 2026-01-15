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
from shotgun.attachments import AttachmentType, get_attachment_icon
from shotgun.attachments.parser import ATTACHMENT_PATH_PATTERN


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
                    # Check for attachment reference and add indicator
                    attachment_info = self._extract_attachment_info(content)
                    if attachment_info:
                        acc += f"**>** {content}\n\n{attachment_info}\n\n"
                    else:
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

    def _extract_attachment_info(self, content: str) -> str | None:
        """Extract attachment indicator from @path reference in content.

        Args:
            content: Text content that may contain @path reference.

        Returns:
            Formatted attachment indicator string, or None if no attachment.
        """
        match = ATTACHMENT_PATH_PATTERN.search(content)
        if not match:
            return None

        path_str = match.group(1)
        filename = path_str.split("/")[-1] if "/" in path_str else path_str

        # Determine icon based on extension
        extension = filename.split(".")[-1].lower() if "." in filename else ""
        if extension == "pdf":
            icon = get_attachment_icon(AttachmentType.PDF)
        elif extension in ("png", "jpg", "jpeg", "gif", "webp"):
            icon = get_attachment_icon(AttachmentType.PNG)  # Image icon
        else:
            return None  # Not a supported attachment

        return f"{icon} *{filename}*"
