"""Chat history widget - main container for message display."""

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

from shotgun.tui.components.prompt_input import PromptInput
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
        self._is_streaming = False  # Track if we're in streaming mode

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

    def set_streaming(self, is_streaming: bool) -> None:
        """Set streaming mode state.

        During streaming, update_messages will store items but NOT update
        _rendered_count for streaming content. This prevents the count from
        getting out of sync when streaming messages differ from final messages.

        Args:
            is_streaming: True when streaming starts, False when it ends.
        """
        self._is_streaming = is_streaming

    def update_messages(self, messages: list[ModelMessage | HintMessage]) -> None:
        """Update the displayed messages using incremental mounting.

        During streaming (_is_streaming=True), ModelResponse messages are skipped
        because they're displayed via PartialResponseWidget. Other messages like
        HintMessage (e.g., "Delegating to...") and ModelRequest are still mounted.

        When streaming ends (_is_streaming=False), all new widgets are mounted
        including the final ModelResponse.
        """
        if not self.vertical_tail:
            return

        self.items = messages
        filtered = list(self.filtered_items())

        # Only mount new messages that haven't been rendered yet
        if len(filtered) > self._rendered_count:
            new_messages = filtered[self._rendered_count :]
            mounted_count = 0
            for item in new_messages:
                widget: Widget
                if isinstance(item, ModelRequest):
                    widget = UserQuestionWidget(item)
                elif isinstance(item, HintMessage):
                    widget = HintMessageWidget(item)
                elif isinstance(item, ModelResponse):
                    # During streaming, skip ModelResponse - it's shown in PartialResponseWidget
                    # This prevents _rendered_count from getting out of sync
                    if self._is_streaming:
                        continue
                    widget = AgentResponseWidget(item)
                else:
                    continue

                # Mount before the PartialResponseWidget
                self.vertical_tail.mount(widget, before=self.vertical_tail.children[-1])
                mounted_count += 1

            # Update rendered count by what we actually mounted
            # During streaming, we skip ModelResponse so count only non-ModelResponse
            if self._is_streaming:
                # Count only non-ModelResponse messages in the new batch
                non_response_count = sum(
                    1 for m in new_messages if not isinstance(m, ModelResponse)
                )
                self._rendered_count += non_response_count
            else:
                self._rendered_count = len(filtered)

            # Scroll to bottom to show newly added messages
            if mounted_count > 0:
                self.vertical_tail.scroll_end(animate=False)

    def on_click(self, event: events.Click) -> None:
        """Focus the prompt input when clicking on the history area."""
        # Only handle clicks that weren't already handled by a child widget
        if event.button == 1:  # Left click
            results = self.screen.query(PromptInput)
            if results:
                prompt_input = results.first()
                if prompt_input.display:
                    prompt_input.focus()
