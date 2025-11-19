"""Chat history widget - main container for message display."""

from collections.abc import Generator, Sequence

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    UserPromptPart,
)
from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget

from shotgun.tui.components.vertical_tail import VerticalTail
from shotgun.tui.screens.chat_screen.hint_message import HintMessage, HintMessageWidget

from .agent_response import AgentResponseWidget
from .partial_response import PartialResponseWidget
from .user_question import UserQuestionWidget


class ChatHistory(Widget):
    """Main widget for displaying chat message history."""

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
        self._rendered_items: list[int] = []  # Track id() of rendered items

    def compose(self) -> ComposeResult:
        """Compose the chat history widget."""
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
            yield PartialResponseWidget(None).data_bind(
                item=ChatHistory.partial_response
            )

        # Track which items were rendered during initial compose
        self._rendered_items = [id(item) for item in filtered]

    def filtered_items(self) -> Generator[ModelMessage | HintMessage, None, None]:
        """Filter and yield items for display."""
        for item in self.items:
            # Skip ModelRequest messages that only contain ToolReturnPart
            # (these are internal tool results, not user prompts)
            if isinstance(item, ModelRequest):
                has_user_content = any(
                    isinstance(part, UserPromptPart) for part in item.parts
                )
                if not has_user_content:
                    # This is just a tool return, skip displaying it
                    continue

            yield item

    def update_messages(self, messages: list[ModelMessage | HintMessage]) -> None:
        """Update the displayed messages using incremental mounting."""
        if not self.vertical_tail:
            return

        self.items = messages
        filtered = list(self.filtered_items())
        filtered_ids = [id(item) for item in filtered]

        # Check if any existing items were replaced (not just new items added)
        items_replaced = False
        for i, item_id in enumerate(filtered_ids):
            if i < len(self._rendered_items) and self._rendered_items[i] != item_id:
                items_replaced = True
                break

        # If items were replaced, we need to remount from that position
        if items_replaced:
            # Remove widgets from the replaced position onwards (excluding PartialResponseWidget)
            children_to_remove = list(self.vertical_tail.children)[i:-1]
            for child in children_to_remove:
                child.remove()

            # Mount the replaced and new items
            for item in filtered[i:]:
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

            self._rendered_items = filtered_ids
            self.vertical_tail.scroll_end(animate=False)

        # Only mount new messages that haven't been rendered yet
        elif len(filtered) > len(self._rendered_items):
            new_messages = filtered[len(self._rendered_items):]
            for item in new_messages:
                new_widget: Widget
                if isinstance(item, ModelRequest):
                    new_widget = UserQuestionWidget(item)
                elif isinstance(item, HintMessage):
                    new_widget = HintMessageWidget(item)
                elif isinstance(item, ModelResponse):
                    new_widget = AgentResponseWidget(item)
                else:
                    continue

                # Mount before the PartialResponseWidget
                self.vertical_tail.mount(new_widget, before=self.vertical_tail.children[-1])

            self._rendered_items = filtered_ids

            # Scroll to bottom to show newly added messages
            self.vertical_tail.scroll_end(animate=False)
