"""Warning modal for Tier 1 Anthropic API keys."""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Markdown

from shotgun.tui.markdown import create_markdown_parser


class Tier1WarningModal(ModalScreen[bool]):
    """Warning modal shown when Tier 1 API key is detected."""

    DEFAULT_CSS = """
        Tier1WarningModal {
            align: center middle;
            background: rgba(0, 0, 0, 0.0);
        }

        Tier1WarningModal > #dialog-container {
            width: 60%;
            max-width: 70;
            border: wide $warning;
            padding: 1 2;
            background: $surface;
        }

        Tier1WarningModal #title {
            text-align: center;
            color: $warning;
            margin-bottom: 1;
        }

        Tier1WarningModal #message {
            margin-bottom: 1;
        }

        Tier1WarningModal #button-container {
            align: center middle;
            margin-top: 1;
        }

        Tier1WarningModal Button {
            min-width: 20;
        }
    """

    def compose(self) -> ComposeResult:
        """Compose the modal content."""
        with Vertical(id="dialog-container"):
            yield Label("⚠️  Tier 1 API Key Detected", id="title")
            yield Markdown(
                """Your Anthropic API key is on **Tier 1**, which has rate limits that are **too low for Shotgun to work properly**:

- **50 requests/minute** (RPM)
- **50,000 input tokens/minute** (ITPM)
- **10,000 output tokens/minute** (OTPM)

Shotgun's multi-agent workflow will hit these limits almost immediately, resulting in constant rate limit errors and a broken experience.

**To use Shotgun, you need to either:**

1. **Get a Shotgun Account** at [shotgun.sh](https://shotgun.sh) — uses a Tier 4 account, $10/month for $10 of usage
2. **Upgrade your Anthropic account** to Tier 2 or higher
""",
                id="message",
                parser_factory=create_markdown_parser,
            )
            with Vertical(id="button-container"):
                yield Button("I Understand", variant="primary", id="understand-button")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "understand-button":
            self.dismiss(True)
