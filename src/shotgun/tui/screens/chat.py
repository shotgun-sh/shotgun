import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from pydantic_ai import RunContext
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)
from textual import events, on, work
from textual.app import ComposeResult
from textual.command import CommandPalette
from textual.containers import Container, Grid
from textual.keys import Keys
from textual.reactive import reactive
from textual.screen import ModalScreen, Screen
from textual.widget import Widget
from textual.widgets import Button, Label, Markdown, Static

from shotgun.agents.agent_manager import (
    AgentManager,
    MessageHistoryUpdated,
    PartialResponseMessage,
)
from shotgun.agents.config import get_provider_model
from shotgun.agents.conversation_history import (
    ConversationHistory,
    ConversationState,
)
from shotgun.agents.conversation_manager import ConversationManager
from shotgun.agents.models import (
    AgentDeps,
    AgentType,
    FileOperationTracker,
    UserQuestion,
)
from shotgun.codebase.core.manager import CodebaseAlreadyIndexedError
from shotgun.codebase.models import IndexProgress, ProgressPhase
from shotgun.posthog_telemetry import track_event
from shotgun.sdk.codebase import CodebaseSDK
from shotgun.sdk.exceptions import CodebaseNotFoundError, InvalidPathError
from shotgun.tui.commands import CommandHandler
from shotgun.tui.filtered_codebase_service import FilteredCodebaseService
from shotgun.tui.screens.chat_screen.hint_message import HintMessage
from shotgun.tui.screens.chat_screen.history import ChatHistory
from shotgun.utils import get_shotgun_home

from ..components.prompt_input import PromptInput
from ..components.spinner import Spinner
from ..utils.mode_progress import PlaceholderHints
from .chat_screen.command_providers import (
    AgentModeProvider,
    CodebaseCommandProvider,
    DeleteCodebasePaletteProvider,
    ProviderSetupProvider,
)

logger = logging.getLogger(__name__)


class PromptHistory:
    def __init__(self) -> None:
        self.prompts: list[str] = ["Hello there!"]
        self.curr: int | None = None

    def next(self) -> str:
        if self.curr is None:
            self.curr = -1
        else:
            self.curr = -1
        return self.prompts[self.curr]

    def prev(self) -> str:
        if self.curr is None:
            raise Exception("current entry is none")
        if self.curr == -1:
            self.curr = None
            return ""
        self.curr += 1
        return ""

    def append(self, text: str) -> None:
        self.prompts.append(text)
        self.curr = None


@dataclass
class CodebaseIndexSelection:
    """User-selected repository path and name for indexing."""

    repo_path: Path
    name: str


class StatusBar(Widget):
    DEFAULT_CSS = """
        StatusBar {
            text-wrap: wrap;
            padding-left: 1;
        }
    """

    def __init__(self, working: bool = False) -> None:
        """Initialize the status bar.

        Args:
            working: Whether an agent is currently working.
        """
        super().__init__()
        self.working = working

    def render(self) -> str:
        if self.working:
            return """[$foreground-muted][bold $text]esc[/] to stop • [bold $text]enter[/] to send • [bold $text]ctrl+p[/] command palette • [bold $text]shift+tab[/] cycle modes • /help for commands[/]"""
        else:
            return """[$foreground-muted][bold $text]enter[/] to send • [bold $text]ctrl+p[/] command palette • [bold $text]shift+tab[/] cycle modes • /help for commands[/]"""


