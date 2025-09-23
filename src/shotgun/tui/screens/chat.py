from collections.abc import AsyncGenerator
from typing import cast

from pydantic_ai import DeferredToolResults, RunContext
from pydantic_ai.messages import (
    BuiltinToolCallPart,
    BuiltinToolReturnPart,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ThinkingPart,
    ToolCallPart,
)
from textual import on, work
from textual.app import ComposeResult
from textual.command import DiscoveryHit, Hit, Provider
from textual.containers import Container
from textual.reactive import reactive
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import Markdown

from shotgun.agents.agent_manager import AgentManager, AgentType, MessageHistoryUpdated
from shotgun.agents.config import get_provider_model
from shotgun.agents.models import (
    AgentDeps,
    FileOperationTracker,
    UserAnswer,
    UserQuestion,
)
from shotgun.sdk.services import get_artifact_service, get_codebase_service

from ..components.prompt_input import PromptInput
from ..components.spinner import Spinner
from ..components.vertical_tail import VerticalTail


def _dummy_system_prompt_fn(ctx: RunContext[AgentDeps]) -> str:
    """Dummy system prompt function for TUI chat interface."""
    return "You are a helpful AI assistant."


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


class ChatHistory(Widget):
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

    def __init__(self) -> None:
        super().__init__()
        self.items: list[ModelMessage] = []
        self.vertical_tail: VerticalTail | None = None

    def compose(self) -> ComposeResult:
        self.vertical_tail = VerticalTail()
        yield self.vertical_tail

    def update_messages(self, messages: list[ModelMessage]) -> None:
        """Update the displayed messages without recomposing."""
        if not self.vertical_tail:
            return

        # Clear existing widgets
        self.vertical_tail.remove_children()

        # Add new message widgets
        for item in messages:
            if isinstance(item, ModelRequest):
                self.vertical_tail.mount(UserQuestionWidget(item))
            elif isinstance(item, ModelResponse):
                self.vertical_tail.mount(AgentResponseWidget(item))

        self.items = messages


class UserQuestionWidget(Widget):
    def __init__(self, item: ModelRequest) -> None:
        super().__init__()
        self.item = item

    def compose(self) -> ComposeResult:
        prompt = "".join(str(part.content) for part in self.item.parts if part.content)
        yield Markdown(markdown=f"**>** {prompt}")


class AgentResponseWidget(Widget):
    def __init__(self, item: ModelResponse) -> None:
        super().__init__()
        self.item = item

    def compose(self) -> ComposeResult:
        yield Markdown(markdown=f"**⏺** {self.compute_output()}")

    def compute_output(self) -> str:
        acc = ""
        for part in self.item.parts:  # TextPart | ToolCallPart | BuiltinToolCallPart | BuiltinToolReturnPart | ThinkingPart
            if isinstance(part, TextPart):
                acc += part.content
            elif isinstance(part, ToolCallPart):
                acc += f"{part.tool_name}({part.args})\n"
            elif isinstance(part, BuiltinToolCallPart):
                acc += f"{part.tool_name}({part.args})\n"
            elif isinstance(part, BuiltinToolReturnPart):
                acc += f"{part.tool_name}()\n"
            elif isinstance(part, ThinkingPart):
                acc += f"Thinking: {part.content}\n"
        return acc


class StatusBar(Widget):
    DEFAULT_CSS = """
        StatusBar {
            text-wrap: wrap;
        }
    """

    def render(self) -> str:
        return """[$foreground-muted][bold $text]enter[/] to send • [bold $text]ctrl+p[/] command palette • [bold $text]shift+tab[/] cycle modes • /help for commands[/]"""


