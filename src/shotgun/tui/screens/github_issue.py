"""Screen for guiding users to create GitHub issues."""

import webbrowser

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Markdown, Static


class GitHubIssueScreen(ModalScreen[None]):
    """Guide users to create issues on GitHub."""

    CSS = """
        GitHubIssueScreen {
            align: center middle;
        }

        #issue-container {
            width: 70;
            max-width: 100;
            height: auto;
            border: thick $primary;
            background: $surface;
            padding: 2;
        }

        #issue-header {
            text-style: bold;
            color: $text-accent;
            padding-bottom: 1;
            text-align: center;
        }

        #issue-content {
            padding: 1 0;
        }

        #issue-buttons {
            height: auto;
            padding: 2 0 0 0;
            align: center middle;
        }

        #issue-buttons Button {
            margin: 1 1;
            min-width: 20;
        }
    """

    BINDINGS = [
        ("escape", "dismiss", "Close"),
    ]

    def compose(self) -> ComposeResult:
        """Compose the GitHub issue screen."""
        with Container(id="issue-container"):
            yield Static("Create a GitHub Issue", id="issue-header")
            with Vertical(id="issue-content"):
                yield Markdown(
                    """
## Report Bugs or Request Features

We track all bugs, feature requests, and improvements on GitHub Issues.

### How to Create an Issue:

1. Click the button below to open our GitHub Issues page
2. Click **"New Issue"**
3. Choose a template:
   - **Bug Report** - Report a bug or unexpected behavior
   - **Feature Request** - Suggest new functionality
   - **Documentation** - Report docs issues or improvements
4. Fill in the details and submit

We review all issues and will respond as soon as possible!

### Before Creating an Issue:

- Search existing issues to avoid duplicates
- Include steps to reproduce for bugs
- Be specific about what you'd like for feature requests
                    """,
                    id="issue-markdown",
                )
            with Vertical(id="issue-buttons"):
                yield Button(
                    "🐙 Open GitHub Issues", id="github-button", variant="primary"
                )
                yield Button("Close", id="close-button")

    @on(Button.Pressed, "#github-button")
    def handle_github(self) -> None:
        """Open GitHub issues page in browser."""
        webbrowser.open("https://github.com/shotgun-sh/shotgun/issues")
        self.notify("Opening GitHub Issues in your browser...")

    @on(Button.Pressed, "#close-button")
    def handle_close(self) -> None:
        """Handle close button press."""
        self.dismiss()
