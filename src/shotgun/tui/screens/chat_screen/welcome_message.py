"""Welcome message widget for onboarding checklist."""

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, Markdown, Static

from shotgun.logging_config import get_logger

logger = get_logger(__name__)


class WelcomeMessage(BaseModel):
    """Data model capturing the welcome state snapshot."""

    kind: Literal["welcome"] = "welcome"
    is_home_directory: bool = False
    is_indexed: bool = False
    has_context7_key: bool = False
    is_frontier_model: bool = False
    frontier_model_label: str = ""
    frontier_model_name: str = ""
    is_ollama: bool = False
    is_byok: bool = False
    is_shotgun_account: bool = False
    has_gemini_key: bool = False


def _is_home_directory() -> bool:
    """Check if cwd is user's home directory."""
    if os.environ.get("HOME_DIRECTORY_SIMULATE", "").lower() == "true":
        return True
    return Path.cwd() == Path.home()


async def build_welcome_state() -> WelcomeMessage:
    """Build the welcome state by inspecting config, codebase index, and provider keys."""
    from shotgun.agents.config import get_config_manager
    from shotgun.agents.config.models import ModelName
    from shotgun.sdk.codebase import CodebaseSDK

    config_manager = get_config_manager()
    config = await config_manager.load()

    is_home = _is_home_directory()

    # Check codebase index status
    is_indexed = False
    if not is_home:
        try:
            sdk = CodebaseSDK()
            result = await sdk.list_codebases_for_directory()
            is_indexed = len(result.graphs) > 0
        except Exception:
            logger.debug("Failed to check codebase index status", exc_info=True)

    # Context7 key
    has_context7_key = (
        config.context7.api_key is not None
        and len(config.context7.api_key.get_secret_value()) > 0
    )

    # Determine account type
    is_shotgun_account = config_manager._provider_has_api_key(config.shotgun)
    is_ollama = config.ollama.enabled

    # Check BYOK provider keys
    has_anthropic = (
        config.anthropic.api_key is not None
        and len(config.anthropic.api_key.get_secret_value()) > 0
        if config.anthropic.api_key
        else False
    )
    has_openai = (
        config.openai.api_key is not None
        and len(config.openai.api_key.get_secret_value()) > 0
        if config.openai.api_key
        else False
    )
    has_google = (
        config.google.api_key is not None
        and len(config.google.api_key.get_secret_value()) > 0
        if config.google.api_key
        else False
    )

    is_byok = has_anthropic or has_openai or has_google

    # Gemini key for web search
    has_gemini_key = has_google

    # Determine frontier model
    is_frontier_model = False
    frontier_model_label = ""
    frontier_model_name = ""

    frontier_models = {
        ModelName.CLAUDE_OPUS_4_5,
        ModelName.GPT_5_2,
        ModelName.GEMINI_3_PRO_PREVIEW,
    }

    if config.selected_model and config.selected_model in frontier_models:
        is_frontier_model = True
    elif not is_ollama:
        # Determine best available frontier model
        if is_shotgun_account:
            frontier_model_label = "Select Opus 4.5"
            frontier_model_name = ModelName.CLAUDE_OPUS_4_5
        elif has_anthropic:
            frontier_model_label = "Select Opus 4.5"
            frontier_model_name = ModelName.CLAUDE_OPUS_4_5
        elif has_openai:
            frontier_model_label = "Select GPT-5.2"
            frontier_model_name = ModelName.GPT_5_2
        elif has_google:
            frontier_model_label = "Select Gemini 3 Pro"
            frontier_model_name = ModelName.GEMINI_3_PRO_PREVIEW

    return WelcomeMessage(
        is_home_directory=is_home,
        is_indexed=is_indexed,
        has_context7_key=has_context7_key,
        is_frontier_model=is_frontier_model,
        frontier_model_label=frontier_model_label,
        frontier_model_name=frontier_model_name,
        is_ollama=is_ollama,
        is_byok=is_byok,
        is_shotgun_account=is_shotgun_account,
        has_gemini_key=has_gemini_key,
    )


