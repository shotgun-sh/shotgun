"""Modal dialog for codebase indexing prompts."""

import os
import webbrowser
from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, VerticalScroll
from textual.events import Resize
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Markdown, Static

from shotgun.utils.file_system_utils import get_shotgun_home

# Use a higher threshold than the global default since this dialog has more content
INDEX_PROMPT_COMPACT_THRESHOLD = 45


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
            border: none;
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
            background: $surface-lighten-1;
            color: $text;
            padding: 1 2;
            margin-bottom: 1;
            text-align: center;
        }

        #compact-link {
            text-align: center;
            padding: 1 0;
            display: none;
        }

        /* Compact styles for short terminals */
        #index-prompt-dialog.compact {
            padding: 0 1;
            border: none;
            max-height: 100%;
        }

        #index-prompt-dialog.compact #index-prompt-content {
            display: none;
        }

        #index-prompt-dialog.compact #compact-link {
            display: block;
        }

        #index-prompt-dialog.compact #index-prompt-warning {
            padding: 0;
            margin-bottom: 0;
            background: transparent;
        }

        #index-prompt-dialog.compact #index-prompt-title {
            padding-bottom: 0;
        }

        #index-prompt-dialog.compact #index-prompt-buttons {
            padding-top: 0;
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
                    "Home directory detected",
                    id="index-prompt-title",
                )
                yield Static(
                    "Running from home directory isn't recommended.",
                    id="index-prompt-warning",
                )
                with Container(id="index-prompt-buttons"):
                    yield Button(
                        "Quit",
                        id="index-prompt-quit",
                    )
                    yield Button(
                        "Continue without indexing",
                        id="index-prompt-continue",
                    )
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
                    "Want to index your codebase?",
                    id="index-prompt-title",
                )
                # Compact mode: show only a link
                yield Static(
                    "[@click=screen.open_faq]Learn more about indexing[/]",
                    id="compact-link",
                    markup=True,
                )
                # Full mode: show detailed content
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
        """Track when the home directory warning screen is shown and apply compact layout."""
        if _is_home_directory():
            _track_event("home_directory_warning_shown")
        # Apply compact layout if starting in a short terminal
        self._apply_compact_layout(
            self.app.size.height < INDEX_PROMPT_COMPACT_THRESHOLD
        )

    @on(Resize)
    def handle_resize(self, event: Resize) -> None:
        """Adjust layout based on terminal height."""
        self._apply_compact_layout(event.size.height < INDEX_PROMPT_COMPACT_THRESHOLD)

    def _apply_compact_layout(self, compact: bool) -> None:
        """Apply or remove compact layout classes for short terminals."""
        dialog = self.query_one("#index-prompt-dialog")
        if compact:
            dialog.add_class("compact")
        else:
            dialog.remove_class("compact")

    def action_open_faq(self) -> None:
        """Open the FAQ page in a browser."""
        webbrowser.open("https://github.com/shotgun-sh/shotgun?tab=readme-ov-file#faq")

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
