"""Modal dialog for codebase indexing prompts."""

import os
from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Markdown, Static

from shotgun.utils.file_system_utils import get_shotgun_home


def _is_home_directory() -> bool:
    """Check if cwd is user's home directory.

    Can be simulated with HOME_DIRECTORY_SIMULATE=true env var for testing.
    """
    if os.environ.get("HOME_DIRECTORY_SIMULATE", "").lower() == "true":
        return True
    return Path.cwd() == Path.home()


def _track_event(event_name: str) -> None:
    """Track an event to PostHog."""
    from shotgun.posthog_telemetry import track_event

    track_event(event_name)


class CodebaseIndexPromptScreen(ModalScreen[bool]):
    """Modal dialog asking whether to index the detected codebase."""

    DEFAULT_CSS = """
        CodebaseIndexPromptScreen {
            align: center middle;
            background: rgba(0, 0, 0, 0.0);
        }

        CodebaseIndexPromptScreen > #index-prompt-dialog {
            width: 80%;
            max-width: 90;
            height: auto;
            max-height: 85%;
            border: wide $primary;
            padding: 1 2;
            layout: vertical;
            background: $surface;
        }

        #index-prompt-title {
            text-style: bold;
            color: $text-accent;
            text-align: center;
            padding-bottom: 1;
        }

        #index-prompt-content {
            height: auto;
            max-height: 1fr;
        }

        #index-prompt-info {
            padding: 0 1;
        }

        #index-prompt-buttons {
            layout: horizontal;
            align-horizontal: right;
            height: auto;
            padding-top: 1;
        }

        #index-prompt-buttons Button {
            margin: 0 1;
            min-width: 12;
        }

        #index-prompt-warning {
            background: $error;
            color: white;
            padding: 1 2;
            margin-bottom: 1;
            text-align: center;
        }
    """

    def compose(self) -> ComposeResult:
        storage_path = get_shotgun_home() / "codebases"
        cwd = Path.cwd()
        is_home = _is_home_directory()

        with Container(id="index-prompt-dialog"):
            if is_home:
                # Show warning for home directory
                yield Label(
                    "⚠️ Cannot index home directory",
                    id="index-prompt-title",
                )
                yield Static(
                    "You're running Shotgun from your home directory.\n"
                    "This would index your entire home folder which will take forever!\n\n"
                    "Please quit and restart Shotgun from inside a repository or project folder.",
                    id="index-prompt-warning",
                )
                with Container(id="index-prompt-buttons"):
                    yield Button(
                        "Continue without indexing",
                        id="index-prompt-continue",
                    )
                    yield Button("Quit", id="index-prompt-quit", variant="error")
            else:
                # Normal indexing prompt
                content = f"""
## 🔒 Your code never leaves your computer

Shotgun will index the codebase at:
**`{cwd}`**
_(This is the current working directory where you started Shotgun)_

### What happens during indexing:

- **Stays on your computer**: Index is stored locally at `{storage_path}` - it will not be stored on a server
- **Zero cost**: Indexing runs entirely on your machine
- **Runs in the background**: Usually takes 1-3 minutes, and you can continue using Shotgun while it indexes
- **Enable code understanding**: Allows Shotgun to answer questions about your codebase

---

If you're curious, you can review how Shotgun indexes/queries code by taking a look at the [source code](https://github.com/shotgun-sh/shotgun).

We take your privacy seriously. You can read our full [privacy policy](https://app.shotgun.sh/privacy) for more details.
"""
                yield Label(
                    "Want to index your codebase so Shotgun can understand it?",
                    id="index-prompt-title",
                )
                with VerticalScroll(id="index-prompt-content"):
                    yield Markdown(content, id="index-prompt-info")
                with Container(id="index-prompt-buttons"):
                    yield Button(
                        "Not now",
                        id="index-prompt-cancel",
                    )
                    yield Button(
                        "Index now",
                        id="index-prompt-confirm",
                        variant="primary",
                    )

    def on_mount(self) -> None:
        """Track when the home directory warning screen is shown."""
        if _is_home_directory():
            _track_event("home_directory_warning_shown")

    @on(Button.Pressed, "#index-prompt-cancel")
    def handle_cancel(self, event: Button.Pressed) -> None:
        event.stop()
        self.dismiss(False)

    @on(Button.Pressed, "#index-prompt-confirm")
    def handle_confirm(self, event: Button.Pressed) -> None:
        event.stop()
        self.dismiss(True)

    @on(Button.Pressed, "#index-prompt-continue")
    def handle_continue(self, event: Button.Pressed) -> None:
        """Continue without indexing when in home directory."""
        event.stop()
        _track_event("home_directory_warning_continue")
        self.dismiss(False)

    @on(Button.Pressed, "#index-prompt-quit")
    def handle_quit(self, event: Button.Pressed) -> None:
        event.stop()
        _track_event("home_directory_warning_quit")
        self.app.exit()
