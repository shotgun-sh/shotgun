"""Main chat screen implementation."""

import asyncio
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from shotgun.agents.router.models import ExecutionStep

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
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
    ToolExecutionStartedMessage,
    ToolStreamingProgressMessage,
)
from shotgun.agents.config.models import MODEL_SPECS
from shotgun.agents.conversation import ConversationManager
from shotgun.agents.conversation.history.compaction import apply_persistent_compaction
from shotgun.agents.conversation.history.token_estimation import (
    estimate_tokens_from_messages,
)
from shotgun.agents.models import (
    AgentDeps,
    AgentType,
    FileOperationTracker,
)
from shotgun.agents.router.models import (
    CascadeScope,
    ExecutionPlan,
    PlanApprovalStatus,
    RouterDeps,
    RouterMode,
)
from shotgun.agents.runner import AgentRunner
from shotgun.codebase.core.errors import (
    DatabaseIssue,
    KuzuErrorType,
    classify_kuzu_error,
)
from shotgun.codebase.core.kuzu_compat import KuzuImportError
from shotgun.codebase.core.manager import (
    CodebaseAlreadyIndexedError,
    CodebaseGraphManager,
)
from shotgun.codebase.models import IndexProgress, ProgressPhase
from shotgun.exceptions import (
    SHOTGUN_CONTACT_EMAIL,
    ErrorNotPickedUpBySentry,
    ShotgunAccountException,
)
from shotgun.posthog_telemetry import track_event
from shotgun.sdk.codebase import CodebaseSDK
from shotgun.sdk.exceptions import CodebaseNotFoundError, InvalidPathError
from shotgun.tui.commands import CommandHandler
from shotgun.tui.components.context_indicator import ContextIndicator
from shotgun.tui.components.mode_indicator import ModeIndicator
from shotgun.tui.components.prompt_input import PromptInput
from shotgun.tui.components.spinner import Spinner
from shotgun.tui.components.status_bar import StatusBar

# TUIErrorHandler removed - exceptions now caught directly
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
from shotgun.tui.screens.chat_screen.messages import (
    CascadeConfirmationRequired,
    CascadeConfirmed,
    CascadeDeclined,
    CheckpointContinue,
    CheckpointModify,
    CheckpointStop,
    PlanApprovalRequired,
    PlanApproved,
    PlanPanelClosed,
    PlanRejected,
    PlanUpdated,
    StepCompleted,
    SubAgentCompleted,
    SubAgentStarted,
)
from shotgun.tui.screens.confirmation_dialog import ConfirmationDialog
from shotgun.tui.screens.database_locked_dialog import DatabaseLockedDialog
from shotgun.tui.screens.database_timeout_dialog import DatabaseTimeoutDialog
from shotgun.tui.screens.kuzu_error_dialog import KuzuErrorDialog
from shotgun.tui.screens.shared_specs import (
    CreateSpecDialog,
    ShareSpecsAction,
    ShareSpecsDialog,
    UploadProgressScreen,
)
from shotgun.tui.services.conversation_service import ConversationService
from shotgun.tui.state.processing_state import ProcessingStateManager
from shotgun.tui.utils.mode_progress import PlaceholderHints
from shotgun.tui.widgets.approval_widget import PlanApprovalWidget
from shotgun.tui.widgets.cascade_confirmation_widget import CascadeConfirmationWidget
from shotgun.tui.widgets.plan_panel import PlanPanelWidget
from shotgun.tui.widgets.step_checkpoint_widget import StepCheckpointWidget
from shotgun.tui.widgets.widget_coordinator import WidgetCoordinator
from shotgun.utils import get_shotgun_home
from shotgun.utils.file_system_utils import get_shotgun_base_path
from shotgun.utils.marketing import MarketingManager

logger = logging.getLogger(__name__)


def _format_duration(seconds: float) -> str:
    """Format duration in natural language."""
    if seconds < 60:
        return f"{int(seconds)} seconds"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    if secs == 0:
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    return f"{minutes} minute{'s' if minutes != 1 else ''} {secs} seconds"


def _format_count(count: int) -> str:
    """Format count in natural language (e.g., '5 thousand')."""
    if count < 1000:
        return str(count)
    elif count < 1_000_000:
        thousands = count / 1000
        if thousands == int(thousands):
            return f"{int(thousands)} thousand"
        return f"{thousands:.1f} thousand"
    else:
        millions = count / 1_000_000
        if millions == int(millions):
            return f"{int(millions)} million"
        return f"{millions:.1f} million"


