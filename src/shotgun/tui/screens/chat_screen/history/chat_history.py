"""Chat history widget - main container for message display."""

import logging
from collections.abc import Generator, Sequence

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    UserPromptPart,
)
from textual import events
from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget

from shotgun.agents.messages import InternalPromptPart
from shotgun.tui.components.prompt_input import PromptInput
from shotgun.tui.components.vertical_tail import VerticalTail
from shotgun.tui.screens.chat_screen.hint_message import HintMessage, HintMessageWidget

from .agent_response import AgentResponseWidget
from .partial_response import PartialResponseWidget
from .user_question import UserQuestionWidget

logger = logging.getLogger(__name__)


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
            # Skip ModelRequest messages without visible user content
            if isinstance(item, ModelRequest):
                # Check for visible user content (UserPromptPart but NOT InternalPromptPart)
                has_visible_user_content = any(
                    isinstance(part, UserPromptPart)
                    and not isinstance(part, InternalPromptPart)
                    for part in item.parts
                )
                if not has_visible_user_content:
                    # Skip: either just tool returns or internal system prompts
                    continue

            yield item

    def update_messages(self, messages: list[ModelMessage | HintMessage]) -> None:
        """Update the displayed messages using incremental mounting."""
        if not self.vertical_tail:
            logger.debug(
                "[CHAT_HISTORY] update_messages called but vertical_tail is None"
            )
            return

        self.items = messages
        filtered = list(self.filtered_items())

        # If rendered count is higher than filtered count, the message list was
        # modified (not just appended). Remove existing widgets and reset.
        # This can happen when messages are compacted, filtered, or cleared.
        if self._rendered_count > len(filtered):
            logger.debug(
                "[CHAT_HISTORY] Rendered count (%d) > filtered count (%d), "
                "removing existing widgets to rebuild",
                self._rendered_count,
                len(filtered),
            )
            # Remove all message widgets except PartialResponseWidget
            for child in list(self.vertical_tail.children):
                if not isinstance(child, PartialResponseWidget):
                    child.remove()
            self._rendered_count = 0

        # Only mount new messages that haven't been rendered yet
        if len(filtered) > self._rendered_count:
            new_messages = filtered[self._rendered_count :]
            logger.debug(
                "[CHAT_HISTORY] Mounting %d new messages (total=%d, filtered=%d)",
                len(new_messages),
                len(messages),
                len(filtered),
            )
            for item in new_messages:
                widget: Widget
                if isinstance(item, ModelRequest):
                    widget = UserQuestionWidget(item)
                elif isinstance(item, HintMessage):
                    widget = HintMessageWidget(item)
                elif isinstance(item, ModelResponse):
                    widget = AgentResponseWidget(item)
                else:
                    logger.debug(
                        "[CHAT_HISTORY] Skipping unknown message type: %s",
                        type(item).__name__,
                    )
                    continue

                # Mount before the PartialResponseWidget
                self.vertical_tail.mount(widget, before=self.vertical_tail.children[-1])

            self._rendered_count = len(filtered)

            # Scroll to bottom to show newly added messages
            self.vertical_tail.scroll_end(animate=False)

    def on_click(self, event: events.Click) -> None:
        """Focus the prompt input when clicking on the history area.

        Skip focusing if text is selected (to allow copy operations).
        """
        # Only handle left clicks
        if event.button != 1:
            return

        # Don't focus input if user has selected text (they might want to copy it)
        if self.screen.get_selected_text():
            return

        results = self.screen.query(PromptInput)
        if results:
            prompt_input = results.first()
            if prompt_input.display:
                prompt_input.focus()
