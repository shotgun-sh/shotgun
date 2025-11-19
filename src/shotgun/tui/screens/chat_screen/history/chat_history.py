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
        self._rendered_count = 0  # Track how many messages have been mounted

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

        # Track how many messages were rendered during initial compose
        self._rendered_count = len(filtered)

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

        # Handle case where streaming inflated _rendered_count but final messages differ
        # This happens when error replaces ModelResponse with HintMessage
        if len(filtered) <= self._rendered_count and filtered:
            # Check if the last rendered item type differs from what should be there
            # Children: [UserQuestion, AgentResponse, ..., PartialResponse]
            # We need to check the item before PartialResponseWidget
            num_children = len(self.vertical_tail.children)
            if num_children > 1:  # Has items besides PartialResponseWidget
                last_widget = self.vertical_tail.children[-2]  # Item before Partial
                last_filtered = filtered[-1]

                # Check type mismatch
                type_mismatch = (
                    (
                        isinstance(last_widget, AgentResponseWidget)
                        and isinstance(last_filtered, HintMessage)
                    )
                    or (
                        isinstance(last_widget, HintMessageWidget)
                        and isinstance(last_filtered, ModelResponse)
                    )
                    or (
                        isinstance(last_widget, AgentResponseWidget)
                        and isinstance(last_filtered, ModelRequest)
                    )
                    or (
                        isinstance(last_widget, UserQuestionWidget)
                        and not isinstance(last_filtered, ModelRequest)
                    )
                )

                if type_mismatch:
                    # Remove the mismatched widget and adjust count
                    last_widget.remove()
                    self._rendered_count = len(filtered) - 1

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

            # Scroll to bottom to show newly added messages
            self.vertical_tail.scroll_end(animate=False)