class WelcomeWidget(Widget):
    """Interactive onboarding checklist widget."""

    DEFAULT_CSS = """
        WelcomeWidget {
            background: $secondary-background-darken-1;
            height: auto;
            margin: 1;
            margin-left: 1;
            padding: 1;
        }

        WelcomeWidget .welcome-intro {
            height: auto;
            padding: 0;
            margin: 0;
        }

        WelcomeWidget .checklist-item {
            height: auto;
            padding: 0;
            margin: 0 0 0 2;
        }

        WelcomeWidget .checklist-note {
            height: auto;
            padding: 0;
            margin: 0 0 0 4;
            color: $text-muted;
        }

        WelcomeWidget .action-row {
            height: auto;
            width: auto;
            margin: 0 0 0 4;
        }

        WelcomeWidget .action-btn {
            width: auto;
            min-width: 16;
            margin: 0 1 0 0;
        }

        WelcomeWidget .welcome-footer {
            height: auto;
            padding: 1 0 0 0;
            margin: 0;
            color: $text-muted;
        }

        WelcomeWidget .getting-started-row {
            height: auto;
            width: auto;
            margin: 0 0 1 0;
        }
    """

    class WelcomeAction(Message):
        """Posted when a welcome button is clicked."""

        def __init__(self, action: str, model_name: str = "") -> None:
            super().__init__()
            self.action = action
            self.model_name = model_name

    def __init__(self, state: WelcomeMessage) -> None:
        super().__init__()
        self.state = state

    def compose(self) -> ComposeResult:
        s = self.state

        # Intro
        intro = (
            "**Welcome to Shotgun** - Spec Driven Development for Developers and AI Agents.\n\n"
            "Shotgun writes codebase-aware specs for your AI coding agents so they don't derail.\n\n"
            "It will guide you to doing codebase research -> building a spec -> an implementation plan -> a task list.\n\n"
            'Once you have all of that you can either use Shotgun Autopilot ("/" + autopilot) to automate implementing '
            "with Claude Code or just prompt your AI Coding Agent directly."
        )
        yield Markdown(intro, classes="welcome-intro")

        # Getting started button
        with Horizontal(classes="getting-started-row"):
            yield Button(
                "Getting started guide",
                id="welcome-getting-started",
                classes="action-btn",
                variant="default",
            )

        # Checklist #1: Index
        if s.is_home_directory:
            yield Static(
                "[dim]☐ [strike]Index this folder[/strike] (start in a project directory, not home)[/dim]",
                classes="checklist-item",
                markup=True,
            )
        elif s.is_indexed:
            yield Static(
                "[green]✔[/green] [dim strike]Index this folder[/dim strike]",
                classes="checklist-item",
                markup=True,
            )
        else:
            yield Static("☐ Index this folder", classes="checklist-item", markup=True)
            yield Static(
                "The codebase index lives on your computer, it costs nothing.",
                classes="checklist-note",
            )
            with Horizontal(classes="action-row"):
                yield Button(
                    "Index this folder",
                    id="welcome-index",
                    classes="action-btn",
                    variant="primary",
                )

        # Checklist #2: Context7
        if s.has_context7_key:
            yield Static(
                "[green]✔[/green] [dim strike]Set up Context7[/dim strike]",
                classes="checklist-item",
                markup=True,
            )
        else:
            yield Static("☐ Set up Context7", classes="checklist-item", markup=True)
            with Horizontal(classes="action-row"):
                yield Button(
                    "Set up Context7",
                    id="welcome-context7",
                    classes="action-btn",
                    variant="default",
                )

        # Checklist #3: Frontier model (hidden for Ollama)
        if not s.is_ollama:
            if s.is_frontier_model:
                yield Static(
                    "[green]✔[/green] [dim strike]Select a frontier model[/dim strike]",
                    classes="checklist-item",
                    markup=True,
                )
            elif s.frontier_model_label:
                yield Static(
                    "☐ Select a frontier model",
                    classes="checklist-item",
                    markup=True,
                )
                with Horizontal(classes="action-row"):
                    yield Button(
                        s.frontier_model_label,
                        id="welcome-select-model",
                        classes="action-btn",
                        variant="default",
                    )

        # Checklist #4: Gemini (BYOK only)
        if s.is_byok:
            if s.has_gemini_key:
                yield Static(
                    "[green]✔[/green] [dim strike]Set up Gemini key for web search[/dim strike]",
                    classes="checklist-item",
                    markup=True,
                )
            else:
                yield Static(
                    "☐ Set up Gemini key for web search",
                    classes="checklist-item",
                    markup=True,
                )
                with Horizontal(classes="action-row"):
                    yield Button(
                        "Set up Gemini key",
                        id="welcome-gemini",
                        classes="action-btn",
                        variant="default",
                    )

        # Footer
        yield Static(
            "These are 100% optional but make the spec much better and the experience much nicer.",
            classes="welcome-footer",
        )

    @on(Button.Pressed, "#welcome-getting-started")
    def _on_getting_started(self) -> None:
        self.post_message(self.WelcomeAction("getting_started"))

    @on(Button.Pressed, "#welcome-index")
    def _on_index(self) -> None:
        self.post_message(self.WelcomeAction("index"))

    @on(Button.Pressed, "#welcome-context7")
    def _on_context7(self) -> None:
        self.post_message(self.WelcomeAction("context7"))

    @on(Button.Pressed, "#welcome-select-model")
    def _on_select_model(self) -> None:
        self.post_message(
            self.WelcomeAction(
                "select_model", model_name=self.state.frontier_model_name
            )
        )

    @on(Button.Pressed, "#welcome-gemini")
    def _on_gemini(self) -> None:
        self.post_message(self.WelcomeAction("gemini_setup"))