class ModeIndicator(Widget):
    """Widget to display the current agent mode."""

    DEFAULT_CSS = """
        ModeIndicator {
            text-wrap: wrap;
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
        }
        mode_description = {
            AgentType.RESEARCH: "Research topics with web search and synthesize findings",
            AgentType.PLAN: "Create comprehensive, actionable plans with milestones",
            AgentType.TASKS: "Generate specific, actionable tasks from research and plans",
        }

        mode_title = mode_display.get(self.mode, self.mode.value.title())
        description = mode_description.get(self.mode, "")

        return f"[bold $text-accent]{mode_title} mode[/][$foreground-muted] ({description})[/]"


class AgentModeProvider(Provider):
    """Command provider for agent mode switching."""

    @property
    def chat_screen(self) -> "ChatScreen":
        return cast(ChatScreen, self.screen)

    def set_mode(self, mode: AgentType) -> None:
        """Switch to research mode."""
        self.chat_screen.mode = mode

    async def discover(self) -> AsyncGenerator[DiscoveryHit, None]:
        """Provide default mode switching commands when palette opens."""
        yield DiscoveryHit(
            "Switch to Research Mode",
            lambda: self.set_mode(AgentType.RESEARCH),
            help="🔬 Research topics with web search and synthesize findings",
        )
        yield DiscoveryHit(
            "Switch to Plan Mode",
            lambda: self.set_mode(AgentType.PLAN),
            help="📋 Create comprehensive, actionable plans with milestones",
        )
        yield DiscoveryHit(
            "Switch to Tasks Mode",
            lambda: self.set_mode(AgentType.TASKS),
            help="✅ Generate specific, actionable tasks from research and plans",
        )

    async def search(self, query: str) -> AsyncGenerator[Hit, None]:
        """Search for mode commands."""
        matcher = self.matcher(query)

        commands = [
            (
                "Switch to Research Mode",
                "🔬 Research topics with web search and synthesize findings",
                lambda: self.set_mode(AgentType.RESEARCH),
                AgentType.RESEARCH,
            ),
            (
                "Switch to Plan Mode",
                "📋 Create comprehensive, actionable plans with milestones",
                lambda: self.set_mode(AgentType.PLAN),
                AgentType.PLAN,
            ),
            (
                "Switch to Tasks Mode",
                "✅ Generate specific, actionable tasks from research and plans",
                lambda: self.set_mode(AgentType.TASKS),
                AgentType.TASKS,
            ),
        ]

        for title, help_text, callback, mode in commands:
            if self.chat_screen.mode == mode:
                continue
            score = matcher.match(title)
            if score > 0:
                yield Hit(score, matcher.highlight(title), callback, help=help_text)


class ProviderSetupProvider(Provider):
    """Command palette entries for provider configuration."""

    @property
    def chat_screen(self) -> "ChatScreen":
        return cast(ChatScreen, self.screen)

    def open_provider_config(self) -> None:
        """Show the provider configuration screen."""
        self.chat_screen.app.push_screen("provider_config")

    async def discover(self) -> AsyncGenerator[DiscoveryHit, None]:
        yield DiscoveryHit(
            "Open Provider Setup",
            self.open_provider_config,
            help="⚙️ Manage API keys for available providers",
        )

    async def search(self, query: str) -> AsyncGenerator[Hit, None]:
        matcher = self.matcher(query)
        title = "Open Provider Setup"
        score = matcher.match(title)
        if score > 0:
            yield Hit(
                score,
                matcher.highlight(title),
                self.open_provider_config,
                help="⚙️ Manage API keys for available providers",
            )


class ChatScreen(Screen[None]):
    CSS_PATH = "chat.tcss"

    BINDINGS = [
        ("ctrl+p", "command_palette", "Command Palette"),
        ("shift+tab", "toggle_mode", "Toggle mode"),
    ]

    COMMANDS = {AgentModeProvider, ProviderSetupProvider}

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
    }

    value = reactive("")
    mode = reactive(AgentType.RESEARCH)
    history: PromptHistory = PromptHistory()
    messages = reactive(list[ModelMessage]())
    working = reactive(False)
    question: reactive[UserQuestion | None] = reactive(None)

    def __init__(self) -> None:
        super().__init__()
        # Get the model configuration and services
        model_config = get_provider_model()
        codebase_service = get_codebase_service()
        artifact_service = get_artifact_service()
        self.deps = AgentDeps(
            interactive_mode=True,
            llm_model=model_config,
            codebase_service=codebase_service,
            artifact_service=artifact_service,
            system_prompt_fn=_dummy_system_prompt_fn,
        )
        self.agent_manager = AgentManager(deps=self.deps, initial_type=self.mode)

    def on_mount(self) -> None:
        self.query_one(PromptInput).focus(scroll_visible=True)
        # Hide spinner initially
        self.query_one("#spinner").display = False

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
        modes = [AgentType.RESEARCH, AgentType.PLAN, AgentType.TASKS]
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
            yield ChatHistory()
            yield Markdown(markdown="", id="question-display")
            yield self.agent_manager
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
                yield ModeIndicator(mode=self.mode)

    @on(MessageHistoryUpdated)
    def handle_message_history_updated(self, event: MessageHistoryUpdated) -> None:
        """Handle message history updates from the agent manager."""
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
        self.history.append(message.text)

        # Clear the input
        self.value = ""
        self.run_agent(message.text)

        prompt_input = self.query_one(PromptInput)
        prompt_input.clear()

    def _placeholder_for_mode(self, mode: AgentType) -> str:
        """Return the placeholder text appropriate for the current mode."""
        return self._PLACEHOLDER_BY_MODE.get(mode, "Type your message")

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
