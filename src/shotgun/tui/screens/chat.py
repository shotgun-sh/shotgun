import logging
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from pydantic_ai import DeferredToolResults, RunContext
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)
from textual import on, work
from textual.app import ComposeResult
from textual.command import CommandPalette
from textual.containers import Container, Grid
from textual.reactive import reactive
from textual.screen import ModalScreen, Screen
from textual.widget import Widget
from textual.widgets import Button, DirectoryTree, Input, Label, Markdown, Static

from shotgun.agents.agent_manager import (
    AgentManager,
    AgentType,
    MessageHistoryUpdated,
    PartialResponseMessage,
)
from shotgun.agents.config import get_provider_model
from shotgun.agents.models import (
    AgentDeps,
    FileOperationTracker,
    UserAnswer,
    UserQuestion,
)
from shotgun.codebase.core.manager import CodebaseAlreadyIndexedError
from shotgun.sdk.codebase import CodebaseSDK
from shotgun.sdk.exceptions import CodebaseNotFoundError, InvalidPathError
from shotgun.sdk.services import get_artifact_service, get_codebase_service
from shotgun.tui.commands import CommandHandler
from shotgun.tui.screens.chat_screen.history import ChatHistory

from ..components.prompt_input import PromptInput
from ..components.spinner import Spinner
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

    def render(self) -> str:
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

        return f"[bold $text-accent]{mode_title} mode[/][$foreground-muted] ({description})[/]"


