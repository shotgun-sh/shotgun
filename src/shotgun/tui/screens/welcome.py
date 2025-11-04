"""Welcome screen for choosing between Shotgun Account and BYOK."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Markdown, Static

if TYPE_CHECKING:
    from ..app import ShotgunApp


class WelcomeScreen(Screen[None]):
    """Welcome screen for first-time setup."""

    CSS = """
        WelcomeScreen {
            layout: vertical;
            align: center middle;
        }

        #titlebox {
            width: 100%;
            height: auto;
            margin: 2 0;
            padding: 1;
            border: hkey $border;
            content-align: center middle;

            & > * {
                text-align: center;
            }
        }

        #welcome-title {
            padding: 1 0;
            text-style: bold;
            color: $text-accent;
        }

        #welcome-subtitle {
            padding: 0 1;
        }

        #options-container {
            width: 100%;
            height: auto;
            padding: 2;
            align: center middle;
        }

        #options {
            width: auto;
            height: auto;
        }

        .option-box {
            width: 45;
            height: auto;
            border: solid $primary;
            padding: 2;
            margin: 0 1;
            background: $surface;
        }

        .option-box:focus-within {
            border: solid $accent;
        }

        .option-title {
            text-style: bold;
            color: $text-accent;
            padding: 0 0 1 0;
        }

        .option-benefits {
            padding: 1 0;
        }

        .option-button {
            margin: 1 0 0 0;
            width: 100%;
        }
    """

    BINDINGS = [
        ("ctrl+c", "app.quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="titlebox"):
            yield Static("Welcome to Shotgun", id="welcome-title")
            yield Static(
                "Choose how you'd like to get started",
                id="welcome-subtitle",
            )

        with Container(id="options-container"):
            with Horizontal(id="options"):
                # Left box - Shotgun Account
                with Vertical(classes="option-box", id="shotgun-box"):
                    yield Static("Use a Shotgun Account", classes="option-title")
                    yield Markdown(
                        "**Benefits:**\n"
                        "• Use of all models in the Model Garden\n"
                        "• We'll pick the optimal models to give you the best "
                        "experience for things like web search, codebase indexing",
                        classes="option-benefits",
                    )
                    yield Button(
                        "Sign Up for/Use your Shotgun Account",
                        variant="primary",
                        id="shotgun-button",
                        classes="option-button",
                    )

                # Right box - BYOK
                with Vertical(classes="option-box", id="byok-box"):
                    yield Static("Bring Your Own Key (BYOK)", classes="option-title")
                    yield Markdown(
                        "**Benefits:**\n"
                        "• 100% Supported by the application\n"
                        "• Use your existing API keys from OpenAI, Anthropic, or Google",
                        classes="option-benefits",
                    )
                    yield Button(
                        "Configure API Keys",
                        variant="success",
                        id="byok-button",
                        classes="option-button",
                    )

    def on_mount(self) -> None:
        """Focus the first button on mount."""
        self.query_one("#shotgun-button", Button).focus()
        # Update BYOK button text asynchronously
        self.run_worker(self._update_byok_button_text(), exclusive=False)

    async def _update_byok_button_text(self) -> None:
        """Update BYOK button text based on whether user has existing providers."""
        byok_button = self.query_one("#byok-button", Button)
        app = cast("ShotgunApp", self.app)
        if await app.config_manager.has_any_provider_key():
            byok_button.label = "I'll stick with my BYOK setup"

    @on(Button.Pressed, "#shotgun-button")
    def _on_shotgun_pressed(self) -> None:
        """Handle Shotgun Account button press."""
        self.run_worker(self._start_shotgun_auth(), exclusive=True)

    @on(Button.Pressed, "#byok-button")
    def _on_byok_pressed(self) -> None:
        """Handle BYOK button press."""
        self.run_worker(self._start_byok_config(), exclusive=True)

    async def _start_byok_config(self) -> None:
        """Launch BYOK provider configuration flow."""
        await self._mark_welcome_shown()

        app = cast("ShotgunApp", self.app)

        # If user already has providers, just dismiss and continue to chat
        if await app.config_manager.has_any_provider_key():
            self.dismiss()
            return

        # Otherwise, push provider config screen and wait for result
        from .provider_config import ProviderConfigScreen

        await self.app.push_screen_wait(ProviderConfigScreen())

        # Dismiss welcome screen after config if providers are now configured
        if await app.config_manager.has_any_provider_key():
            self.dismiss()

    async def _start_shotgun_auth(self) -> None:
        """Launch Shotgun Account authentication flow."""
        from .shotgun_auth import ShotgunAuthScreen

        # Mark welcome screen as shown before auth
        await self._mark_welcome_shown()

        # Push the auth screen and wait for result
        await self.app.push_screen_wait(ShotgunAuthScreen())

        # Dismiss welcome screen after auth
        self.dismiss()

    async def _mark_welcome_shown(self) -> None:
        """Mark the welcome screen as shown in config."""
        app = cast("ShotgunApp", self.app)
        config = await app.config_manager.load()
        config.shown_welcome_screen = True
        await app.config_manager.save(config)
