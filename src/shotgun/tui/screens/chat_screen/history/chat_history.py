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
        self._rendered_ids: list[int] = []  # Track id() of rendered items

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
        self._rendered_ids = [id(item) for item in filtered]

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

        # Check if existing items match (for incremental mounting)
        can_append = True
        if len(filtered_ids) >= len(self._rendered_ids):
            # Check that all previously rendered items are still in same position
            for i, prev_id in enumerate(self._rendered_ids):
                if filtered_ids[i] != prev_id:
                    can_append = False
                    break
        else:
            # Fewer items than before (shouldn't normally happen)
            can_append = False

        if can_append and len(filtered) > len(self._rendered_ids):
            # Just append new messages
            new_messages = filtered[len(self._rendered_ids):]
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

            self._rendered_ids = filtered_ids
            self.vertical_tail.scroll_end(animate=False)

        elif not can_append:
            # Items changed - clear and remount all
            # Remove all children except the last one (PartialResponseWidget)
            for child in list(self.vertical_tail.children)[:-1]:
                child.remove()

            # Remount all items
            for item in filtered:
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

            self._rendered_ids = filtered_ids
            self.vertical_tail.scroll_end(animate=False)
