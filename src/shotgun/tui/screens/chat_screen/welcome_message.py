"""Welcome message widget for onboarding checklist."""

import os
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, SecretStr
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Static

from shotgun.logging_config import get_logger
from shotgun.tui.markdown import Markdown

logger = get_logger(__name__)


class WelcomeActionType(StrEnum):
    """Action types for welcome widget buttons."""

    INDEX = "index"
    CONTEXT7 = "context7"
    SELECT_MODEL = "select_model"
    GEMINI_SETUP = "gemini_setup"
    GETTING_STARTED = "getting_started"


def _has_secret_key(secret: SecretStr | None) -> bool:
    """Return True if the secret contains a non-empty value."""
    return bool(secret and secret.get_secret_value())


class WelcomeMessage(BaseModel):
    """Data model capturing the welcome state snapshot."""

    kind: Literal["welcome"] = "welcome"
    is_home_directory: bool = False
    is_indexed: bool = False
    is_indexing: bool = False
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
    has_context7_key = _has_secret_key(config.context7.api_key)

    # Determine account type
    is_shotgun_account = config_manager.provider_has_api_key(config.shotgun)
    is_ollama = config.ollama.enabled

    # Check BYOK provider keys
    has_anthropic = _has_secret_key(config.anthropic.api_key)
    has_openai = _has_secret_key(config.openai.api_key)
    has_google = _has_secret_key(config.google.api_key)

    is_byok = has_anthropic or has_openai or has_google

    # Gemini key for web search
    has_gemini_key = has_google

    # Determine frontier model
    is_frontier_model = False
    frontier_model_label = ""
    frontier_model_name = ""

    frontier_models = {
        ModelName.CLAUDE_OPUS_4_6,
        ModelName.GPT_5_2,
        ModelName.GPT_5_4,
        ModelName.GPT_5_4_PRO,
        ModelName.GEMINI_3_1_PRO_PREVIEW,
    }

    if config.selected_model and config.selected_model in frontier_models:
        is_frontier_model = True
    elif not is_ollama:
        # Determine best available frontier model
        if is_shotgun_account:
            frontier_model_label = "Select Opus 4.6"
            frontier_model_name = ModelName.CLAUDE_OPUS_4_6
        elif has_anthropic:
            frontier_model_label = "Select Opus 4.6"
            frontier_model_name = ModelName.CLAUDE_OPUS_4_6
        elif has_openai:
            frontier_model_label = "Select GPT-5.2"
            frontier_model_name = ModelName.GPT_5_2
        elif has_google:
            frontier_model_label = "Select Gemini 3.1 Pro"
            frontier_model_name = ModelName.GEMINI_3_1_PRO_PREVIEW

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


class ActionLink(Static):
    """A thin clickable link-style button (1 line tall)."""

    DEFAULT_CSS = """
        ActionLink {
            width: auto;
            height: auto;
            padding: 0 1;
            color: $text;
            background: $primary;
            text-style: bold;
            border: tall $primary;
        }

        ActionLink:hover {
            background: $primary-lighten-1;
            border: tall $primary-lighten-1;
        }

        ActionLink.-success {
            background: $success;
            border: tall $success;
        }

        ActionLink.-success:hover {
            background: $success-lighten-1;
            border: tall $success-lighten-1;
        }
    """

    can_focus = True

    class Clicked(Message):
        """Posted when the link is clicked."""

        def __init__(self, link: "ActionLink") -> None:
            super().__init__()
            self.link = link

        @property
        def control(self) -> "ActionLink":
            """The ActionLink that was clicked."""
            return self.link

    def __init__(
        self, label: str, *, id: str | None = None, classes: str | None = None
    ) -> None:
        super().__init__(label, id=id, classes=classes, markup=False)

    def on_click(self) -> None:
        self.post_message(self.Clicked(self))