class FilteredDirectoryTree(DirectoryTree):
    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        return [path for path in paths if path.is_dir()]


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
            yield Label("Index your codebase?", id="index-prompt-title")
            yield Static(
                "We found project files but no index yet. Indexing enables smarter chat."
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


class CodebaseIndexScreen(ModalScreen[CodebaseIndexSelection | None]):
    """Modal dialog for choosing a repository and name to index."""

    DEFAULT_CSS = """
        CodebaseIndexScreen {
            align: center middle;
            background: rgba(0, 0, 0, 0.0);
        }
        CodebaseIndexScreen > #index-dialog {
            width: 80%;
            max-width: 80;
            height: 80%;
            max-height: 40;
            border: wide $primary;
            padding: 1;
            layout: vertical;
            background: $surface;
        }

        #index-dialog DirectoryTree {
            height: 1fr;
            border: solid $accent;
            overflow: auto;
        }

        #index-dialog-controls {
            layout: horizontal;
            align-horizontal: right;
            padding-top: 1;
        }
    """

    def __init__(self, start_path: Path | None = None) -> None:
        super().__init__()
        self.start_path = Path(start_path or Path.cwd())
        self.selected_path: Path | None = self.start_path

    def compose(self) -> ComposeResult:
        with Container(id="index-dialog"):
            yield Label("Index a codebase", id="index-dialog-title")
            yield FilteredDirectoryTree(self.start_path, id="index-directory-tree")
            yield Input(
                placeholder="Enter a name for the codebase",
                id="index-codebase-name",
            )
            with Container(id="index-dialog-controls"):
                yield Button("Cancel", id="index-cancel")
                yield Button(
                    "Index",
                    id="index-confirm",
                    variant="primary",
                    disabled=True,
                )

    def on_mount(self) -> None:
        name_input = self.query_one("#index-codebase-name", Input)
        if not name_input.value and self.selected_path:
            name_input.value = self.selected_path.name
        self._update_confirm()

    def _update_confirm(self) -> None:
        confirm = self.query_one("#index-confirm", Button)
        name_input = self.query_one("#index-codebase-name", Input)
        confirm.disabled = not (self.selected_path and name_input.value.strip())

    @on(DirectoryTree.DirectorySelected, "#index-directory-tree")
    def handle_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        event.stop()
        selected = event.path if event.path.is_dir() else event.path.parent
        self.selected_path = selected
        name_input = self.query_one("#index-codebase-name", Input)
        if not name_input.value:
            name_input.value = selected.name
        self._update_confirm()

    @on(Input.Changed, "#index-codebase-name")
    def handle_name_changed(self, event: Input.Changed) -> None:
        event.stop()
        self._update_confirm()

    @on(Button.Pressed, "#index-cancel")
    def handle_cancel(self, event: Button.Pressed) -> None:
        event.stop()
        self.dismiss(None)

    @on(Button.Pressed, "#index-confirm")
    def handle_confirm(self, event: Button.Pressed) -> None:
        event.stop()
        name_input = self.query_one("#index-codebase-name", Input)
        if not self.selected_path:
            self.dismiss(None)
            return
        selection = CodebaseIndexSelection(
            repo_path=self.selected_path,
            name=name_input.value.strip(),
        )
        self.dismiss(selection)


class ChatScreen(Screen[None]):
    CSS_PATH = "chat.tcss"

    BINDINGS = [
        ("ctrl+p", "command_palette", "Command Palette"),
        ("shift+tab", "toggle_mode", "Toggle mode"),
    ]

    COMMANDS = {AgentModeProvider, ProviderSetupProvider, CodebaseCommandProvider}

    _PLACEHOLDER_BY_MODE: dict[AgentType, str] = {
        AgentType.RESEARCH: (
            "Ask for investigations, e.g. research strengths and weaknesses of PydanticAI vs its rivals"
        ),
        AgentType.PLAN: (
            "Describe a goal to plan, e.g. draft a rollout plan for launching our Slack automation"
        ),
        AgentType.TASKS: (
            "Request actionable work, e.g. break down tasks to wire OpenTelemetry into the API"
        ),
        AgentType.SPECIFY: (
            "Request detailed specifications, e.g. create a comprehensive spec for user authentication system"
        ),
        AgentType.EXPORT: (
            "Request export tasks, e.g. export research findings to Markdown or convert tasks to CSV"
        ),
    }

    value = reactive("")
    mode = reactive(AgentType.RESEARCH)
    history: PromptHistory = PromptHistory()
    messages = reactive(list[ModelMessage]())
    working = reactive(False)
    question: reactive[UserQuestion | None] = reactive(None)
    indexing_job: reactive[CodebaseIndexSelection | None] = reactive(None)
    partial_message: reactive[ModelMessage | None] = reactive(None)

    def __init__(self) -> None:
        super().__init__()
        # Get the model configuration and services
        model_config = get_provider_model()
        codebase_service = get_codebase_service()
        artifact_service = get_artifact_service()
        self.codebase_sdk = CodebaseSDK()

        # Create shared deps without system_prompt_fn (agents provide their own)
        # We need a placeholder system_prompt_fn to satisfy the field requirement
        def _placeholder_system_prompt_fn(ctx: RunContext[AgentDeps]) -> str:
            raise RuntimeError(
                "This should not be called - agents provide their own system_prompt_fn"
            )

        self.deps = AgentDeps(
            interactive_mode=True,
            llm_model=model_config,
            codebase_service=codebase_service,
            artifact_service=artifact_service,
            system_prompt_fn=_placeholder_system_prompt_fn,
        )
        self.agent_manager = AgentManager(deps=self.deps, initial_type=self.mode)
        self.command_handler = CommandHandler()

    def on_mount(self) -> None:
        self.query_one(PromptInput).focus(scroll_visible=True)
        # Hide spinner initially
        self.query_one("#spinner").display = False
        self.call_later(self.check_if_codebase_is_indexed)
        # Start the question listener worker to handle ask_user interactions
        self.call_later(self.add_question_listener)

    @work
    async def check_if_codebase_is_indexed(self) -> None:
        cur_dir = Path.cwd().resolve()
        is_empty = all(
            dir.is_dir() and dir.name in ["__pycache__", ".git", ".shotgun"]
            for dir in cur_dir.iterdir()
        )
        if is_empty:
            return

        # find at least one codebase that is indexed in the current directory
        directory_indexed = next(
            (
                dir
                for dir in (await self.codebase_sdk.list_codebases()).graphs
                if cur_dir.is_relative_to(Path(dir.repo_path).resolve())
            ),
            None,
        )
        if directory_indexed:
            self.mount_hint(help_text_with_codebase())
            return

        should_index = await self.app.push_screen_wait(CodebaseIndexPromptScreen())
        if not should_index:
            self.mount_hint(help_text_empty_dir())
            return

        self.index_codebase_command()

    def watch_mode(self, new_mode: AgentType) -> None:
        """React to mode changes by updating the agent manager."""

        if self.is_mounted:
            self.agent_manager.set_agent(new_mode)

            mode_indicator = self.query_one(ModeIndicator)
            mode_indicator.mode = new_mode
            mode_indicator.refresh()

            prompt_input = self.query_one(PromptInput)
            prompt_input.placeholder = self._placeholder_for_mode(new_mode)
            prompt_input.refresh()

    def watch_working(self, is_working: bool) -> None:
        """Show or hide the spinner based on working state."""
        if self.is_mounted:
            spinner = self.query_one("#spinner")
            spinner.set_classes("" if is_working else "hidden")
            spinner.display = is_working

    def watch_messages(self, messages: list[ModelMessage]) -> None:
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
                yield StatusBar()
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
        chat_history = self.query_one(ChatHistory)
        if not chat_history.vertical_tail:
            return
        chat_history.vertical_tail.mount(Markdown(markdown))

    @on(PartialResponseMessage)
    def handle_partial_response(self, event: PartialResponseMessage) -> None:
        self.partial_message = event.message

        partial_response_widget = self.query_one(ChatHistory)
        partial_response_widget.partial_response = self.partial_message
        if event.is_last:
            partial_response_widget.partial_response = None

    def _clear_partial_response(self) -> None:
        partial_response_widget = self.query_one(ChatHistory)
        partial_response_widget.partial_response = None

    @on(MessageHistoryUpdated)
    def handle_message_history_updated(self, event: MessageHistoryUpdated) -> None:
        """Handle message history updates from the agent manager."""
        self._clear_partial_response()
        self.messages = event.messages

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

                    # Add this as a simple markdown widget
                    file_info_widget = Markdown(message)
                    chat_history.vertical_tail.mount(file_info_widget)

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

    def _placeholder_for_mode(self, mode: AgentType) -> str:
        """Return the placeholder text appropriate for the current mode."""
        return self._PLACEHOLDER_BY_MODE.get(mode, "Type your message")

    def index_codebase_command(self) -> None:
        start_path = Path.cwd()

        def handle_result(result: CodebaseIndexSelection | None) -> None:
            if result:
                self.call_later(lambda: self.index_codebase(result))

        self.app.push_screen(
            CodebaseIndexScreen(start_path=start_path),
            handle_result,
        )

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
        try:
            result = await self.codebase_sdk.index_codebase(
                selection.repo_path, selection.name
            )
            self.notify(
                f"Indexed codebase '{result.name}' (ID: {result.graph_id})",
                severity="information",
                timeout=8,
            )

            self.mount_hint(codebase_indexed_hint(selection.name))
        except CodebaseAlreadyIndexedError as exc:
            self.notify(str(exc), severity="warning")
            return
        except InvalidPathError as exc:
            self.notify(str(exc), severity="error")

        except Exception as exc:  # pragma: no cover - defensive UI path
            self.notify(f"Failed to index codebase: {exc}", severity="error")
        finally:
            label.update("")
            label.refresh()

    @work
    async def run_agent(self, message: str) -> None:
        deferred_tool_results = None
        prompt = None
        self.working = True

        if self.question:
            # This is a response to a question from the agent
            self.question.result.set_result(
                UserAnswer(answer=message, tool_call_id=self.question.tool_call_id)
            )

            deferred_tool_results = DeferredToolResults()

            deferred_tool_results.calls[self.question.tool_call_id] = UserAnswer(
                answer=message, tool_call_id=self.question.tool_call_id
            )

            self.question = None
        else:
            # This is a new user prompt
            prompt = message

        await self.agent_manager.run(
            prompt=prompt,
            deferred_tool_results=deferred_tool_results,
        )
        self.working = False

        prompt_input = self.query_one(PromptInput)
        prompt_input.focus()


def codebase_indexed_hint(codebase_name: str) -> str:
    return (
        f"Codebase **{codebase_name}** indexed successfully. You can now use it in your chat.\n\n"
        + help_text_with_codebase()
    )


def help_text_with_codebase() -> str:
    return (
        "I can help with:\n\n"
        "- Speccing out a new feature\n"
        "- Onboarding you onto this project\n"
        "- Helping with a refactor spec\n"
        "- Creating AGENTS.md file for this project\n"
    )


def help_text_empty_dir() -> str:
    return (
        "What would you like to build? Here are some examples:\n\n"
        "- Research FastAPI vs Django\n"
        "- Plan my new web app using React\n"
        "- Create PRD for my planned product\n"
    )
