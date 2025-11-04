"""Main chat screen implementation."""

import asyncio
import logging
from pathlib import Path
from typing import cast

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolReturnPart,
    UserPromptPart,
)
from textual import events, on, work
from textual.app import ComposeResult
from textual.command import CommandPalette
from textual.containers import Container, Grid
from textual.keys import Keys
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Static

from shotgun.agents.agent_manager import (
    AgentManager,
    ClarifyingQuestionsMessage,
    CompactionCompletedMessage,
    CompactionStartedMessage,
    MessageHistoryUpdated,
    ModelConfigUpdated,
    PartialResponseMessage,
)
from shotgun.agents.config.models import MODEL_SPECS
from shotgun.agents.conversation_manager import ConversationManager
from shotgun.agents.history.compaction import apply_persistent_compaction
from shotgun.agents.history.token_estimation import estimate_tokens_from_messages
from shotgun.agents.models import (
    AgentDeps,
    AgentType,
    FileOperationTracker,
)
from shotgun.codebase.core.manager import (
    CodebaseAlreadyIndexedError,
    CodebaseGraphManager,
)
from shotgun.codebase.models import IndexProgress, ProgressPhase
from shotgun.posthog_telemetry import track_event
from shotgun.sdk.codebase import CodebaseSDK
from shotgun.sdk.exceptions import CodebaseNotFoundError, InvalidPathError
from shotgun.tui.commands import CommandHandler
from shotgun.tui.components.context_indicator import ContextIndicator
from shotgun.tui.components.mode_indicator import ModeIndicator
from shotgun.tui.components.prompt_input import PromptInput
from shotgun.tui.components.spinner import Spinner
from shotgun.tui.components.status_bar import StatusBar
from shotgun.tui.screens.chat.codebase_index_prompt_screen import (
    CodebaseIndexPromptScreen,
)
from shotgun.tui.screens.chat.codebase_index_selection import CodebaseIndexSelection
from shotgun.tui.screens.chat.help_text import (
    help_text_empty_dir,
    help_text_with_codebase,
)
from shotgun.tui.screens.chat.prompt_history import PromptHistory
from shotgun.tui.screens.chat_screen.command_providers import (
    DeleteCodebasePaletteProvider,
    UnifiedCommandProvider,
)
from shotgun.tui.screens.chat_screen.hint_message import HintMessage
from shotgun.tui.screens.chat_screen.history import ChatHistory
from shotgun.tui.screens.confirmation_dialog import ConfirmationDialog
from shotgun.tui.services.conversation_service import ConversationService
from shotgun.tui.state.processing_state import ProcessingStateManager
from shotgun.tui.utils.mode_progress import PlaceholderHints
from shotgun.tui.widgets.widget_coordinator import WidgetCoordinator
from shotgun.utils import get_shotgun_home
from shotgun.utils.marketing import MarketingManager

logger = logging.getLogger(__name__)