class WelcomeWidget(Widget):
    """Interactive onboarding checklist widget."""

    DEFAULT_CSS = """
        WelcomeWidget {
            background: $secondary-background-darken-1;
            height: auto;
            margin: 1;
            margin-left: 1;
            padding: 1 2;
        }

        WelcomeWidget .welcome-intro {
            height: auto;
            padding: 0;
            margin: 0 0 1 0;
        }

        WelcomeWidget .getting-started-row {
            height: auto;
            width: auto;
            margin: 0 0 0 0;
        }

        WelcomeWidget .section-header {
            height: auto;
            padding: 0;
            margin: 1 0 0 0;
            color: $text;
        }

        WelcomeWidget .checklist-group {
            height: auto;
            margin: 0 0 1 0;
        }

        WelcomeWidget .checklist-row {
            height: auto;
            width: 100%;
            margin: 0 0 0 1;
        }

        WelcomeWidget .checklist-label {
            height: auto;
            width: auto;
            padding: 0;
        }

        WelcomeWidget .checklist-note {
            height: auto;
            padding: 0;
            margin: 0 0 0 5;
            color: $text-muted;
        }

        WelcomeWidget ActionLink {
            margin: 0 0 0 2;
        }

        WelcomeWidget .getting-started-link {
            margin: 0 0 0 0;
        }

        WelcomeWidget .welcome-footer {
            height: auto;
            padding: 0;
            margin: 0;
            color: $text-muted;
        }
    """

    class WelcomeAction(Message):
        """Posted when a welcome button is clicked."""

        def __init__(self, action: WelcomeActionType, model_name: str = "") -> None:
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

        # Getting started link
        with Horizontal(classes="getting-started-row"):
            yield ActionLink(
                "Getting started guide",
                id="welcome-getting-started",
                classes="getting-started-link -success",
            )

        # Section header
        yield Static(
            "[bold]Get the most out of Shotgun:[/bold]",
            classes="section-header",
            markup=True,
        )

        # Checklist #1: Index
        with Vertical(classes="checklist-group"):
            if s.is_home_directory:
                with Horizontal(classes="checklist-row"):
                    yield Static(
                        "[dim]☐ [strike]Index this folder[/strike] (start in a project directory, not home)[/dim]",
                        classes="checklist-label",
                        markup=True,
                    )
            elif s.is_indexed:
                with Horizontal(classes="checklist-row"):
                    yield Static(
                        "[green]✔[/green] [dim strike]Index this folder[/dim strike]",
                        classes="checklist-label",
                        markup=True,
                    )
            elif s.is_indexing:
                with Horizontal(classes="checklist-row"):
                    yield Static(
                        "⏳ Indexing in progress…",
                        classes="checklist-label",
                        markup=True,
                    )
            else:
                with Horizontal(classes="checklist-row"):
                    yield Static(
                        "☐ Index this folder",
                        classes="checklist-label",
                        markup=True,
                    )
                    yield ActionLink(
                        "Index this folder",
                        id="welcome-index",
                        classes="-success",
                    )
                yield Static(
                    "The codebase index lives on your computer, it costs nothing.",
                    classes="checklist-note",
                )

        # Checklist #2: Context7
        with Vertical(classes="checklist-group"):
            if s.has_context7_key:
                with Horizontal(classes="checklist-row"):
                    yield Static(
                        "[green]✔[/green] [dim strike]Set up Context7[/dim strike]",
                        classes="checklist-label",
                        markup=True,
                    )
            else:
                with Horizontal(classes="checklist-row"):
                    yield Static(
                        "☐ Set up Context7",
                        classes="checklist-label",
                        markup=True,
                    )
                    yield ActionLink(
                        "Set up Context7",
                        id="welcome-context7",
                    )

        # Checklist #3: Frontier model (hidden for Ollama)
        if not s.is_ollama:
            with Vertical(classes="checklist-group"):
                if s.is_frontier_model:
                    with Horizontal(classes="checklist-row"):
                        yield Static(
                            "[green]✔[/green] [dim strike]Select a frontier model[/dim strike]",
                            classes="checklist-label",
                            markup=True,
                        )
                elif s.frontier_model_label:
                    with Horizontal(classes="checklist-row"):
                        yield Static(
                            "☐ Select a frontier model",
                            classes="checklist-label",
                            markup=True,
                        )
                        yield ActionLink(
                            s.frontier_model_label,
                            id="welcome-select-model",
                        )

        # Checklist #4: Gemini (BYOK only)
        if s.is_byok:
            with Vertical(classes="checklist-group"):
                if s.has_gemini_key:
                    with Horizontal(classes="checklist-row"):
                        yield Static(
                            "[green]✔[/green] [dim strike]Set up Gemini for better/faster web search[/dim strike]",
                            classes="checklist-label",
                            markup=True,
                        )
                else:
                    with Horizontal(classes="checklist-row"):
                        yield Static(
                            "☐ Set up Gemini for better/faster web search",
                            classes="checklist-label",
                            markup=True,
                        )
                        yield ActionLink(
                            "Set up Gemini key",
                            id="welcome-gemini",
                        )

        # Footer
        yield Static(
            "These are 100% optional but make the spec much better and the experience much nicer.",
            classes="welcome-footer",
        )

    @on(ActionLink.Clicked, "#welcome-getting-started")
    def _on_getting_started(self) -> None:
        self.post_message(self.WelcomeAction(WelcomeActionType.GETTING_STARTED))

    @on(ActionLink.Clicked, "#welcome-index")
    def _on_index(self) -> None:
        self.post_message(self.WelcomeAction(WelcomeActionType.INDEX))

    @on(ActionLink.Clicked, "#welcome-context7")
    def _on_context7(self) -> None:
        self.post_message(self.WelcomeAction(WelcomeActionType.CONTEXT7))

    @on(ActionLink.Clicked, "#welcome-select-model")
    def _on_select_model(self) -> None:
        self.post_message(
            self.WelcomeAction(
                WelcomeActionType.SELECT_MODEL,
                model_name=self.state.frontier_model_name,
            )
        )

    @on(ActionLink.Clicked, "#welcome-gemini")
    def _on_gemini(self) -> None:
        self.post_message(self.WelcomeAction(WelcomeActionType.GEMINI_SETUP))