class ModeIndicator(Widget):
    """Widget to display the current agent mode."""

    DEFAULT_CSS = """
        ModeIndicator {
            text-wrap: wrap;
            padding-left: 1;
        }
    """

    def __init__(self, mode: AgentType) -> None:
        """Initialize the mode indicator.

        Args:
            mode: The current agent type/mode.
        """
        super().__init__()
        self.mode = mode
        self.progress_checker = PlaceholderHints().progress_checker

    def render(self) -> str:
        """Render the mode indicator."""
        mode_display = {
            AgentType.RESEARCH: "Research",
            AgentType.PLAN: "Planning",
            AgentType.TASKS: "Tasks",
            AgentType.SPECIFY: "Specify",
            AgentType.EXPORT: "Export",
        }
        mode_description = {
            AgentType.RESEARCH: "Research topics with web search and synthesize findings",
            AgentType.PLAN: "Create comprehensive, actionable plans with milestones",
            AgentType.TASKS: "Generate specific, actionable tasks from research and plans",
            AgentType.SPECIFY: "Create detailed specifications and requirements documents",
            AgentType.EXPORT: "Export artifacts and findings to various formats",
        }

        mode_title = mode_display.get(self.mode, self.mode.value.title())
        description = mode_description.get(self.mode, "")

        # Check if mode has content
        has_content = self.progress_checker.has_mode_content(self.mode)
        status_icon = " ✓" if has_content else ""

        return f"[bold $text-accent]{mode_title}{status_icon} mode[/][$foreground-muted] ({description})[/]"


class CodebaseIndexPromptScreen(ModalScreen[bool]):
    """Modal dialog asking whether to index the detected codebase."""

    DEFAULT_CSS = """
        CodebaseIndexPromptScreen {
            align: center middle;
            background: rgba(0, 0, 0, 0.0);
        }

        CodebaseIndexPromptScreen > #index-prompt-dialog {
            width: 60%;
            max-width: 60;
            height: auto;
            border: wide $primary;
            padding: 1 2;
            layout: vertical;
            background: $surface;
            height: auto;
        }

        #index-prompt-buttons {
            layout: horizontal;
            align-horizontal: right;
            height: auto;
        }
    """

    def compose(self) -> ComposeResult:
        with Container(id="index-prompt-dialog"):
            yield Label("Index this codebase?", id="index-prompt-title")
            yield Static(
                f"Would you like to index the codebase at:\n{Path.cwd()}\n\n"
                "This is required for the agent to understand your code and answer "
                "questions about it. Without indexing, the agent cannot analyze your codebase."
            )
            with Container(id="index-prompt-buttons"):
                yield Button(
                    "Index now",
                    id="index-prompt-confirm",
                    variant="primary",
                )
                yield Button("Not now", id="index-prompt-cancel")

    @on(Button.Pressed, "#index-prompt-cancel")
    def handle_cancel(self, event: Button.Pressed) -> None:
        event.stop()
        self.dismiss(False)

    @on(Button.Pressed, "#index-prompt-confirm")
    def handle_confirm(self, event: Button.Pressed) -> None:
        event.stop()
        self.dismiss(True)


