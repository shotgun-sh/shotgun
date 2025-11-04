# mypy: disable-error-code="import-not-found"
"""Widget coordinator to centralize widget queries and updates.

This module eliminates scattered `query_one()` calls throughout ChatScreen
by providing a single place for all widget updates. This improves:
- Testability (can test update logic in isolation)
- Maintainability (clear update contracts)
- Performance (can batch updates if needed)
"""

import logging
from typing import TYPE_CHECKING

from pydantic_ai.messages import ModelMessage

from shotgun.agents.config.models import ModelName
from shotgun.agents.models import AgentType
from shotgun.tui.components.context_indicator import ContextIndicator
from shotgun.tui.components.mode_indicator import ModeIndicator
from shotgun.tui.components.prompt_input import PromptInput
from shotgun.tui.components.spinner import Spinner
from shotgun.tui.components.status_bar import StatusBar
from shotgun.tui.screens.chat_screen.history.chat_history import ChatHistory

if TYPE_CHECKING:
    from shotgun.agents.context_analyzer.models import ContextAnalysis
    from shotgun.agents.conversation_history import HintMessage
    from shotgun.tui.screens.chat import ChatScreen

logger = logging.getLogger(__name__)


class WidgetCoordinator:
    """Coordinates updates to all widgets in ChatScreen.

    This class centralizes all `query_one()` calls and widget manipulations,
    providing clear update methods instead of scattered direct queries.

    Benefits:
    - Single place for all widget updates
    - Testable without full TUI
    - Clear update contracts
    - Can add batching/debouncing easily
    """

    def __init__(self, screen: "ChatScreen"):
        """Initialize the coordinator with a reference to the screen.

        Args:
            screen: The ChatScreen instance containing the widgets.
        """
        self.screen = screen

    def update_for_mode_change(
        self, new_mode: AgentType, placeholder: str | None = None
    ) -> None:
        """Update all widgets when agent mode changes.

        Args:
            new_mode: The new agent mode.
            placeholder: Optional placeholder text for input. If not provided,
                        will use the screen's _placeholder_for_mode method.
        """
        if not self.screen.is_mounted:
            return

        # Update mode indicator
        try:
            mode_indicator = self.screen.query_one(ModeIndicator)
            mode_indicator.mode = new_mode
            mode_indicator.refresh()
        except Exception as e:
            logger.exception(f"Failed to update mode indicator: {e}")

        # Update prompt input placeholder
        try:
            prompt_input = self.screen.query_one(PromptInput)
            if placeholder is None:
                placeholder = self.screen._placeholder_for_mode(
                    new_mode, force_new=True
                )
            prompt_input.placeholder = placeholder
            prompt_input.refresh()
        except Exception as e:
            logger.exception(f"Failed to update prompt input: {e}")

    def update_for_processing_state(
        self, is_processing: bool, spinner_text: str | None = None
    ) -> None:
        """Update widgets when processing state changes.

        Args:
            is_processing: Whether processing is active.
            spinner_text: Optional text to display in spinner.
        """
        if not self.screen.is_mounted:
            return

        # Update spinner visibility
        try:
            spinner = self.screen.query_one("#spinner", Spinner)
            spinner.set_classes("" if is_processing else "hidden")
            spinner.display = is_processing
            if spinner_text and is_processing:
                spinner.text = spinner_text
        except Exception as e:
            logger.exception(f"Failed to update spinner: {e}")

        # Update status bar
        try:
            status_bar = self.screen.query_one(StatusBar)
            status_bar.working = is_processing
            status_bar.refresh()
        except Exception as e:
            logger.exception(f"Failed to update status bar: {e}")

    def update_for_qa_mode(self, qa_mode_active: bool) -> None:
        """Update widgets when Q&A mode changes.

        Args:
            qa_mode_active: Whether Q&A mode is active.
        """
        if not self.screen.is_mounted:
            return

        # Update status bar
        try:
            status_bar = self.screen.query_one(StatusBar)
            status_bar.refresh()
        except Exception as e:
            logger.exception(f"Failed to update status bar for Q&A: {e}")

        # Update mode indicator
        try:
            mode_indicator = self.screen.query_one(ModeIndicator)
            mode_indicator.refresh()
        except Exception as e:
            logger.exception(f"Failed to update mode indicator for Q&A: {e}")

    def update_messages(self, messages: list[ModelMessage | "HintMessage"]) -> None:
        """Update chat history with new messages.

        Args:
            messages: The messages to display.
        """
        if not self.screen.is_mounted:
            return

        try:
            chat_history = self.screen.query_one(ChatHistory)
            chat_history.update_messages(messages)
        except Exception as e:
            logger.exception(f"Failed to update messages: {e}")

    def set_partial_response(
        self, message: ModelMessage | None, messages: list[ModelMessage | "HintMessage"]
    ) -> None:
        """Update chat history with partial streaming response.

        Args:
            message: The partial message being streamed.
            messages: The full message history.
        """
        if not self.screen.is_mounted:
            return

        try:
            chat_history = self.screen.query_one(ChatHistory)
            if message:
                chat_history.partial_response = message
            chat_history.update_messages(messages)
        except Exception as e:
            logger.exception(f"Failed to set partial response: {e}")

    def update_context_indicator(
        self, analysis: "ContextAnalysis | None", model_name: str
    ) -> None:
        """Update context indicator with new analysis.

        Args:
            analysis: The context analysis results.
            model_name: The current model name.
        """
        if not self.screen.is_mounted:
            return

        try:
            context_indicator = self.screen.query_one(ContextIndicator)
            # Cast the string model name to ModelName type
            model = ModelName(model_name) if model_name else None
            context_indicator.update_context(analysis, model)
        except Exception as e:
            logger.exception(f"Failed to update context indicator: {e}")

    def update_prompt_input(
        self,
        placeholder: str | None = None,
        clear: bool = False,
        focus: bool = False,
    ) -> None:
        """Update prompt input widget.

        Args:
            placeholder: New placeholder text.
            clear: Whether to clear the input.
            focus: Whether to focus the input.
        """
        if not self.screen.is_mounted:
            return

        try:
            prompt_input = self.screen.query_one(PromptInput)
            if placeholder is not None:
                prompt_input.placeholder = placeholder
            if clear:
                prompt_input.clear()
            if focus:
                prompt_input.focus()
        except Exception as e:
            logger.exception(f"Failed to update prompt input: {e}")

    def refresh_mode_indicator(self) -> None:
        """Refresh mode indicator without changing mode."""
        if not self.screen.is_mounted:
            return

        try:
            mode_indicator = self.screen.query_one(ModeIndicator)
            mode_indicator.refresh()
        except Exception as e:
            logger.exception(f"Failed to refresh mode indicator: {e}")

    def update_spinner_text(self, text: str) -> None:
        """Update spinner text without changing visibility.

        Args:
            text: The new spinner text.
        """
        if not self.screen.is_mounted:
            return

        try:
            spinner = self.screen.query_one("#spinner", Spinner)
            if spinner.display:  # Only update if visible
                spinner.text = text
        except Exception as e:
            logger.exception(f"Failed to update spinner text: {e}")

    def set_context_streaming(self, streaming: bool) -> None:
        """Enable or disable context indicator streaming animation.

        Args:
            streaming: Whether to show streaming animation.
        """
        if not self.screen.is_mounted:
            return

        try:
            context_indicator = self.screen.query_one(ContextIndicator)
            context_indicator.set_streaming(streaming)
        except Exception as e:
            logger.exception(f"Failed to set context streaming: {e}")