class ChatScreen(Screen[None]):
    CSS_PATH = "chat.tcss"

    BINDINGS = [
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

    # Q&A mode state (for structured output clarifying questions)
    qa_mode = reactive(False)
    qa_questions: list[str] = []
    qa_current_index = reactive(0)
    qa_answers: list[str] = []

    # Working state - keep reactive for Textual watchers
    working = reactive(False)

    # Throttle context indicator updates (in seconds)
    _last_context_update: float = 0.0
    _context_update_throttle: float = 5.0  # 5 seconds

    # Step checkpoint widget (Planning mode)
    _checkpoint_widget: StepCheckpointWidget | None = None

    # Cascade confirmation widget (Planning mode)
    _cascade_widget: CascadeConfirmationWidget | None = None

    # Plan approval widget (Planning mode)
    _approval_widget: PlanApprovalWidget | None = None

    # Plan panel widget (Stage 11)
    _plan_panel: PlanPanelWidget | None = None

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
        show_pull_hint: bool = False,
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
            show_pull_hint: Whether to show hint about recently pulled spec
        """
        super().__init__()

        # All dependencies are now required and injected
        self.deps = deps

        # Wire up plan change callback for Plan Panel (Stage 11)
        if isinstance(deps, RouterDeps):
            deps.on_plan_changed = self._on_plan_changed

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
        self.show_pull_hint = show_pull_hint

        # Initialize mode from agent_manager before compose() runs
        # This ensures ModeIndicator shows correct mode on first render
        self.mode = agent_manager._current_agent_type

    def on_mount(self) -> None:
        # Use widget coordinator to focus input
        self.widget_coordinator.update_prompt_input(focus=True)
        # Hide spinner initially
        self.query_one("#spinner").display = False

        # Bind spinner to processing state manager
        self.processing_state.bind_spinner(self.query_one("#spinner", Spinner))

        # Load conversation history if --continue flag was provided
        # Use call_later to handle async exists() check
        if self.continue_session:
            self.call_later(self._check_and_load_conversation)

        # Show pull hint if launching after spec pull
        if self.show_pull_hint:
            self.call_later(self._show_pull_hint)

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

    async def _handle_pending_database_issues(self) -> bool:
        """Handle any database issues detected at startup.

        This method processes pending database issues (locked, corrupted, timeout)
        and shows appropriate dialogs to the user.

        Returns:
            True if should continue with normal startup, False if should abort
        """
        from shotgun.codebase.core.manager import CodebaseGraphManager
        from shotgun.utils import get_shotgun_home

        # Get pending issues from app
        pending_issues: list[DatabaseIssue] = getattr(self.app, "pending_db_issues", [])
        if not pending_issues:
            return True

        storage_dir = get_shotgun_home() / "codebases"
        manager = CodebaseGraphManager(storage_dir)

        # Handle locked databases first - show ONE dialog for all locked DBs
        locked_issues = [
            i for i in pending_issues if i.error_type == KuzuErrorType.LOCKED
        ]
        if locked_issues:
            # Show single locked dialog
            retry = await self.app.push_screen_wait(DatabaseLockedDialog())
            if not retry:
                # User cancelled - exit the app gracefully
                await self.app.action_quit()
                return False

            # User wants to retry - re-detect to see if locks are cleared
            new_issues = await manager.detect_database_issues(timeout_seconds=10.0)
            still_locked = [
                i for i in new_issues if i.error_type == KuzuErrorType.LOCKED
            ]
            if still_locked:
                # Still locked - show hint message
                self.agent_manager.add_hint_message(
                    HintMessage(
                        message="Database is still locked. "
                        "Please close the other shotgun instance and restart."
                    )
                )
                await self.app.action_quit()
                return False

        # Process non-locked issues
        for issue in pending_issues:
            if issue.error_type == KuzuErrorType.LOCKED:
                continue  # Already handled above

            if issue.error_type == KuzuErrorType.TIMEOUT:
                # Show timeout dialog
                action = await self.app.push_screen_wait(
                    DatabaseTimeoutDialog(
                        codebase_name=issue.graph_id,
                        timeout_seconds=10.0,
                    )
                )
                if action == "retry":
                    # Retry with longer timeout (90s)
                    new_issues = await manager.detect_database_issues(
                        timeout_seconds=90.0
                    )
                    still_timeout = any(
                        i.graph_id == issue.graph_id
                        and i.error_type == KuzuErrorType.TIMEOUT
                        for i in new_issues
                    )
                    if still_timeout:
                        self.agent_manager.add_hint_message(
                            HintMessage(
                                message=f"Database '{issue.graph_id}' still not responding. "
                                "It may be corrupted or the codebase is extremely large."
                            )
                        )
                elif action == "skip":
                    # User chose to skip this database
                    logger.info(f"User skipped timeout database: {issue.graph_id}")
                # "cancel" - do nothing

            elif issue.error_type == KuzuErrorType.CORRUPTION:
                # Show corruption confirmation dialog
                should_delete = await self.app.push_screen_wait(
                    ConfirmationDialog(
                        title="Database Corrupted",
                        message=(
                            f"The codebase index '{issue.graph_id}' appears to be corrupted.\n\n"
                            f"Error: {issue.message}\n\n"
                            "Would you like to delete it? You will need to re-index the codebase."
                        ),
                        confirm_label="Delete & Re-index",
                        cancel_label="Keep (Skip)",
                        confirm_variant="warning",
                        danger=True,
                    )
                )
                if should_delete:
                    deleted = await manager.delete_database(issue.graph_id)
                    if deleted:
                        self.agent_manager.add_hint_message(
                            HintMessage(
                                message=f"Deleted corrupted database '{issue.graph_id}'. "
                                "You can re-index using /index."
                            )
                        )
                    else:
                        logger.error(
                            f"Failed to delete corrupted database: {issue.graph_id}"
                        )

        # Clear the pending issues after processing
        if hasattr(self.app, "pending_db_issues"):
            self.app.pending_db_issues = []

        return True

    @work
    async def check_if_codebase_is_indexed(self) -> None:
        # Handle any pending database issues from startup first
        should_continue = await self._handle_pending_database_issues()
        if not should_continue:
            return

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

    # =========================================================================
    # Router State Properties (for Protocol compliance)
    # =========================================================================

    @property
    def router_mode(self) -> str | None:
        """Get the current router mode for RouterModeProvider protocol.

        Returns:
            'planning' or 'drafting' if using router agent, None otherwise.
        """
        if isinstance(self.deps, RouterDeps):
            return self.deps.router_mode.value
        return None

    @property
    def active_sub_agent(self) -> str | None:
        """Get the active sub-agent for ActiveSubAgentProvider protocol.

        Returns:
            The sub-agent type string if executing, None otherwise.
        """
        if isinstance(self.deps, RouterDeps) and self.deps.active_sub_agent:
            return self.deps.active_sub_agent.value
        return None

    def action_toggle_mode(self) -> None:
        """Toggle between Planning and Drafting modes for Router."""
        from shotgun.agents.router.models import RouterDeps, RouterMode

        # If in Q&A mode, exit it first (SHIFT+TAB escapes Q&A mode)
        if self.qa_mode:
            self._exit_qa_mode()
            self.agent_manager.add_hint_message(
                HintMessage(message="Exited Q&A mode via Shift+Tab")
            )
            return

        if not isinstance(self.deps, RouterDeps):
            return

        # Prevent mode switching during execution
        if self.deps.is_executing:
            self.agent_manager.add_hint_message(
                HintMessage(message="⚠️ Cannot switch modes during plan execution")
            )
            return

        # Prevent mode switching while sub-agent is active
        if self.deps.active_sub_agent is not None:
            self.agent_manager.add_hint_message(
                HintMessage(message="⚠️ Cannot switch modes while sub-agent is running")
            )
            return

        # Toggle mode
        if self.deps.router_mode == RouterMode.PLANNING:
            self.deps.router_mode = RouterMode.DRAFTING
            mode_name = "Drafting"
        else:
            self.deps.router_mode = RouterMode.PLANNING
            mode_name = "Planning"
            # Clear plan when switching back to Planning mode
            # This forces the agent to create a new plan for the next request
            self.deps.current_plan = None
            self.deps.approval_status = PlanApprovalStatus.SKIPPED
            self.deps.is_executing = False

        # Show mode change feedback
        self.agent_manager.add_hint_message(
            HintMessage(message=f"Switched to {mode_name} mode")
        )

        # Update UI
        self.widget_coordinator.update_for_mode_change(self.mode)
        self.call_later(lambda: self.widget_coordinator.update_prompt_input(focus=True))

    async def action_show_usage(self) -> None:
        usage_hint = self.agent_manager.get_usage_hint()
        logger.info(f"Usage hint: {usage_hint}")

        # Add budget info for Shotgun Account users
        if self.deps.llm_model.is_shotgun_account:
            try:
                from shotgun.llm_proxy import LiteLLMProxyClient

                logger.debug("Fetching budget info for Shotgun Account")
                client = LiteLLMProxyClient(self.deps.llm_model.api_key)
                budget_info = await client.get_budget_info()

                # Format budget section
                source_label = "Key" if budget_info.source == "key" else "Team"
                budget_section = f"""## Shotgun Account Budget

* Max Budget:     ${budget_info.max_budget:.2f}
* Current Spend:  ${budget_info.spend:.2f}
* Remaining:      ${budget_info.remaining:.2f} ({100 - budget_info.percentage_used:.1f}%)
* Budget Source:  {source_label}-level

**Questions or need help?**"""

                # Build markdown_before (usage + budget info before email)
                if usage_hint:
                    markdown_before = f"{usage_hint}\n\n{budget_section}"
                else:
                    markdown_before = budget_section

                markdown_after = (
                    "\n\n_Reach out anytime for billing questions "
                    "or to increase your budget._"
                )

                # Mount with email copy button
                self.mount_hint_with_email(
                    markdown_before=markdown_before,
                    email="contact@shotgun.sh",
                    markdown_after=markdown_after,
                )
                logger.debug("Successfully added budget info to usage hint")
                return  # Exit early since we've already mounted

            except Exception as e:
                logger.warning(f"Failed to fetch budget info: {e}")
                # For Shotgun Account, show budget fetch error
                # If we have usage data, still show it
                if usage_hint:
                    # Show usage even though budget fetch failed
                    self.mount_hint(usage_hint)
                else:
                    # No usage and budget fetch failed - show specific error with email
                    markdown_before = (
                        "⚠️ **Unable to fetch budget information**\n\n"
                        "There was an error retrieving your budget data."
                    )
                    markdown_after = (
                        "\n\n_Try the command again in a moment. "
                        "If the issue persists, reach out for help._"
                    )
                    self.mount_hint_with_email(
                        markdown_before=markdown_before,
                        email="contact@shotgun.sh",
                        markdown_after=markdown_after,
                    )
                return  # Exit early

        # Fallback for non-Shotgun Account users
        if usage_hint:
            self.mount_hint(usage_hint)
        else:
            self.agent_manager.add_hint_message(
                HintMessage(message="⚠️ No usage hint available")
            )

    async def action_show_context(self) -> None:
        context_hint = await self.agent_manager.get_context_hint()
        if context_hint:
            self.mount_hint(context_hint)
        else:
            self.agent_manager.add_hint_message(
                HintMessage(message="⚠️ No context analysis available")
            )

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
            self.agent_manager.add_hint_message(
                HintMessage(message=f"❌ Failed to compact: {e}")
            )
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
            await self.conversation_service.clear_conversation()

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
            self.agent_manager.add_hint_message(
                HintMessage(message=f"❌ Failed to clear: {e}")
            )

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

    def _show_pull_hint(self) -> None:
        """Show hint about recently pulled spec from meta.json."""
        # Import at runtime to avoid circular import (CLI -> TUI dependency)
        from shotgun.cli.spec.models import SpecMeta

        shotgun_dir = get_shotgun_base_path()
        meta_path = shotgun_dir / "meta.json"
        if not meta_path.exists():
            return

        try:
            meta: SpecMeta = SpecMeta.model_validate_json(meta_path.read_text())
            # Only show if pulled within last 60 seconds
            age_seconds = (datetime.now(timezone.utc) - meta.pulled_at).total_seconds()
            if age_seconds > 60:
                return

            hint_parts = [f"You just pulled **{meta.spec_name}** from the cloud."]
            if meta.web_url:
                hint_parts.append(f"[View in browser]({meta.web_url})")
            hint_parts.append(
                f"The specs are now located at `{shotgun_dir}` so Shotgun has access to them."
            )
            if meta.backup_path:
                hint_parts.append(
                    f"Previous files were backed up to: `{meta.backup_path}`"
                )
            self.mount_hint("\n\n".join(hint_parts))
        except Exception:
            # Ignore errors reading meta.json - this is optional UI feedback
            logger.debug("Failed to read meta.json for pull hint", exc_info=True)

    def mount_hint_with_email(
        self, markdown_before: str, email: str, markdown_after: str = ""
    ) -> None:
        """Mount a hint with inline email copy button.

        Args:
            markdown_before: Markdown content to display before the email line
            email: Email address to display with copy button
            markdown_after: Optional markdown content to display after the email line
        """
        hint = HintMessage(
            message=markdown_before, email=email, markdown_after=markdown_after
        )
        self.agent_manager.add_hint_message(hint)

    async def execute_shell_command(self, command: str) -> None:
        """Execute a shell command and display output.

        This implements the `!`-to-shell behavior for interactive mode.
        Commands are executed in the current working directory with
        full shell features (pipes, redirection, etc.).

        Args:
            command: The shell command to execute (after stripping the leading `!`)

        Note:
            - Commands are executed with shell=True for full shell features
            - Output is streamed to the TUI via hint messages
            - Errors are displayed but do not crash the application
            - Commands are NOT added to conversation history
        """
        # Handle empty command (just `!` with nothing after it)
        if not command or command.isspace():
            self.mount_hint("⚠️ Empty shell command. Usage: `!<command>`")
            return

        # Show what command is being executed
        # Use code block for better visibility
        self.mount_hint(f"**Running:** `{command}`")

        try:
            # Execute with shell=True to support pipes, redirection, etc.
            # Run in current working directory
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=Path.cwd(),
            )

            # Wait for command to complete and capture output
            stdout_bytes, stderr_bytes = await process.communicate()
            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")
            return_code = process.returncode or 0

            # Build output message
            output_parts = []

            if stdout:
                # Show stdout in a code block for proper formatting
                output_parts.append(f"```\n{stdout.rstrip()}\n```")

            if stderr:
                # Show stderr with a warning indicator
                output_parts.append(f"**stderr:**\n```\n{stderr.rstrip()}\n```")

            if return_code != 0:
                # Show non-zero exit code as error
                output_parts.append(f"**Exit code:** {return_code}")

            # Display output (or success message if no output)
            if output_parts:
                self.mount_hint("\n\n".join(output_parts))
            elif return_code == 0:
                self.mount_hint("✓ Command completed successfully (no output)")

        except Exception as e:
            # Show error message
            self.mount_hint(f"❌ **Shell command failed:**\n```\n{str(e)}\n```")

    @on(PartialResponseMessage)
    def handle_partial_response(self, event: PartialResponseMessage) -> None:
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
        self.widget_coordinator.set_partial_response(event.message, new_message_list)

        # Skip context updates for file write operations (they don't add to input context)
        has_file_write = any(
            isinstance(msg, ModelResponse)
            and any(
                isinstance(part, ToolCallPart)
                and part.tool_name in ("write_file", "append_file")
                for part in msg.parts
            )
            for msg in event.messages
        )

        if has_file_write:
            return  # Skip context update for file writes

        # Skip context updates when a sub-agent is streaming
        # Sub-agents run with isolated message history, so their streaming doesn't
        # represent the router's actual context usage
        if isinstance(self.deps, RouterDeps) and self.deps.active_sub_agent is not None:
            return  # Skip context update for sub-agent streaming

        # Throttle context indicator updates to improve performance during streaming
        # Only update at most once per 5 seconds to avoid excessive token calculations
        current_time = time.time()
        if current_time - self._last_context_update >= self._context_update_throttle:
            self._last_context_update = current_time
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

        # Safety check: don't enter Q&A mode if questions array is empty
        if not event.questions:
            logger.warning("ClarifyingQuestionsMessage received with empty questions")
            return

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
        logger.debug(
            "[MSG_HISTORY] MessageHistoryUpdated received - %d messages",
            len(event.messages),
        )
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
        # Skip if hint was already added by agent_manager (e.g., in QA mode)
        if event.file_operations:
            # Check if file operation hint already exists in recent messages
            file_hint_exists = any(
                isinstance(msg, HintMessage)
                and (
                    msg.message.startswith("📝 Modified:")
                    or msg.message.startswith("📁 Modified")
                )
                for msg in event.messages[-5:]  # Check last 5 messages
            )

            if not file_hint_exists:
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
                            num_files = len(
                                {op.file_path for op in event.file_operations}
                            )
                            if path_obj.is_dir():
                                message = f"📁 Modified {num_files} files in: `{display_path}`"
                            else:
                                # Common path is a file, show parent directory
                                message = f"📁 Modified {num_files} files in: `{path_obj.parent}`"

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

    @on(ToolExecutionStartedMessage)
    def handle_tool_execution_started(self, event: ToolExecutionStartedMessage) -> None:
        """Update spinner text when a tool starts executing.

        This provides visual feedback during long-running tool executions
        like web search, so the UI doesn't appear frozen.
        """
        self.widget_coordinator.update_spinner_text(event.spinner_text)

    @on(ToolStreamingProgressMessage)
    def handle_tool_streaming_progress(
        self, event: ToolStreamingProgressMessage
    ) -> None:
        """Update spinner text with token count during tool streaming.

        Shows progress while tool arguments are streaming in,
        particularly useful for long file writes.
        """
        text = f"{event.spinner_text} (~{event.streamed_tokens:,} tokens)"
        self.widget_coordinator.update_spinner_text(text)
        # Force immediate refresh to show progress
        self.refresh()

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

            # Reset agents so they get recreated with new model
            self.agent_manager._agents_initialized = False
            self.agent_manager._research_agent = None
            self.agent_manager._plan_agent = None
            self.agent_manager._tasks_agent = None
            self.agent_manager._specify_agent = None
            self.agent_manager._export_agent = None
            self.agent_manager._research_deps = None
            self.agent_manager._plan_deps = None
            self.agent_manager._tasks_deps = None
            self.agent_manager._specify_deps = None
            self.agent_manager._export_deps = None

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

    @on(PromptInput.OpenCommandPalette)
    def _on_open_command_palette(self, event: PromptInput.OpenCommandPalette) -> None:
        """Open command palette when triggered by '/' prefix."""
        self.app.action_command_palette()

    @on(PromptInput.Submitted)
    async def handle_submit(self, message: PromptInput.Submitted) -> None:
        """Handle user input submission from the prompt.

        This is the main interactive loop entrypoint for shotgun-cli TUI.
        Input classification:
        1. Lines starting with `!` (after trimming whitespace) are shell commands
        2. Lines starting with `/` are internal commands
        3. All other lines are sent to the LLM

        Shell command behavior (`!`-to-shell):
        - Lines like `!ls` or `  !git status` execute as shell commands
        - Shell commands are NOT sent to LLM
        - Shell commands are NOT added to conversation history
        - Implementation: v1 limitation - no history expansion (!!, !$, etc.)
        """
        text = message.text.strip()

        # If empty text, just clear input and return
        if not text:
            self.widget_coordinator.update_prompt_input(clear=True)
            self.value = ""
            return

        # Stage 1: Classify input - check if line starts with `!` (shell command)
        # Trim leading whitespace and check first character
        trimmed = message.text.lstrip()
        if trimmed.startswith("!"):
            # This is a shell command - extract the command by removing exactly one `!`
            # Note: `!!ls` becomes `!ls` in v1 (no special history expansion)
            shell_command = trimmed[1:]  # Remove the leading `!`

            # Execute shell command (do NOT forward to LLM or add to history)
            await self.execute_shell_command(shell_command)

            # Clear input and return (do not proceed to LLM handling)
            # This ensures shell commands are never added to conversation history
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

    def share_specs_command(self) -> None:
        """Launch the share specs workflow."""
        self.call_later(lambda: self._start_share_specs_flow())

    @work
    async def _start_share_specs_flow(self) -> None:
        """Main workflow for sharing specs to workspace."""
        # 1. Check preconditions (instant check, no API call)
        shotgun_dir = Path.cwd() / ".shotgun"
        if not shotgun_dir.exists():
            self.mount_hint("No .shotgun/ directory found in current directory")
            return

        # 2. Show spec selection dialog (handles workspace fetch, permissions, and spec loading)
        result = await self.app.push_screen_wait(ShareSpecsDialog())
        if result is None or result.action is None:
            return  # User cancelled or error

        workspace_id = result.workspace_id
        if not workspace_id:
            self.mount_hint("Failed to get workspace")
            return

        # 3. Handle create vs add version
        if result.action == ShareSpecsAction.CREATE:
            # Show create spec dialog
            create_result = await self.app.push_screen_wait(CreateSpecDialog())
            if create_result is None:
                return  # User cancelled

            # Pass spec creation info to UploadProgressScreen
            # It will create the spec/version and then upload
            upload_result = await self.app.push_screen_wait(
                UploadProgressScreen(
                    workspace_id,
                    spec_name=create_result.name,
                    spec_description=create_result.description,
                    spec_is_public=create_result.is_public,
                )
            )

        else:  # add_version
            spec_id = result.spec_id
            if not spec_id:
                self.mount_hint("No spec selected")
                return

            # Pass spec_id to UploadProgressScreen
            # It will create the version and then upload
            upload_result = await self.app.push_screen_wait(
                UploadProgressScreen(workspace_id, spec_id=spec_id)
            )

        # 7. Show result
        if upload_result and upload_result.success:
            if upload_result.web_url:
                self.mount_hint(
                    f"Specs shared successfully!\n\nView at: {upload_result.web_url}"
                )
            else:
                self.mount_hint("Specs shared successfully!")
        elif upload_result and upload_result.cancelled:
            self.mount_hint("Upload cancelled")
        # Error case is handled by the upload screen

    def delete_codebase_from_palette(self, graph_id: str) -> None:
        stack = getattr(self.app, "screen_stack", None)
        if stack and isinstance(stack[-1], CommandPalette):
            self.app.pop_screen()

        self.call_later(lambda: self.delete_codebase(graph_id))

    @work
    async def delete_codebase(self, graph_id: str) -> None:
        try:
            await self.codebase_sdk.delete_codebase(graph_id)
            self.agent_manager.add_hint_message(
                HintMessage(message=f"✓ Deleted codebase: {graph_id}")
            )
        except CodebaseNotFoundError as exc:
            self.agent_manager.add_hint_message(HintMessage(message=f"❌ {exc}"))
        except Exception as exc:  # pragma: no cover - defensive UI path
            self.agent_manager.add_hint_message(
                HintMessage(message=f"❌ Failed to delete codebase: {exc}")
            )

    def _classify_kuzu_error(self, exception: Exception) -> KuzuErrorType:
        """Classify a Kuzu database error.

        Args:
            exception: The exception to classify

        Returns:
            KuzuErrorType indicating the category of error
        """
        return classify_kuzu_error(exception)

    def _is_kuzu_corruption_error(self, exception: Exception) -> bool:
        """Check if error is related to kuzu database corruption.

        Args:
            exception: The exception to check

        Returns:
            True if the error indicates kuzu database corruption or lock issues
        """
        error_type = classify_kuzu_error(exception)
        # Consider corruption and lock errors as "kuzu errors" that need special handling
        return error_type in (
            KuzuErrorType.CORRUPTION,
            KuzuErrorType.LOCKED,
            KuzuErrorType.SCHEMA,
        )

    @work(group="indexing", exit_on_error=False)
    async def index_codebase(self, selection: CodebaseIndexSelection) -> None:
        logger.debug(f"index_codebase worker starting for {selection.repo_path}")
        index_start_time = time.time()

        # Compute graph_id to track indexing state
        graph_id = self.codebase_sdk.service.compute_graph_id(selection.repo_path)

        # Mark indexing as started and show hint
        await self.codebase_sdk.service.indexing.start(graph_id)
        self.agent_manager.add_hint_message(
            HintMessage(
                message="Indexing has started. The codebase graph will be "
                "inaccessible to the AI Agents until this is completed."
            )
        )

        label = self.query_one("#indexing-job-display", Static)
        label.update(
            f"[$foreground-muted]Indexing codebase: [bold $text-accent]{selection.name}[/][/]"
        )
        label.refresh()

        # Track progress timer for cleanup
        progress_timer = None

        try:

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
                # Calculate overall percentage with weights based on actual timing:
                # Structure: 0-2%, Definitions: 2-18%, Relationships: 18-20%
                # Flush nodes: 20-28%, Flush relationships: 28-100%
                if progress_info.phase == ProgressPhase.STRUCTURE:
                    # Phase 1: 0-2% (actual: ~0%)
                    overall_pct = 2.0 if progress_info.phase_complete else 1.0
                elif progress_info.phase == ProgressPhase.DEFINITIONS:
                    # Phase 2: 2-18% based on files processed (actual: ~16%)
                    if progress_info.total and progress_info.total > 0:
                        phase_pct = (progress_info.current / progress_info.total) * 16.0
                        overall_pct = 2.0 + phase_pct
                    else:
                        overall_pct = 2.0
                elif progress_info.phase == ProgressPhase.RELATIONSHIPS:
                    # Phase 3: 18-20% based on relationships processed (actual: ~0.3%)
                    if progress_info.total and progress_info.total > 0:
                        phase_pct = (progress_info.current / progress_info.total) * 2.0
                        overall_pct = 18.0 + phase_pct
                    else:
                        overall_pct = 18.0
                elif progress_info.phase == ProgressPhase.FLUSH_NODES:
                    # Phase 4: 20-28% based on nodes flushed (actual: ~7.5%)
                    if progress_info.total and progress_info.total > 0:
                        phase_pct = (progress_info.current / progress_info.total) * 8.0
                        overall_pct = 20.0 + phase_pct
                    else:
                        overall_pct = 20.0
                elif progress_info.phase == ProgressPhase.FLUSH_RELATIONSHIPS:
                    # Phase 5: 28-100% based on relationships flushed (actual: ~76%)
                    if progress_info.total and progress_info.total > 0:
                        phase_pct = (progress_info.current / progress_info.total) * 72.0
                        overall_pct = 28.0 + phase_pct
                    else:
                        overall_pct = 28.0
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
                        self.agent_manager.add_hint_message(
                            HintMessage(
                                message=f"🔄 Retrying indexing after cleanup (attempt {attempt + 1}/{max_retries})..."
                            )
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
                    logger.debug("index_codebase SDK call completed successfully")

                    # Success! Stop progress animation
                    progress_timer.stop()

                    # Show 100% completion after indexing finishes
                    final_bar = create_progress_bar(100.0)
                    label.update(
                        f"[$foreground-muted]Indexing codebase: {final_bar} 100%[/]"
                    )
                    label.refresh()

                    # Calculate duration and format message
                    duration = time.time() - index_start_time
                    duration_str = _format_duration(duration)
                    entity_count = result.node_count + result.relationship_count
                    entity_str = _format_count(entity_count)

                    logger.info(
                        f"Successfully indexed codebase '{result.name}' in {duration_str} "
                        f"({entity_count} entities)"
                    )
                    self.agent_manager.add_hint_message(
                        HintMessage(
                            message=f"✓ Indexed '{result.name}' in {duration_str} ({entity_str} entities). "
                            "Codebase graph is now accessible."
                        )
                    )
                    break  # Success - exit retry loop

                except asyncio.CancelledError:
                    logger.warning(
                        "index_codebase worker was cancelled - this should not happen"
                    )
                    raise  # Re-raise to let finally block clean up

                except CodebaseAlreadyIndexedError as exc:
                    progress_timer.stop()
                    logger.warning(f"Codebase already indexed: {exc}")
                    self.agent_manager.add_hint_message(HintMessage(message=f"⚠️ {exc}"))
                    return
                except InvalidPathError as exc:
                    progress_timer.stop()
                    logger.error(f"Invalid path error: {exc}")
                    self.agent_manager.add_hint_message(
                        HintMessage(message=f"❌ {exc}")
                    )
                    return
                except KuzuImportError as exc:
                    progress_timer.stop()
                    logger.error(f"Kuzu import error (Windows DLL issue): {exc}")
                    # Show dialog with copy button for Windows users
                    await self.app.push_screen_wait(KuzuErrorDialog())
                    return

                except Exception as exc:  # pragma: no cover - defensive UI path
                    # Check if this is a kuzu corruption error and we have retries left
                    if attempt < max_retries - 1 and self._is_kuzu_corruption_error(
                        exc
                    ):
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

                    # Provide helpful error message with correct path for kuzu errors
                    if self._is_kuzu_corruption_error(exc):
                        storage_dir = self.codebase_sdk.service.storage_dir
                        self.agent_manager.add_hint_message(
                            HintMessage(
                                message=(
                                    f"❌ Database error during indexing. "
                                    f"Try deleting files in: {storage_dir}"
                                )
                            )
                        )
                    else:
                        self.agent_manager.add_hint_message(
                            HintMessage(message=f"❌ Failed to index codebase: {exc}")
                        )
                    break
        finally:
            # Always stop the progress timer, clean up label, and mark indexing complete
            if progress_timer:
                progress_timer.stop()
            label.update("")
            label.refresh()
            await self.codebase_sdk.service.indexing.complete(graph_id)

    @work
    async def run_agent(self, message: str) -> None:
        # Start processing with spinner
        from textual.worker import get_current_worker

        self.processing_state.start_processing("Processing...")
        self.processing_state.bind_worker(get_current_worker())

        # Start context indicator animation immediately
        self.widget_coordinator.set_context_streaming(True)

        try:
            # Use unified agent runner - exceptions propagate for handling
            runner = AgentRunner(self.agent_manager)
            await runner.run(message)
        except ShotgunAccountException as e:
            # Shotgun Account errors show contact email UI
            message_parts = e.to_markdown().split("**Need help?**")
            if len(message_parts) == 2:
                markdown_before = message_parts[0] + "**Need help?**"
                markdown_after = message_parts[1].strip()
                self.mount_hint_with_email(
                    markdown_before=markdown_before,
                    email=SHOTGUN_CONTACT_EMAIL,
                    markdown_after=markdown_after,
                )
            else:
                # Fallback if message format is unexpected
                self.mount_hint(e.to_markdown())
        except ErrorNotPickedUpBySentry as e:
            # All other user-actionable errors - display with markdown
            self.mount_hint(e.to_markdown())
        except Exception as e:
            # Unexpected errors that weren't wrapped (shouldn't happen)
            logger.exception("Unexpected error in run_agent")
            self.mount_hint(f"⚠️ An unexpected error occurred: {str(e)}")
        finally:
            self.processing_state.stop_processing()
            # Stop context indicator animation
            self.widget_coordinator.set_context_streaming(False)

            # Check for low balance after agent loop completes (only for Shotgun Account)
            # This runs after processing but doesn't interfere with Q&A mode
            if self.deps.llm_model.is_shotgun_account:
                await self._check_low_balance_warning()

        # Check for pending approval (Planning mode multi-step plan creation)
        self._check_pending_approval()

        # Check for pending checkpoint (Planning mode step completion)
        self._check_pending_checkpoint()

        # Check for plan completion (Drafting mode)
        self._check_plan_completion()

        # Check if agent stopped with incomplete plan (failsafe)
        self._check_incomplete_plan()

        # Save conversation after each interaction
        self._save_conversation()

        self.widget_coordinator.update_prompt_input(focus=True)

    def _save_conversation(self) -> None:
        """Save the current conversation to persistent storage."""
        # Use conversation service for saving (run async in background)
        # Use exclusive=True to prevent concurrent saves that can cause file contention
        self.run_worker(
            self.conversation_service.save_conversation(self.agent_manager),
            exclusive=True,
        )

    async def _check_low_balance_warning(self) -> None:
        """Check account balance and show warning if $2.50 or less remaining.

        This runs after every agent loop completion for Shotgun Account users.
        Errors are silently caught to avoid disrupting user workflow.
        """
        try:
            from shotgun.llm_proxy import LiteLLMProxyClient

            client = LiteLLMProxyClient(self.deps.llm_model.api_key)
            budget_info = await client.get_budget_info()

            # Show warning if remaining balance is $2.50 or less
            if budget_info.remaining <= 2.50:
                warning_message = (
                    f"⚠️ **Low Balance Warning**\n\n"
                    f"Your Shotgun Account has **${budget_info.remaining:.2f}** remaining.\n\n"
                    f"👉 **[Top Up Now at https://app.shotgun.sh/dashboard](https://app.shotgun.sh/dashboard)**"
                )
                self.agent_manager.add_hint_message(
                    HintMessage(message=warning_message)
                )
        except Exception as e:
            # Silently log and continue - don't block user workflow
            logger.debug(f"Failed to check low balance warning: {e}")

    async def _check_and_load_conversation(self) -> None:
        """Check if conversation exists and load it if it does."""
        if await self.conversation_manager.exists():
            self._load_conversation()

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

    # =========================================================================
    # Step Checkpoint Handlers (Planning Mode)
    # =========================================================================

    @on(StepCompleted)
    def handle_step_completed(self, event: StepCompleted) -> None:
        """Show checkpoint widget when a step completes in Planning mode.

        This handler is triggered after mark_step_done is called and sets
        up a pending checkpoint. It shows the StepCheckpointWidget to let
        the user decide whether to continue, modify, or stop.
        """
        if not isinstance(self.deps, RouterDeps):
            return
        if self.deps.router_mode != RouterMode.PLANNING:
            return

        # Show checkpoint widget
        self._show_checkpoint_widget(event.step, event.next_step)

    def _track_checkpoint_event(self, event_name: str) -> None:
        """Track a checkpoint-related PostHog event.

        Args:
            event_name: The name of the event to track.
        """
        if isinstance(self.deps, RouterDeps) and self.deps.current_plan:
            plan = self.deps.current_plan
            completed_count = sum(1 for s in plan.steps if s.done)
            track_event(
                event_name,
                {
                    "completed_step_position": completed_count,
                    "steps_remaining": len(plan.steps) - completed_count,
                },
            )

    @on(CheckpointContinue)
    def handle_checkpoint_continue(self) -> None:
        """Continue to next step when user approves at checkpoint."""
        self._track_checkpoint_event("checkpoint_continued")
        self._hide_checkpoint_widget()
        self._execute_next_step()

    @on(CheckpointModify)
    def handle_checkpoint_modify(self) -> None:
        """Return to prompt input for plan modification."""
        self._hide_checkpoint_widget()

        if isinstance(self.deps, RouterDeps):
            self.deps.is_executing = False

        self.widget_coordinator.update_prompt_input(focus=True)

    @on(CheckpointStop)
    def handle_checkpoint_stop(self) -> None:
        """Stop execution, keep remaining steps as pending."""
        self._track_checkpoint_event("checkpoint_stopped")
        self._hide_checkpoint_widget()

        if isinstance(self.deps, RouterDeps):
            self.deps.is_executing = False

        # Show confirmation message
        self.mount_hint("⏸️ Execution stopped. Remaining steps are still in the plan.")
        self.widget_coordinator.update_prompt_input(focus=True)

    def _show_checkpoint_widget(
        self,
        step: "ExecutionStep",
        next_step: "ExecutionStep | None",
    ) -> None:
        """Replace PromptInput with StepCheckpointWidget.

        Args:
            step: The step that was just completed.
            next_step: The next step to execute, or None if last step.
        """
        # Create the checkpoint widget
        self._checkpoint_widget = StepCheckpointWidget(step, next_step)

        # Hide PromptInput
        prompt_input = self.query_one(PromptInput)
        prompt_input.display = False

        # Mount checkpoint widget in footer
        footer = self.query_one("#footer")
        footer.mount(self._checkpoint_widget, after=prompt_input)

    def _hide_checkpoint_widget(self) -> None:
        """Remove checkpoint widget, restore PromptInput."""
        if hasattr(self, "_checkpoint_widget") and self._checkpoint_widget:
            self._checkpoint_widget.remove()
            self._checkpoint_widget = None

        # Show PromptInput
        prompt_input = self.query_one(PromptInput)
        prompt_input.display = True

    def _execute_next_step(self) -> None:
        """Execute the next step in the plan."""
        if not isinstance(self.deps, RouterDeps) or not self.deps.current_plan:
            return

        # Advance to next step
        plan = self.deps.current_plan
        plan.current_step_index += 1

        next_step = plan.current_step()
        if next_step:
            # Resume router execution for the next step
            self.run_agent(f"Continue with next step: {next_step.title}")
        else:
            # Plan complete
            self.deps.is_executing = False
            self.mount_hint("✅ All plan steps completed!")
            self.widget_coordinator.update_prompt_input(focus=True)

    def _check_pending_checkpoint(self) -> None:
        """Check if there's a pending checkpoint and post StepCompleted if so.

        This is called after each agent run to check if mark_step_done
        set a pending checkpoint in Planning mode.
        """
        if not isinstance(self.deps, RouterDeps):
            return

        if self.deps.pending_checkpoint is None:
            return

        # Extract checkpoint data and clear the pending state
        checkpoint = self.deps.pending_checkpoint
        self.deps.pending_checkpoint = None

        # Post the StepCompleted message to trigger the checkpoint UI
        self.post_message(
            StepCompleted(
                step=checkpoint.completed_step, next_step=checkpoint.next_step
            )
        )

    def _check_plan_completion(self) -> None:
        """Check if a plan was completed in Drafting mode and show completion message.

        This is called after each agent run to check if mark_step_done
        set pending_completion in Drafting mode.
        """
        logger.debug("[PLAN] _check_plan_completion called")
        if not isinstance(self.deps, RouterDeps):
            logger.debug("[PLAN] Not RouterDeps, skipping plan completion check")
            return

        if not self.deps.pending_completion:
            logger.debug("[PLAN] No pending completion")
            return

        # Don't show completion message if Q&A mode is active.
        # The user needs to answer the clarifying questions first.
        # Keep pending_completion=True so it shows after Q&A is done.
        if self.qa_mode:
            logger.debug("[PLAN] Q&A mode active, deferring plan completion message")
            return

        # Clear the pending state
        self.deps.pending_completion = False

        # Show completion message
        logger.debug("[PLAN] Showing plan completion message for drafting mode")
        self.mount_hint("✅ All plan steps completed!")

        # Hide the plan panel since the plan is done
        self._hide_plan_panel()

    def _check_incomplete_plan(self) -> None:
        """Check if agent returned with an incomplete plan in Drafting mode.

        This is a failsafe to notify the user if the agent stopped
        mid-plan without completing all steps.
        """
        logger.debug("[PLAN] _check_incomplete_plan called")

        if not isinstance(self.deps, RouterDeps):
            logger.debug("[PLAN] Not RouterDeps, skipping incomplete plan check")
            return

        logger.debug(
            "[PLAN] router_mode=%s, current_plan=%s",
            self.deps.router_mode,
            self.deps.current_plan.goal if self.deps.current_plan else None,
        )

        if self.deps.router_mode != RouterMode.DRAFTING:
            logger.debug("[PLAN] Not in DRAFTING mode, skipping incomplete plan check")
            return

        plan = self.deps.current_plan
        if plan is None:
            logger.debug("[PLAN] No current plan")
            return

        if plan.is_complete():
            logger.debug("[PLAN] Plan is complete, no incomplete plan hint needed")
            return

        # Don't show the "continue to resume" hint if Q&A mode is active.
        # The user needs to answer the clarifying questions first.
        if self.qa_mode:
            logger.debug(
                "[PLAN] Q&A mode active, deferring incomplete plan hint until "
                "questions are answered"
            )
            return

        # Plan exists and is incomplete - show status hint
        completed = sum(1 for s in plan.steps if s.done)
        total = len(plan.steps)
        remaining = [s.title for s in plan.steps if not s.done]

        logger.info(
            "[PLAN] Agent stopped with incomplete plan: %d/%d steps done, "
            "remaining: %s",
            completed,
            total,
            remaining,
        )

        hint = (
            f"📋 **Plan Status: {completed}/{total} steps complete**\n\n"
            f"Remaining: {', '.join(remaining)}\n\n"
            f"_Type 'continue' to resume the plan._"
        )
        self.mount_hint(hint)

    # =========================================================================
    # Sub-Agent Lifecycle Handlers (Stage 8)
    # =========================================================================

    @on(SubAgentStarted)
    def handle_sub_agent_started(self, event: SubAgentStarted) -> None:
        """Update mode indicator when router delegates to a sub-agent.

        Sets the active_sub_agent in RouterDeps and refreshes the mode
        indicator to show "📋 Planning → Research" format.
        """
        if isinstance(self.deps, RouterDeps):
            self.deps.active_sub_agent = event.agent_type
            self.widget_coordinator.refresh_mode_indicator()

    @on(SubAgentCompleted)
    def handle_sub_agent_completed(self, event: SubAgentCompleted) -> None:
        """Clear sub-agent display when delegation completes.

        Clears the active_sub_agent in RouterDeps and refreshes the mode
        indicator to show just the mode name.
        """
        if isinstance(self.deps, RouterDeps):
            self.deps.active_sub_agent = None
            self.widget_coordinator.refresh_mode_indicator()

    # =========================================================================
    # Cascade Confirmation Handlers (Planning Mode)
    # =========================================================================

    @on(CascadeConfirmationRequired)
    def handle_cascade_confirmation_required(
        self, event: CascadeConfirmationRequired
    ) -> None:
        """Show cascade confirmation widget when a file with dependents is updated.

        In Planning mode, after updating a file like specification.md that has
        dependent files, this shows the CascadeConfirmationWidget to let the
        user decide which dependent files should also be updated.
        """
        if not isinstance(self.deps, RouterDeps):
            return
        if self.deps.router_mode != RouterMode.PLANNING:
            # In Drafting mode, auto-cascade without confirmation
            self._execute_cascade(CascadeScope.ALL, event.dependent_files)
            return

        # Show cascade confirmation widget
        self._show_cascade_widget(event.updated_file, event.dependent_files)

    @on(CascadeConfirmed)
    def handle_cascade_confirmed(self, event: CascadeConfirmed) -> None:
        """Execute cascade update based on user's selected scope."""
        # Get dependent files from the widget before hiding it
        dependent_files: list[str] = []
        if self._cascade_widget:
            dependent_files = self._cascade_widget.dependent_files

        self._hide_cascade_widget()
        self._execute_cascade(event.scope, dependent_files)

    @on(CascadeDeclined)
    def handle_cascade_declined(self) -> None:
        """Handle user declining cascade update."""
        self._hide_cascade_widget()
        self.mount_hint(
            "ℹ️ Cascade update skipped. You can update dependent files manually."
        )
        self.widget_coordinator.update_prompt_input(focus=True)

    def _show_cascade_widget(
        self,
        updated_file: str,
        dependent_files: list[str],
    ) -> None:
        """Replace PromptInput with CascadeConfirmationWidget.

        Args:
            updated_file: The file that was just updated.
            dependent_files: List of files that depend on the updated file.
        """
        # Create the cascade confirmation widget
        self._cascade_widget = CascadeConfirmationWidget(updated_file, dependent_files)

        # Hide PromptInput
        prompt_input = self.query_one(PromptInput)
        prompt_input.display = False

        # Mount cascade widget in footer
        footer = self.query_one("#footer")
        footer.mount(self._cascade_widget, after=prompt_input)

    def _hide_cascade_widget(self) -> None:
        """Remove cascade widget, restore PromptInput."""
        if self._cascade_widget:
            self._cascade_widget.remove()
            self._cascade_widget = None

        # Show PromptInput
        prompt_input = self.query_one(PromptInput)
        prompt_input.display = True

    def _execute_cascade(self, scope: CascadeScope, dependent_files: list[str]) -> None:
        """Execute cascade updates based on the selected scope.

        Args:
            scope: The scope of files to update.
            dependent_files: List of dependent files that could be updated.

        Note:
            Actual cascade execution (calling sub-agents) requires Stage 9's
            delegation tools. For now, this shows a hint about what would happen.
        """
        if scope == CascadeScope.NONE:
            return

        # Determine which files will be updated based on scope
        files_to_update: list[str] = []
        if scope == CascadeScope.ALL:
            files_to_update = dependent_files
        elif scope == CascadeScope.PLAN_ONLY:
            files_to_update = [f for f in dependent_files if "plan.md" in f]
        elif scope == CascadeScope.TASKS_ONLY:
            files_to_update = [f for f in dependent_files if "tasks.md" in f]

        if files_to_update:
            file_names = ", ".join(f.split("/")[-1] for f in files_to_update)
            # TODO: Stage 9 will implement actual delegation to sub-agents
            self.mount_hint(f"📋 Cascade update queued for: {file_names}")

        self.widget_coordinator.update_prompt_input(focus=True)

    def _check_pending_cascade(self) -> None:
        """Check if there's a pending cascade and post CascadeConfirmationRequired if so.

        This is called after each agent run to check if a file modification
        set a pending cascade in Planning mode.
        """
        if not isinstance(self.deps, RouterDeps):
            return

        if self.deps.pending_cascade is None:
            return

        # Extract cascade data and clear the pending state
        cascade = self.deps.pending_cascade
        self.deps.pending_cascade = None

        # Post the CascadeConfirmationRequired message to trigger the cascade UI
        self.post_message(
            CascadeConfirmationRequired(
                updated_file=cascade.updated_file,
                dependent_files=cascade.dependent_files,
            )
        )

    # =========================================================================
    # Plan Approval Handlers (Planning Mode - Stage 7)
    # =========================================================================

    @on(PlanApprovalRequired)
    def handle_plan_approval_required(self, event: PlanApprovalRequired) -> None:
        """Show approval widget when a multi-step plan is created.

        In Planning mode, after creating a plan with multiple steps,
        this shows the PlanApprovalWidget to let the user decide
        whether to proceed or clarify.
        """
        logger.debug(
            "[PLAN] handle_plan_approval_required - plan=%s",
            f"'{event.plan.goal}' with {len(event.plan.steps)} steps",
        )
        if not isinstance(self.deps, RouterDeps):
            logger.debug("[PLAN] Not RouterDeps, skipping approval widget")
            return
        if self.deps.router_mode != RouterMode.PLANNING:
            logger.debug(
                "[PLAN] Not in PLANNING mode (%s), skipping approval widget",
                self.deps.router_mode,
            )
            return

        # Show approval widget
        logger.debug("[PLAN] Showing approval widget")
        self._show_approval_widget(event.plan)

    @on(PlanApproved)
    def handle_plan_approved(self) -> None:
        """Begin plan execution when user approves."""
        self._hide_approval_widget()

        if isinstance(self.deps, RouterDeps):
            # Track plan approved metric
            if self.deps.current_plan:
                track_event(
                    "plan_approved",
                    {
                        "step_count": len(self.deps.current_plan.steps),
                    },
                )

            self.deps.approval_status = PlanApprovalStatus.APPROVED
            self.deps.is_executing = True

            # Switch to Drafting mode when plan is approved
            self.deps.router_mode = RouterMode.DRAFTING
            self.widget_coordinator.update_for_mode_change(self.mode)

            # Begin execution of the first step
            plan = self.deps.current_plan
            if plan and plan.current_step():
                first_step = plan.current_step()
                if first_step:
                    self.run_agent(f"Execute step: {first_step.title}")
            else:
                self.widget_coordinator.update_prompt_input(focus=True)

    @on(PlanRejected)
    def handle_plan_rejected(self) -> None:
        """Return to prompt input for clarification when user rejects plan."""
        self._hide_approval_widget()

        if isinstance(self.deps, RouterDeps):
            # Track plan rejected metric
            if self.deps.current_plan:
                track_event(
                    "plan_rejected",
                    {
                        "step_count": len(self.deps.current_plan.steps),
                    },
                )

            self.deps.approval_status = PlanApprovalStatus.REJECTED
            # Clear the plan since user wants to modify
            self.deps.current_plan = None

        self.mount_hint("ℹ️ Plan cancelled. Please clarify what you'd like to do.")
        self.widget_coordinator.update_prompt_input(focus=True)

    def _show_approval_widget(self, plan: ExecutionPlan) -> None:
        """Replace PromptInput with PlanApprovalWidget.

        Args:
            plan: The execution plan that needs user approval.
        """
        # Create the approval widget
        self._approval_widget = PlanApprovalWidget(plan)

        # Hide PromptInput
        prompt_input = self.query_one(PromptInput)
        prompt_input.display = False

        # Mount approval widget in footer
        footer = self.query_one("#footer")
        footer.mount(self._approval_widget, after=prompt_input)

    def _hide_approval_widget(self) -> None:
        """Remove approval widget, restore PromptInput."""
        if self._approval_widget:
            self._approval_widget.remove()
            self._approval_widget = None

        # Show PromptInput
        prompt_input = self.query_one(PromptInput)
        prompt_input.display = True

    def _check_pending_approval(self) -> None:
        """Check if there's a pending approval and post PlanApprovalRequired if so.

        This is called after each agent run to check if create_plan
        set a pending approval in Planning mode.
        """
        logger.debug("[PLAN] _check_pending_approval called")
        if not isinstance(self.deps, RouterDeps):
            logger.debug("[PLAN] Not RouterDeps, skipping pending approval check")
            return

        # Don't show plan approval while user is answering questions.
        # The pending approval will remain set and be checked again
        # after Q&A completes (when run_agent is called with answers).
        if self.qa_mode:
            logger.debug("[PLAN] Q&A mode active, deferring plan approval")
            return

        if self.deps.pending_approval is None:
            logger.debug("[PLAN] No pending approval")
            return

        # Extract approval data and clear the pending state
        approval = self.deps.pending_approval
        self.deps.pending_approval = None

        logger.debug(
            "[PLAN] Found pending approval for plan: '%s' with %d steps",
            approval.plan.goal,
            len(approval.plan.steps),
        )

        # Post the PlanApprovalRequired message to trigger the approval UI
        self.post_message(PlanApprovalRequired(plan=approval.plan))

    # =========================================================================
    # Plan Panel (Stage 11)
    # =========================================================================

    @on(PlanUpdated)
    def handle_plan_updated(self, event: PlanUpdated) -> None:
        """Auto-show/hide plan panel when plan changes.

        The plan panel automatically shows when a plan is created or
        modified, and hides when the plan is cleared.
        """
        if event.plan is not None:
            # Show panel (auto-reopens when plan changes)
            self._show_plan_panel(event.plan)
        else:
            # Plan cleared - hide panel
            self._hide_plan_panel()

    @on(PlanPanelClosed)
    def handle_plan_panel_closed(self, event: PlanPanelClosed) -> None:
        """Handle user closing the plan panel with × button."""
        self._hide_plan_panel()

    def _show_plan_panel(self, plan: ExecutionPlan) -> None:
        """Show the plan panel with the given plan.

        Args:
            plan: The execution plan to display.
        """
        if self._plan_panel is None:
            self._plan_panel = PlanPanelWidget(plan)
            # Mount in window container, before footer
            window = self.query_one("#window")
            footer = self.query_one("#footer")
            window.mount(self._plan_panel, before=footer)
        else:
            self._plan_panel.update_plan(plan)

    def _hide_plan_panel(self) -> None:
        """Hide the plan panel."""
        if self._plan_panel:
            self._plan_panel.remove()
            self._plan_panel = None

    def _on_plan_changed(self, plan: ExecutionPlan | None) -> None:
        """Handle plan changes from router tools.

        This callback is set on RouterDeps to receive plan updates
        and post PlanUpdated messages to update the plan panel.

        Args:
            plan: The updated plan or None if plan was cleared.
        """
        logger.debug(
            "[PLAN] _on_plan_changed called - plan=%s",
            f"'{plan.goal}' with {len(plan.steps)} steps" if plan else "None",
        )
        self.post_message(PlanUpdated(plan))