class ChatScreen(Screen[None]):
    CSS_PATH = "chat.tcss"

    BINDINGS = [
        ("ctrl+p", "command_palette", "Command Palette"),
        ("shift+tab", "toggle_mode", "Toggle mode"),
    ]

    COMMANDS = {AgentModeProvider, ProviderSetupProvider, CodebaseCommandProvider}

    value = reactive("")
    mode = reactive(AgentType.RESEARCH)
    history: PromptHistory = PromptHistory()
    messages = reactive(list[ModelMessage | HintMessage]())
    working = reactive(False)
    question: reactive[UserQuestion | None] = reactive(None)
    indexing_job: reactive[CodebaseIndexSelection | None] = reactive(None)
    partial_message: reactive[ModelMessage | None] = reactive(None)
    _current_worker = None  # Track the current running worker for cancellation

    def __init__(self, continue_session: bool = False) -> None:
        super().__init__()
        # Get the model configuration and services
        model_config = get_provider_model()
        # Use filtered service in TUI to restrict access to CWD codebase only
        storage_dir = get_shotgun_home() / "codebases"
        codebase_service = FilteredCodebaseService(storage_dir)
        self.codebase_sdk = CodebaseSDK()

        # Create shared deps without system_prompt_fn (agents provide their own)
        # We need a placeholder system_prompt_fn to satisfy the field requirement
        def _placeholder_system_prompt_fn(ctx: RunContext[AgentDeps]) -> str:
            raise RuntimeError(
                "This should not be called - agents provide their own system_prompt_fn"
            )

        self.deps = AgentDeps(
            interactive_mode=True,
            is_tui_context=True,
            llm_model=model_config,
            codebase_service=codebase_service,
            system_prompt_fn=_placeholder_system_prompt_fn,
        )
        self.agent_manager = AgentManager(deps=self.deps, initial_type=self.mode)
        self.command_handler = CommandHandler()
        self.placeholder_hints = PlaceholderHints()
        self.conversation_manager = ConversationManager()
        self.continue_session = continue_session

    def on_mount(self) -> None:
        self.query_one(PromptInput).focus(scroll_visible=True)
        # Hide spinner initially
        self.query_one("#spinner").display = False

        # Load conversation history if --continue flag was provided
        if self.continue_session and self.conversation_manager.exists():
            self._load_conversation()

        self.call_later(self.check_if_codebase_is_indexed)
        # Start the question listener worker to handle ask_user interactions
        self.call_later(self.add_question_listener)

    async def on_key(self, event: events.Key) -> None:
        """Handle key presses for cancellation."""
        # If escape or ctrl+c is pressed while agent is working, cancel the operation
        if (
            event.key in (Keys.Escape, Keys.ControlC)
            and self.working
            and self._current_worker
        ):
            # Track cancellation event
            track_event(
                "agent_cancelled",
                {
                    "agent_mode": self.mode.value,
                    "cancel_key": event.key,
                },
            )

            # Cancel the running agent worker
            self._current_worker.cancel()
            # Show cancellation message
            self.mount_hint("⚠️ Cancelling operation...")
            # Re-enable the input
            prompt_input = self.query_one(PromptInput)
            prompt_input.focus()
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

            mode_indicator = self.query_one(ModeIndicator)
            mode_indicator.mode = new_mode
            mode_indicator.refresh()

            prompt_input = self.query_one(PromptInput)
            # Force new hint selection when mode changes
            prompt_input.placeholder = self._placeholder_for_mode(
                new_mode, force_new=True
            )
            prompt_input.refresh()

    def watch_working(self, is_working: bool) -> None:
        """Show or hide the spinner based on working state."""
        if self.is_mounted:
            spinner = self.query_one("#spinner")
            spinner.set_classes("" if is_working else "hidden")
            spinner.display = is_working

            # Update the status bar to show/hide "ESC to stop"
            status_bar = self.query_one(StatusBar)
            status_bar.working = is_working
            status_bar.refresh()

    def watch_messages(self, messages: list[ModelMessage | HintMessage]) -> None:
        """Update the chat history when messages change."""
        if self.is_mounted:
            chat_history = self.query_one(ChatHistory)
            chat_history.update_messages(messages)

    def watch_question(self, question: UserQuestion | None) -> None:
        """Update the question display."""
        if self.is_mounted:
            question_display = self.query_one("#question-display", Markdown)
            if question:
                question_display.update(f"Question:\n\n{question.question}")
                question_display.display = True
            else:
                question_display.update("")
                question_display.display = False

    def action_toggle_mode(self) -> None:
        modes = [
            AgentType.RESEARCH,
            AgentType.SPECIFY,
            AgentType.PLAN,
            AgentType.TASKS,
            AgentType.EXPORT,
        ]
        self.mode = modes[(modes.index(self.mode) + 1) % len(modes)]
        self.agent_manager.set_agent(self.mode)
        # whoops it actually changes focus. Let's be brutal for now
        self.call_later(lambda: self.query_one(PromptInput).focus())

    @work
    async def add_question_listener(self) -> None:
        while True:
            question = await self.deps.queue.get()
            self.question = question
            await question.result
            self.deps.queue.task_done()

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        with Container(id="window"):
            yield self.agent_manager
            yield ChatHistory()
            yield Markdown(markdown="", id="question-display")
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
                    yield Static("", id="indexing-job-display")

    def mount_hint(self, markdown: str) -> None:
        hint = HintMessage(message=markdown)
        self.agent_manager.add_hint_message(hint)

    @on(PartialResponseMessage)
    def handle_partial_response(self, event: PartialResponseMessage) -> None:
        self.partial_message = event.message
        history = self.query_one(ChatHistory)

        # Only update messages if the message list changed
        new_message_list = self.messages + cast(
            list[ModelMessage | HintMessage], event.messages
        )
        if len(new_message_list) != len(history.items):
            history.update_messages(new_message_list)

        # Always update the partial response (reactive property handles the update)
        history.partial_response = self.partial_message

    def _clear_partial_response(self) -> None:
        partial_response_widget = self.query_one(ChatHistory)
        partial_response_widget.partial_response = None

    @on(MessageHistoryUpdated)
    def handle_message_history_updated(self, event: MessageHistoryUpdated) -> None:
        """Handle message history updates from the agent manager."""
        self._clear_partial_response()
        self.messages = event.messages

        # Refresh placeholder and mode indicator in case artifacts were created
        prompt_input = self.query_one(PromptInput)
        prompt_input.placeholder = self._placeholder_for_mode(self.mode)
        prompt_input.refresh()

        mode_indicator = self.query_one(ModeIndicator)
        mode_indicator.refresh()

        # If there are file operations, add a message showing the modified files
        if event.file_operations:
            chat_history = self.query_one(ChatHistory)
            if chat_history.vertical_tail:
                tracker = FileOperationTracker(operations=event.file_operations)
                display_path = tracker.get_display_path()

                if display_path:
                    # Create a simple markdown message with the file path
                    # The terminal emulator will make this clickable automatically
                    from pathlib import Path

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

    @on(PromptInput.Submitted)
    async def handle_submit(self, message: PromptInput.Submitted) -> None:
        text = message.text.strip()

        # If empty text, just clear input and return
        if not text:
            prompt_input = self.query_one(PromptInput)
            prompt_input.clear()
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
            prompt_input = self.query_one(PromptInput)
            prompt_input.clear()
            self.value = ""
            return

        # Not a command, process as normal
        self.history.append(message.text)

        # Clear the input
        self.value = ""
        self.run_agent(text)  # Use stripped text

        prompt_input = self.query_one(PromptInput)
        prompt_input.clear()

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

    @work
    async def index_codebase(self, selection: CodebaseIndexSelection) -> None:
        label = self.query_one("#indexing-job-display", Static)
        label.update(
            f"[$foreground-muted]Indexing [bold $text-accent]{selection.name}[/]...[/]"
        )
        label.refresh()

        def create_progress_bar(percentage: float, width: int = 20) -> str:
            """Create a visual progress bar using Unicode block characters."""
            filled = int((percentage / 100) * width)
            empty = width - filled
            return "▓" * filled + "░" * empty

        # Spinner animation state (shared between timer and progress callback)
        spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        spinner_state: dict[str, int | str | float] = {
            "frame_index": 0,
            "phase_name": "Starting...",
            "percentage": 0.0,
        }

        def update_spinner_display() -> None:
            """Update spinner frame on timer - runs every 100ms."""
            # Advance spinner frame
            frame_idx = int(spinner_state["frame_index"])
            spinner_state["frame_index"] = (frame_idx + 1) % len(spinner_frames)
            spinner = spinner_frames[frame_idx]

            # Get current state
            phase = str(spinner_state["phase_name"])
            pct = float(spinner_state["percentage"])
            bar = create_progress_bar(pct)

            # Update label
            label.update(
                f"[$foreground-muted]Indexing codebase: {spinner} {phase}... {bar} {pct:.0f}%[/]"
            )

        def progress_callback(progress_info: IndexProgress) -> None:
            """Update progress state (spinner animates independently on timer)."""
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
            spinner_state["phase_name"] = progress_info.phase_name
            spinner_state["percentage"] = overall_pct

        # Start spinner animation timer (10 fps = 100ms interval)
        spinner_timer = self.set_interval(0.1, update_spinner_display)

        try:
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

            # Stop spinner animation
            spinner_timer.stop()

            # Show 100% completion after indexing finishes
            final_bar = create_progress_bar(100.0)
            label.update(
                f"[$foreground-muted]Indexing codebase: ✓ Complete {final_bar} 100%[/]"
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

        except CodebaseAlreadyIndexedError as exc:
            spinner_timer.stop()
            logger.warning(f"Codebase already indexed: {exc}")
            self.notify(str(exc), severity="warning")
            return
        except InvalidPathError as exc:
            spinner_timer.stop()
            logger.error(f"Invalid path error: {exc}")
            self.notify(str(exc), severity="error")

        except Exception as exc:  # pragma: no cover - defensive UI path
            # Log full exception details with stack trace
            logger.exception(
                f"Failed to index codebase - repo_path: {selection.repo_path}, "
                f"name: {selection.name}, error: {exc}"
            )
            self.notify(f"Failed to index codebase: {exc}", severity="error")
        finally:
            # Always stop the spinner timer
            spinner_timer.stop()
            label.update("")
            label.refresh()

    @work
    async def run_agent(self, message: str) -> None:
        prompt = None
        self.working = True

        # Store the worker so we can cancel it if needed
        from textual.worker import get_current_worker

        self._current_worker = get_current_worker()

        prompt = message

        try:
            await self.agent_manager.run(
                prompt=prompt,
            )
        except asyncio.CancelledError:
            # Handle cancellation gracefully - DO NOT re-raise
            self.mount_hint("⚠️ Operation cancelled by user")
        finally:
            self.working = False
            self._current_worker = None

        # Save conversation after each interaction
        self._save_conversation()

        prompt_input = self.query_one(PromptInput)
        prompt_input.focus()

    def _save_conversation(self) -> None:
        """Save the current conversation to persistent storage."""
        # Get conversation state from agent manager
        state = self.agent_manager.get_conversation_state()

        # Create conversation history object
        conversation = ConversationHistory(
            last_agent_model=state.agent_type,
        )
        conversation.set_agent_messages(state.agent_messages)
        conversation.set_ui_messages(state.ui_messages)

        # Save to file
        self.conversation_manager.save(conversation)

    def _load_conversation(self) -> None:
        """Load conversation from persistent storage."""
        conversation = self.conversation_manager.load()
        if conversation is None:
            return

        # Restore agent state
        agent_messages = conversation.get_agent_messages()
        ui_messages = conversation.get_ui_messages()

        # Create ConversationState for restoration
        state = ConversationState(
            agent_messages=agent_messages,
            ui_messages=ui_messages,
            agent_type=conversation.last_agent_model,
        )

        self.agent_manager.restore_conversation_state(state)

        # Update the current mode
        self.mode = AgentType(conversation.last_agent_model)


def help_text_with_codebase(already_indexed: bool = False) -> str:
    return (
        "Howdy! Welcome to Shotgun - the context tool for software engineering. \n\nYou can research, build specs, plan, create tasks, and export context to your favorite code-gen agents.\n\n"
        f"{'' if already_indexed else 'Once your codebase is indexed, '}I can help with:\n\n"
        "- Speccing out a new feature\n"
        "- Onboarding you onto this project\n"
        "- Helping with a refactor spec\n"
        "- Creating AGENTS.md file for this project\n"
    )


def help_text_empty_dir() -> str:
    return (
        "Howdy! Welcome to Shotgun - the context tool for software engineering.\n\nYou can research, build specs, plan, create tasks, and export context to your favorite code-gen agents.\n\n"
        "What would you like to build? Here are some examples:\n\n"
        "- Research FastAPI vs Django\n"
        "- Plan my new web app using React\n"
        "- Create PRD for my planned product\n"
    )