class ChatScreen(Screen[None]):
    CSS_PATH = "chat.tcss"

    BINDINGS = [
        ("ctrl+p", "command_palette", "Command Palette"),
        ("shift+tab", "toggle_mode", "Toggle mode"),
        ("ctrl+u", "show_usage", "Show usage"),
    ]

    COMMANDS = {
        UnifiedCommandProvider,
    }

    value = reactive("")
    mode = reactive(AgentType.RESEARCH)
    history: PromptHistory = PromptHistory()
    messages = reactive(list[ModelMessage | HintMessage]())
    indexing_job: reactive[CodebaseIndexSelection | None] = reactive(None)
    partial_message: reactive[ModelMessage | None] = reactive(None)

    # Q&A mode state (for structured output clarifying questions)
    qa_mode = reactive(False)
    qa_questions: list[str] = []
    qa_current_index = reactive(0)
    qa_answers: list[str] = []

    # Working state - keep reactive for Textual watchers
    working = reactive(False)

    def __init__(
        self,
        agent_manager: AgentManager,
        conversation_manager: ConversationManager,
        conversation_service: ConversationService,
        widget_coordinator: WidgetCoordinator,
        processing_state: ProcessingStateManager,
        command_handler: CommandHandler,
        placeholder_hints: PlaceholderHints,
        codebase_sdk: CodebaseSDK,
        deps: AgentDeps,
        continue_session: bool = False,
        force_reindex: bool = False,
    ) -> None:
        """Initialize the ChatScreen.

        All dependencies must be provided via dependency injection.
        No objects are created in the constructor.

        Args:
            agent_manager: AgentManager instance for managing agent interactions
            conversation_manager: ConversationManager for conversation persistence
            conversation_service: ConversationService for conversation save/load/restore
            widget_coordinator: WidgetCoordinator for centralized widget updates
            processing_state: ProcessingStateManager for managing processing state
            command_handler: CommandHandler for handling slash commands
            placeholder_hints: PlaceholderHints for providing input hints
            codebase_sdk: CodebaseSDK for codebase indexing operations
            deps: AgentDeps configuration for agent dependencies
            continue_session: Whether to continue a previous session
            force_reindex: Whether to force reindexing of codebases
        """
        super().__init__()

        # All dependencies are now required and injected
        self.deps = deps
        self.codebase_sdk = codebase_sdk
        self.agent_manager = agent_manager
        self.command_handler = command_handler
        self.placeholder_hints = placeholder_hints
        self.conversation_manager = conversation_manager
        self.conversation_service = conversation_service
        self.widget_coordinator = widget_coordinator
        self.processing_state = processing_state
        self.continue_session = continue_session
        self.force_reindex = force_reindex

    def on_mount(self) -> None:
        # Use widget coordinator to focus input
        self.widget_coordinator.update_prompt_input(focus=True)
        # Hide spinner initially
        self.query_one("#spinner").display = False

        # Bind spinner to processing state manager
        self.processing_state.bind_spinner(self.query_one("#spinner", Spinner))

        # Load conversation history if --continue flag was provided
        if self.continue_session and self.conversation_manager.exists():
            self._load_conversation()

        self.call_later(self.check_if_codebase_is_indexed)
        # Initial update of context indicator
        self.update_context_indicator()

    async def on_key(self, event: events.Key) -> None:
        """Handle key presses for cancellation."""
        # If escape is pressed during Q&A mode, exit Q&A
        if event.key in (Keys.Escape, Keys.ControlC) and self.qa_mode:
            self._exit_qa_mode()
            # Re-enable the input
            self.widget_coordinator.update_prompt_input(focus=True)
            # Prevent the event from propagating (don't quit the app)
            event.stop()
            return

        # If escape or ctrl+c is pressed while agent is working, cancel the operation
        if event.key in (Keys.Escape, Keys.ControlC):
            if self.processing_state.cancel_current_operation(cancel_key=event.key):
                # Show cancellation message
                self.mount_hint("⚠️ Cancelling operation...")
                # Re-enable the input
                self.widget_coordinator.update_prompt_input(focus=True)
                # Prevent the event from propagating (don't quit the app)
                event.stop()

    @work
    async def check_if_codebase_is_indexed(self) -> None:
        cur_dir = Path.cwd().resolve()
        is_empty = all(
            dir.is_dir() and dir.name in ["__pycache__", ".git", ".shotgun"]
            for dir in cur_dir.iterdir()
        )
        if is_empty or self.continue_session:
            return

        # If force_reindex is True, delete any existing graphs for this directory
        if self.force_reindex:
            accessible_graphs = (
                await self.codebase_sdk.list_codebases_for_directory()
            ).graphs
            for graph in accessible_graphs:
                try:
                    await self.codebase_sdk.delete_codebase(graph.graph_id)
                    logger.info(
                        f"Deleted existing graph {graph.graph_id} due to --force-reindex"
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to delete graph {graph.graph_id} during force reindex: {e}"
                    )

        # Check if the current directory has any accessible codebases
        accessible_graphs = (
            await self.codebase_sdk.list_codebases_for_directory()
        ).graphs
        if accessible_graphs:
            self.mount_hint(help_text_with_codebase(already_indexed=True))
            return

        # Ask user if they want to index the current directory
        should_index = await self.app.push_screen_wait(CodebaseIndexPromptScreen())
        if not should_index:
            self.mount_hint(help_text_empty_dir())
            return

        self.mount_hint(help_text_with_codebase(already_indexed=False))

        # Auto-index the current directory with its name
        cwd_name = cur_dir.name
        selection = CodebaseIndexSelection(repo_path=cur_dir, name=cwd_name)
        self.call_later(lambda: self.index_codebase(selection))

    def watch_mode(self, new_mode: AgentType) -> None:
        """React to mode changes by updating the agent manager."""

        if self.is_mounted:
            self.agent_manager.set_agent(new_mode)
            # Use widget coordinator for all widget updates
            self.widget_coordinator.update_for_mode_change(new_mode)

    def watch_working(self, is_working: bool) -> None:
        """Show or hide the spinner based on working state."""
        logger.debug(f"[WATCH] watch_working called - is_working={is_working}")
        if self.is_mounted:
            # Use widget coordinator for all widget updates
            self.widget_coordinator.update_for_processing_state(is_working)

    def watch_qa_mode(self, qa_mode_active: bool) -> None:
        """Update UI when Q&A mode state changes."""
        if self.is_mounted:
            # Use widget coordinator for all widget updates
            self.widget_coordinator.update_for_qa_mode(qa_mode_active)

    def watch_messages(self, messages: list[ModelMessage | HintMessage]) -> None:
        """Update the chat history when messages change."""
        if self.is_mounted:
            # Use widget coordinator for all widget updates
            self.widget_coordinator.update_messages(messages)

    def action_toggle_mode(self) -> None:
        # Prevent mode switching during Q&A
        if self.qa_mode:
            self.notify(
                "Cannot switch modes while answering questions",
                severity="warning",
                timeout=3,
            )
            return

        modes = [
            AgentType.RESEARCH,
            AgentType.SPECIFY,
            AgentType.PLAN,
            AgentType.TASKS,
            AgentType.EXPORT,
        ]
        self.mode = modes[(modes.index(self.mode) + 1) % len(modes)]
        self.agent_manager.set_agent(self.mode)
        # Re-focus input after mode change
        self.call_later(lambda: self.widget_coordinator.update_prompt_input(focus=True))

    def action_show_usage(self) -> None:
        usage_hint = self.agent_manager.get_usage_hint()
        logger.info(f"Usage hint: {usage_hint}")
        if usage_hint:
            self.mount_hint(usage_hint)
        else:
            self.notify("No usage hint available", severity="error")

    async def action_show_context(self) -> None:
        context_hint = await self.agent_manager.get_context_hint()
        if context_hint:
            self.mount_hint(context_hint)
        else:
            self.notify("No context analysis available", severity="error")

    @work
    async def action_compact_conversation(self) -> None:
        """Compact the conversation history to reduce size."""
        logger.debug(f"[COMPACT] Starting compaction - working={self.working}")

        try:
            # Show spinner and enable ESC cancellation
            from textual.worker import get_current_worker

            self.processing_state.start_processing("Compacting Conversation...")
            self.processing_state.bind_worker(get_current_worker())
            logger.debug(f"[COMPACT] Processing started - working={self.working}")

            # Get current message count and tokens
            original_count = len(self.agent_manager.message_history)
            original_tokens = await estimate_tokens_from_messages(
                self.agent_manager.message_history, self.deps.llm_model
            )

            # Log compaction start
            logger.info(
                f"Starting conversation compaction - {original_count} messages, {original_tokens} tokens"
            )

            # Post compaction started event
            self.agent_manager.post_message(CompactionStartedMessage())
            logger.debug("[COMPACT] Posted CompactionStartedMessage")

            # Apply compaction with force=True to bypass threshold checks
            compacted_messages = await apply_persistent_compaction(
                self.agent_manager.message_history, self.deps, force=True
            )

            logger.debug(
                f"[COMPACT] Compacted messages: count={len(compacted_messages)}, "
                f"last_message_type={type(compacted_messages[-1]).__name__ if compacted_messages else 'None'}"
            )

            # Check last response usage
            last_response = next(
                (
                    msg
                    for msg in reversed(compacted_messages)
                    if isinstance(msg, ModelResponse)
                ),
                None,
            )
            if last_response:
                logger.debug(
                    f"[COMPACT] Last response has usage: {last_response.usage is not None}, "
                    f"usage={last_response.usage if last_response.usage else 'None'}"
                )
            else:
                logger.warning(
                    "[COMPACT] No ModelResponse found in compacted messages!"
                )

            # Update agent manager's message history
            self.agent_manager.message_history = compacted_messages
            logger.debug("[COMPACT] Updated agent_manager.message_history")

            # Calculate after metrics
            compacted_count = len(compacted_messages)
            compacted_tokens = await estimate_tokens_from_messages(
                compacted_messages, self.deps.llm_model
            )

            # Calculate reductions
            message_reduction = (
                ((original_count - compacted_count) / original_count) * 100
                if original_count > 0
                else 0
            )
            token_reduction = (
                ((original_tokens - compacted_tokens) / original_tokens) * 100
                if original_tokens > 0
                else 0
            )

            # Save to conversation file
            conversation_file = get_shotgun_home() / "conversation.json"
            manager = ConversationManager(conversation_file)
            conversation = await manager.load()

            if conversation:
                conversation.set_agent_messages(compacted_messages)
                await manager.save(conversation)

            # Post compaction completed event
            self.agent_manager.post_message(CompactionCompletedMessage())

            # Post message history updated event
            self.agent_manager.post_message(
                MessageHistoryUpdated(
                    messages=self.agent_manager.ui_message_history.copy(),
                    agent_type=self.agent_manager._current_agent_type,
                    file_operations=None,
                )
            )
            logger.debug("[COMPACT] Posted MessageHistoryUpdated event")

            # Force immediate context indicator update
            logger.debug("[COMPACT] Calling update_context_indicator()")
            self.update_context_indicator()

            # Log compaction completion
            logger.info(
                f"Compaction completed: {original_count} → {compacted_count} messages "
                f"({message_reduction:.0f}% message reduction, {token_reduction:.0f}% token reduction)"
            )

            # Add persistent hint message with stats
            self.mount_hint(
                f"✓ Compacted conversation: {original_count} → {compacted_count} messages "
                f"({message_reduction:.0f}% message reduction, {token_reduction:.0f}% token reduction)"
            )

        except Exception as e:
            logger.error(f"Failed to compact conversation: {e}", exc_info=True)
            self.notify(f"Failed to compact: {e}", severity="error")
        finally:
            # Hide spinner
            self.processing_state.stop_processing()
            logger.debug(f"[COMPACT] Processing stopped - working={self.working}")

    @work
    async def action_clear_conversation(self) -> None:
        """Clear the conversation history."""
        # Show confirmation dialog
        should_clear = await self.app.push_screen_wait(
            ConfirmationDialog(
                title="Clear conversation?",
                message="This will permanently delete your entire conversation history. "
                "All messages, context, and progress will be lost. "
                "This action cannot be undone.",
                confirm_label="Clear",
                cancel_label="Keep",
                confirm_variant="warning",
                danger=True,
            )
        )

        if not should_clear:
            return  # User cancelled

        try:
            # Clear message histories
            self.agent_manager.message_history = []
            self.agent_manager.ui_message_history = []

            # Use conversation service to clear conversation
            self.conversation_service.clear_conversation()

            # Post message history updated event to refresh UI
            self.agent_manager.post_message(
                MessageHistoryUpdated(
                    messages=[],
                    agent_type=self.agent_manager._current_agent_type,
                    file_operations=None,
                )
            )

            # Show persistent success message
            self.mount_hint("✓ Conversation cleared - Starting fresh!")

        except Exception as e:
            logger.error(f"Failed to clear conversation: {e}", exc_info=True)
            self.notify(f"Failed to clear: {e}", severity="error")

    @work(exclusive=False)
    async def update_context_indicator(self) -> None:
        """Update the context indicator with current usage data."""
        logger.debug("[CONTEXT] update_context_indicator called")
        try:
            logger.debug(
                f"[CONTEXT] Getting context analysis - "
                f"message_history_count={len(self.agent_manager.message_history)}"
            )
            analysis = await self.agent_manager.get_context_analysis()

            if analysis:
                logger.debug(
                    f"[CONTEXT] Analysis received - "
                    f"agent_context_tokens={analysis.agent_context_tokens}, "
                    f"max_usable_tokens={analysis.max_usable_tokens}, "
                    f"percentage={round((analysis.agent_context_tokens / analysis.max_usable_tokens) * 100, 1) if analysis.max_usable_tokens > 0 else 0}%"
                )
            else:
                logger.warning("[CONTEXT] Analysis is None!")

            model_name = self.deps.llm_model.name
            # Use widget coordinator for context indicator update
            self.widget_coordinator.update_context_indicator(analysis, model_name)
        except Exception as e:
            logger.error(
                f"[CONTEXT] Failed to update context indicator: {e}", exc_info=True
            )

    @work(exclusive=False)
    async def update_context_indicator_with_messages(
        self,
        agent_messages: list[ModelMessage],
        ui_messages: list[ModelMessage | HintMessage],
    ) -> None:
        """Update the context indicator with specific message sets (for streaming updates).

        Args:
            agent_messages: Agent message history including streaming messages (for token counting)
            ui_messages: UI message history including hints and streaming messages
        """
        try:
            from shotgun.agents.context_analyzer.analyzer import ContextAnalyzer

            analyzer = ContextAnalyzer(self.deps.llm_model)
            # Analyze the combined message histories for accurate progressive token counts
            analysis = await analyzer.analyze_conversation(agent_messages, ui_messages)

            if analysis:
                model_name = self.deps.llm_model.name
                self.widget_coordinator.update_context_indicator(analysis, model_name)
        except Exception as e:
            logger.error(
                f"Failed to update context indicator with streaming messages: {e}",
                exc_info=True,
            )

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        with Container(id="window"):
            yield self.agent_manager
            yield ChatHistory()
            with Container(id="footer"):
                yield Spinner(
                    text="Processing...",
                    id="spinner",
                    classes="" if self.working else "hidden",
                )
                yield StatusBar(working=self.working)
                yield PromptInput(
                    text=self.value,
                    highlight_cursor_line=False,
                    id="prompt-input",
                    placeholder=self._placeholder_for_mode(self.mode),
                )
                with Grid():
                    yield ModeIndicator(mode=self.mode)
                    with Container(id="right-footer-indicators"):
                        yield ContextIndicator(id="context-indicator")
                        yield Static("", id="indexing-job-display")

    def mount_hint(self, markdown: str) -> None:
        hint = HintMessage(message=markdown)
        self.agent_manager.add_hint_message(hint)

    @on(PartialResponseMessage)
    def handle_partial_response(self, event: PartialResponseMessage) -> None:
        self.partial_message = event.message

        # Filter event.messages to exclude ModelRequest with only ToolReturnPart
        # These are intermediate tool results that would render as empty (UserQuestionWidget
        # filters out ToolReturnPart in format_prompt_parts), causing user messages to disappear
        filtered_event_messages: list[ModelMessage] = []
        for msg in event.messages:
            if isinstance(msg, ModelRequest):
                # Check if this ModelRequest has any user-visible parts
                has_user_content = any(
                    not isinstance(part, ToolReturnPart) for part in msg.parts
                )
                if has_user_content:
                    filtered_event_messages.append(msg)
                # Skip ModelRequest with only ToolReturnPart
            else:
                # Keep all ModelResponse and other message types
                filtered_event_messages.append(msg)

        # Build new message list combining existing messages with new streaming content
        new_message_list = self.messages + cast(
            list[ModelMessage | HintMessage], filtered_event_messages
        )

        # Use widget coordinator to set partial response
        self.widget_coordinator.set_partial_response(
            self.partial_message, new_message_list
        )

        # Update context indicator with full message history including streaming messages
        # Combine existing agent history with new streaming messages for accurate token count
        combined_agent_history = self.agent_manager.message_history + event.messages
        self.update_context_indicator_with_messages(
            combined_agent_history, new_message_list
        )

    def _clear_partial_response(self) -> None:
        # Use widget coordinator to clear partial response
        self.widget_coordinator.set_partial_response(None, self.messages)

    def _exit_qa_mode(self) -> None:
        """Exit Q&A mode and clean up state."""
        # Track cancellation event
        track_event(
            "qa_mode_cancelled",
            {
                "questions_total": len(self.qa_questions),
                "questions_answered": len(self.qa_answers),
            },
        )

        # Clear Q&A state
        self.qa_mode = False
        self.qa_questions = []
        self.qa_answers = []
        self.qa_current_index = 0

        # Show cancellation message
        self.mount_hint("⚠️ Q&A cancelled - You can continue the conversation.")

    @on(ClarifyingQuestionsMessage)
    def handle_clarifying_questions(self, event: ClarifyingQuestionsMessage) -> None:
        """Handle clarifying questions from agent structured output.

        Note: Hints are now added synchronously in agent_manager.run() before this
        handler is called, so we only need to set up Q&A mode state here.
        """
        # Clear any streaming partial response (removes final_result JSON)
        self._clear_partial_response()

        # Enter Q&A mode
        self.qa_mode = True
        self.qa_questions = event.questions
        self.qa_current_index = 0
        self.qa_answers = []

    @on(MessageHistoryUpdated)
    async def handle_message_history_updated(
        self, event: MessageHistoryUpdated
    ) -> None:
        """Handle message history updates from the agent manager."""
        self._clear_partial_response()
        self.messages = event.messages

        # Use widget coordinator to refresh placeholder and mode indicator
        self.widget_coordinator.update_prompt_input(
            placeholder=self._placeholder_for_mode(self.mode)
        )
        self.widget_coordinator.refresh_mode_indicator()

        # Update context indicator
        self.update_context_indicator()

        # If there are file operations, add a message showing the modified files
        if event.file_operations:
            chat_history = self.query_one(ChatHistory)
            if chat_history.vertical_tail:
                tracker = FileOperationTracker(operations=event.file_operations)
                display_path = tracker.get_display_path()

                if display_path:
                    # Create a simple markdown message with the file path
                    # The terminal emulator will make this clickable automatically
                    path_obj = Path(display_path)

                    if len(event.file_operations) == 1:
                        message = f"📝 Modified: `{display_path}`"
                    else:
                        num_files = len({op.file_path for op in event.file_operations})
                        if path_obj.is_dir():
                            message = (
                                f"📁 Modified {num_files} files in: `{display_path}`"
                            )
                        else:
                            # Common path is a file, show parent directory
                            message = (
                                f"📁 Modified {num_files} files in: `{path_obj.parent}`"
                            )

                    self.mount_hint(message)

                    # Check and display any marketing messages
                    from shotgun.tui.app import ShotgunApp

                    app = cast(ShotgunApp, self.app)
                    await MarketingManager.check_and_display_messages(
                        app.config_manager, event.file_operations, self.mount_hint
                    )

    @on(CompactionStartedMessage)
    def handle_compaction_started(self, event: CompactionStartedMessage) -> None:
        """Update spinner text when compaction starts."""
        # Use widget coordinator to update spinner text
        self.widget_coordinator.update_spinner_text("Compacting Conversation...")

    @on(CompactionCompletedMessage)
    def handle_compaction_completed(self, event: CompactionCompletedMessage) -> None:
        """Reset spinner text when compaction completes."""
        # Use widget coordinator to update spinner text
        self.widget_coordinator.update_spinner_text("Processing...")

    async def handle_model_selected(self, result: ModelConfigUpdated | None) -> None:
        """Handle model selection from ModelPickerScreen.

        Called as a callback when the ModelPickerScreen is dismissed.

        Args:
            result: ModelConfigUpdated if a model was selected, None if cancelled
        """
        if result is None:
            return

        try:
            # Update the model configuration in dependencies
            self.deps.llm_model = result.model_config

            # Update the agent manager's model configuration
            self.agent_manager.deps.llm_model = result.model_config

            # Get current analysis and update context indicator via coordinator
            analysis = await self.agent_manager.get_context_analysis()
            self.widget_coordinator.update_context_indicator(analysis, result.new_model)

            # Get model display name for user feedback
            model_spec = MODEL_SPECS.get(result.new_model)
            model_display = (
                model_spec.short_name if model_spec else str(result.new_model)
            )

            # Format provider information
            key_method = (
                "Shotgun Account" if result.key_provider == "shotgun" else "BYOK"
            )
            provider_display = result.provider.value.title()

            # Track model switch in telemetry
            track_event(
                "model_switched",
                {
                    "old_model": str(result.old_model) if result.old_model else None,
                    "new_model": str(result.new_model),
                    "provider": result.provider.value,
                    "key_provider": result.key_provider.value,
                },
            )

            # Show confirmation to user with provider info
            self.agent_manager.add_hint_message(
                HintMessage(
                    message=f"✓ Switched to {model_display} ({provider_display}, {key_method})"
                )
            )

        except Exception as e:
            logger.error(f"Failed to handle model selection: {e}")
            self.agent_manager.add_hint_message(
                HintMessage(message=f"⚠ Failed to update model configuration: {e}")
            )

    @on(PromptInput.Submitted)
    async def handle_submit(self, message: PromptInput.Submitted) -> None:
        text = message.text.strip()

        # If empty text, just clear input and return
        if not text:
            self.widget_coordinator.update_prompt_input(clear=True)
            self.value = ""
            return

        # Handle Q&A mode (from structured output clarifying questions)
        if self.qa_mode and self.qa_questions:
            # Collect answer
            self.qa_answers.append(text)

            # Show answer
            if len(self.qa_questions) == 1:
                self.agent_manager.add_hint_message(
                    HintMessage(message=f"**A:** {text}")
                )
            else:
                q_num = self.qa_current_index + 1
                self.agent_manager.add_hint_message(
                    HintMessage(message=f"**A{q_num}:** {text}")
                )

            # Move to next or finish
            self.qa_current_index += 1

            if self.qa_current_index < len(self.qa_questions):
                # Show next question
                next_q = self.qa_questions[self.qa_current_index]
                next_q_num = self.qa_current_index + 1
                self.agent_manager.add_hint_message(
                    HintMessage(message=f"**Q{next_q_num}:** {next_q}")
                )
            else:
                # All answered - format and send back
                if len(self.qa_questions) == 1:
                    # Single question - just send the answer
                    formatted_qa = f"Q: {self.qa_questions[0]}\nA: {self.qa_answers[0]}"
                else:
                    # Multiple questions - format all Q&A pairs
                    formatted_qa = "\n\n".join(
                        f"Q{i + 1}: {q}\nA{i + 1}: {a}"
                        for i, (q, a) in enumerate(
                            zip(self.qa_questions, self.qa_answers, strict=True)
                        )
                    )

                # Exit Q&A mode
                self.qa_mode = False
                self.qa_questions = []
                self.qa_answers = []
                self.qa_current_index = 0

                # Send answers back to agent
                self.run_agent(formatted_qa)

            # Clear input
            self.widget_coordinator.update_prompt_input(clear=True)
            self.value = ""
            return

        # Check if it's a command
        if self.command_handler.is_command(text):
            success, response = self.command_handler.handle_command(text)

            # Add the command to history
            self.history.append(message.text)

            # Display the command in chat history
            user_message = ModelRequest(parts=[UserPromptPart(content=text)])
            self.messages = self.messages + [user_message]

            # Display the response (help text or error message)
            response_message = ModelResponse(parts=[TextPart(content=response)])
            self.messages = self.messages + [response_message]

            # Clear the input
            self.widget_coordinator.update_prompt_input(clear=True)
            self.value = ""
            return

        # Not a command, process as normal
        self.history.append(message.text)

        # Add user message to agent_manager's history BEFORE running the agent
        # This ensures immediate visual feedback AND proper deduplication
        user_message = ModelRequest.user_text_prompt(text)
        self.agent_manager.ui_message_history.append(user_message)
        self.messages = self.agent_manager.ui_message_history.copy()

        # Clear the input
        self.value = ""
        self.run_agent(text)  # Use stripped text

        self.widget_coordinator.update_prompt_input(clear=True)

    def _placeholder_for_mode(self, mode: AgentType, force_new: bool = False) -> str:
        """Return the placeholder text appropriate for the current mode.

        Args:
            mode: The current agent mode.
            force_new: If True, force selection of a new random hint.

        Returns:
            Dynamic placeholder hint based on mode and progress.
        """
        return self.placeholder_hints.get_placeholder_for_mode(mode)

    def index_codebase_command(self) -> None:
        # Simplified: always index current working directory with its name
        cur_dir = Path.cwd().resolve()
        cwd_name = cur_dir.name
        selection = CodebaseIndexSelection(repo_path=cur_dir, name=cwd_name)
        self.call_later(lambda: self.index_codebase(selection))

    def delete_codebase_command(self) -> None:
        self.app.push_screen(
            CommandPalette(
                providers=[DeleteCodebasePaletteProvider],
                placeholder="Select a codebase to delete…",
            )
        )

    def delete_codebase_from_palette(self, graph_id: str) -> None:
        stack = getattr(self.app, "screen_stack", None)
        if stack and isinstance(stack[-1], CommandPalette):
            self.app.pop_screen()

        self.call_later(lambda: self.delete_codebase(graph_id))

    @work
    async def delete_codebase(self, graph_id: str) -> None:
        try:
            await self.codebase_sdk.delete_codebase(graph_id)
            self.notify(f"Deleted codebase: {graph_id}", severity="information")
        except CodebaseNotFoundError as exc:
            self.notify(str(exc), severity="error")
        except Exception as exc:  # pragma: no cover - defensive UI path
            self.notify(f"Failed to delete codebase: {exc}", severity="error")

    def _is_kuzu_corruption_error(self, exception: Exception) -> bool:
        """Check if error is related to kuzu database corruption.

        Args:
            exception: The exception to check

        Returns:
            True if the error indicates kuzu database corruption
        """
        error_str = str(exception).lower()
        error_indicators = [
            "not a directory",
            "errno 20",
            "corrupted",
            ".kuzu",
            "ioexception",
            "unordered_map",  # C++ STL map errors from kuzu
            "key not found",  # unordered_map::at errors
            "std::exception",  # Generic C++ exceptions from kuzu
        ]
        return any(indicator in error_str for indicator in error_indicators)

    @work
    async def index_codebase(self, selection: CodebaseIndexSelection) -> None:
        label = self.query_one("#indexing-job-display", Static)
        label.update(
            f"[$foreground-muted]Indexing codebase: [bold $text-accent]{selection.name}[/][/]"
        )
        label.refresh()

        def create_progress_bar(percentage: float, width: int = 20) -> str:
            """Create a visual progress bar using Unicode block characters."""
            filled = int((percentage / 100) * width)
            empty = width - filled
            return "▓" * filled + "░" * empty

        # Spinner animation frames
        spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

        # Progress state (shared between timer and progress callback)
        progress_state: dict[str, int | float] = {
            "frame_index": 0,
            "percentage": 0.0,
        }

        def update_progress_display() -> None:
            """Update progress bar on timer - runs every 100ms."""
            # Advance spinner frame
            frame_idx = int(progress_state["frame_index"])
            progress_state["frame_index"] = (frame_idx + 1) % len(spinner_frames)
            spinner = spinner_frames[frame_idx]

            # Get current state
            pct = float(progress_state["percentage"])
            bar = create_progress_bar(pct)

            # Update label
            label.update(
                f"[$foreground-muted]Indexing codebase: {spinner} {bar} {pct:.0f}%[/]"
            )

        def progress_callback(progress_info: IndexProgress) -> None:
            """Update progress state (timer renders it independently)."""
            # Calculate overall percentage (0-95%, reserve 95-100% for finalization)
            if progress_info.phase == ProgressPhase.STRUCTURE:
                # Phase 1: 0-10%, always show 5% while running, 10% when complete
                overall_pct = 10.0 if progress_info.phase_complete else 5.0
            elif progress_info.phase == ProgressPhase.DEFINITIONS:
                # Phase 2: 10-80% based on files processed
                if progress_info.total and progress_info.total > 0:
                    phase_pct = (progress_info.current / progress_info.total) * 70.0
                    overall_pct = 10.0 + phase_pct
                else:
                    overall_pct = 10.0
            elif progress_info.phase == ProgressPhase.RELATIONSHIPS:
                # Phase 3: 80-95% based on relationships processed (cap at 95%)
                if progress_info.total and progress_info.total > 0:
                    phase_pct = (progress_info.current / progress_info.total) * 15.0
                    overall_pct = 80.0 + phase_pct
                else:
                    overall_pct = 80.0
            else:
                overall_pct = 0.0

            # Update shared state (timer will render it)
            progress_state["percentage"] = overall_pct

        # Start progress animation timer (10 fps = 100ms interval)
        progress_timer = self.set_interval(0.1, update_progress_display)

        # Retry logic for handling kuzu corruption
        max_retries = 3

        for attempt in range(max_retries):
            try:
                # Clean up corrupted DBs before retry (skip on first attempt)
                if attempt > 0:
                    logger.info(
                        f"Retry attempt {attempt + 1}/{max_retries} - cleaning up corrupted databases"
                    )
                    manager = CodebaseGraphManager(
                        self.codebase_sdk.service.storage_dir
                    )
                    cleaned = await manager.cleanup_corrupted_databases()
                    logger.info(f"Cleaned up {len(cleaned)} corrupted database(s)")
                    self.notify(
                        f"Retrying indexing after cleanup (attempt {attempt + 1}/{max_retries})...",
                        severity="information",
                    )

                # Pass the current working directory as the indexed_from_cwd
                logger.debug(
                    f"Starting indexing - repo_path: {selection.repo_path}, "
                    f"name: {selection.name}, cwd: {Path.cwd().resolve()}"
                )
                result = await self.codebase_sdk.index_codebase(
                    selection.repo_path,
                    selection.name,
                    indexed_from_cwd=str(Path.cwd().resolve()),
                    progress_callback=progress_callback,
                )

                # Success! Stop progress animation
                progress_timer.stop()

                # Show 100% completion after indexing finishes
                final_bar = create_progress_bar(100.0)
                label.update(
                    f"[$foreground-muted]Indexing codebase: {final_bar} 100%[/]"
                )
                label.refresh()

                logger.info(
                    f"Successfully indexed codebase '{result.name}' (ID: {result.graph_id})"
                )
                self.notify(
                    f"Indexed codebase '{result.name}' (ID: {result.graph_id})",
                    severity="information",
                    timeout=8,
                )
                break  # Success - exit retry loop

            except CodebaseAlreadyIndexedError as exc:
                progress_timer.stop()
                logger.warning(f"Codebase already indexed: {exc}")
                self.notify(str(exc), severity="warning")
                return
            except InvalidPathError as exc:
                progress_timer.stop()
                logger.error(f"Invalid path error: {exc}")
                self.notify(str(exc), severity="error")
                return

            except Exception as exc:  # pragma: no cover - defensive UI path
                # Check if this is a kuzu corruption error and we have retries left
                if attempt < max_retries - 1 and self._is_kuzu_corruption_error(exc):
                    logger.warning(
                        f"Kuzu corruption detected on attempt {attempt + 1}/{max_retries}: {exc}. "
                        f"Will retry after cleanup..."
                    )
                    # Exponential backoff: 1s, 2s
                    await asyncio.sleep(2**attempt)
                    continue

                # Either final retry failed OR not a corruption error - show error
                logger.exception(
                    f"Failed to index codebase after {attempt + 1} attempts - "
                    f"repo_path: {selection.repo_path}, name: {selection.name}, error: {exc}"
                )
                self.notify(
                    f"Failed to index codebase after {attempt + 1} attempts: {exc}",
                    severity="error",
                    timeout=30,  # Keep error visible for 30 seconds
                )
                break

        # Always stop the progress timer and clean up label
        progress_timer.stop()
        label.update("")
        label.refresh()

    @work
    async def run_agent(self, message: str) -> None:
        prompt = None

        # Start processing with spinner
        from textual.worker import get_current_worker

        self.processing_state.start_processing("Processing...")
        self.processing_state.bind_worker(get_current_worker())

        # Start context indicator animation immediately
        self.widget_coordinator.set_context_streaming(True)

        prompt = message

        try:
            await self.agent_manager.run(
                prompt=prompt,
            )
        except asyncio.CancelledError:
            # Handle cancellation gracefully - DO NOT re-raise
            self.mount_hint("⚠️ Operation cancelled by user")
        except Exception as e:
            # Log with full stack trace to shotgun.log
            logger.exception(
                "Agent run failed",
                extra={
                    "agent_mode": self.mode.value,
                    "error_type": type(e).__name__,
                },
            )

            # Determine user-friendly message based on error type
            error_name = type(e).__name__
            error_message = str(e)

            if "APIStatusError" in error_name and "overload" in error_message.lower():
                hint = "⚠️ The AI service is temporarily overloaded. Please wait a moment and try again."
            elif "APIStatusError" in error_name and "rate" in error_message.lower():
                hint = "⚠️ Rate limit reached. Please wait before trying again."
            elif "APIStatusError" in error_name:
                hint = f"⚠️ AI service error: {error_message}"
            else:
                hint = f"⚠️ An error occurred: {error_message}\n\nCheck logs at ~/.shotgun-sh/logs/shotgun.log"

            self.mount_hint(hint)
        finally:
            self.processing_state.stop_processing()
            # Stop context indicator animation
            self.widget_coordinator.set_context_streaming(False)

        # Save conversation after each interaction
        self._save_conversation()

        self.widget_coordinator.update_prompt_input(focus=True)

    def _save_conversation(self) -> None:
        """Save the current conversation to persistent storage."""
        # Use conversation service for saving (run async in background)
        self.run_worker(
            self.conversation_service.save_conversation(self.agent_manager),
            exclusive=False,
        )

    def _load_conversation(self) -> None:
        """Load conversation from persistent storage."""

        # Use conversation service for restoration (run async)
        async def _do_load() -> None:
            (
                success,
                error_msg,
                restored_type,
            ) = await self.conversation_service.restore_conversation(
                self.agent_manager, self.deps.usage_manager
            )

            if not success and error_msg:
                self.mount_hint(error_msg)
            elif success and restored_type:
                # Update the current mode to match restored conversation
                self.mode = restored_type

        self.run_worker(_do_load(), exclusive=False)
