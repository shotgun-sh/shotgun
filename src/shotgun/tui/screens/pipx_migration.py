"""Migration notice screen for pipx users."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Markdown

if TYPE_CHECKING:
    pass


class PipxMigrationScreen(ModalScreen[None]):
    """Modal screen warning pipx users about migration to uvx."""

    CSS = """
        PipxMigrationScreen {
            align: center middle;
        }

        #migration-container {
            width: 90;
            height: auto;
            max-height: 90%;
            border: thick $error;
            background: $surface;
            padding: 2;
        }

        #migration-content {
            height: 1fr;
            padding: 1 0;
        }

        #buttons-container {
            height: auto;
            padding: 2 0 1 0;
        }

        #action-buttons {
            width: 100%;
            height: auto;
            align: center middle;
        }

        .action-button {
            margin: 0 1;
            min-width: 20;
        }
    """

    BINDINGS = [
        ("escape", "dismiss", "Continue Anyway"),
        ("ctrl+c", "app.quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        """Compose the migration notice modal."""
        with Container(id="migration-container"):
            with VerticalScroll(id="migration-content"):
                yield Markdown(
                    """
## We've Switched to uvx

We've switched from `pipx` to `uvx` as the primary installation method due to critical build issues with our `kuzu` dependency.

### The Problem
Users with pipx encounter cmake build errors during installation because pip falls back to building from source instead of using pre-built binary wheels.

### The Solution: uvx
- ✅ **No build tools required** - Binary wheels enforced
- ✅ **10-100x faster** - Much faster than pipx
- ✅ **Better reliability** - No cmake/build errors

### How to Migrate

**1. Uninstall shotgun-sh from pipx:**
```bash
pipx uninstall shotgun-sh
```

**2. Install uv:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```
Or with Homebrew: `brew install uv`

**3. Run shotgun-sh with uvx:**
```bash
uvx shotgun-sh
```
Or install permanently: `uv tool install shotgun-sh`

---

### Need Help?

**Discord:** https://discord.gg/5RmY6J2N7s

**Full Migration Guide:** https://github.com/shotgun-sh/shotgun/blob/main/docs/PIPX_MIGRATION.md
"""
                )

                with Container(id="buttons-container"):
                    with Horizontal(id="action-buttons"):
                        yield Button(
                            "Copy Instructions to Clipboard",
                            variant="default",
                            id="copy-instructions",
                            classes="action-button",
                        )
                        yield Button(
                            "Continue Anyway",
                            variant="primary",
                            id="continue",
                            classes="action-button",
                        )

    def on_mount(self) -> None:
        """Focus the continue button and ensure scroll starts at top."""
        self.query_one("#continue", Button).focus()
        self.query_one("#migration-content", VerticalScroll).scroll_home(animate=False)

    @on(Button.Pressed, "#copy-instructions")
    def _copy_instructions(self) -> None:
        """Copy all migration instructions to clipboard."""
        instructions = """# Step 1: Uninstall from pipx
pipx uninstall shotgun-sh

# Step 2: Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Step 3: Run shotgun with uvx
uvx shotgun-sh"""
        try:
            import pyperclip  # type: ignore[import-untyped]  # noqa: PGH003

            pyperclip.copy(instructions)
            self.notify("Copied migration instructions to clipboard!")
        except ImportError:
            self.notify(
                "Clipboard not available. See instructions above.",
                severity="warning",
            )

    @on(Button.Pressed, "#continue")
    def _continue(self) -> None:
        """Dismiss the modal and continue."""
        self.dismiss()
