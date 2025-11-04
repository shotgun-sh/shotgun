"""Shotgun Account authentication screen."""

import asyncio
import webbrowser
from typing import TYPE_CHECKING, cast

import httpx
from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Label, Markdown, Static
from textual.worker import Worker, WorkerState

from shotgun.agents.config import ConfigManager
from shotgun.logging_config import get_logger
from shotgun.shotgun_web import (
    ShotgunWebClient,
    TokenStatus,
)
from shotgun.shotgun_web.constants import DEFAULT_POLL_INTERVAL_SECONDS

if TYPE_CHECKING:
    from ..app import ShotgunApp

logger = get_logger(__name__)


class ShotgunAuthScreen(Screen[bool]):
    """Screen for Shotgun Account authentication flow.

    Returns True if authentication was successful, False otherwise.
    """

    CSS = """
        ShotgunAuth {
            layout: vertical;
        }

        #titlebox {
            height: auto;
            margin: 2 0;
            padding: 1;
            border: hkey $border;
            content-align: center middle;

            & > * {
                text-align: center;
            }
        }

        #auth-title {
            padding: 1 0;
            text-style: bold;
            color: $text-accent;
        }

        #content {
            padding: 2;
            height: auto;
        }

        #status {
            padding: 1 0;
            text-align: center;
        }

        #auth-url {
            padding: 1;
            border: solid $primary;
            background: $surface;
            text-align: center;
        }

        #actions {
            padding: 1;
            align: center middle;
        }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.token: str | None = None
        self.auth_url: str | None = None
        self.poll_worker: Worker[None] | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="titlebox"):
            yield Static("Shotgun Account Setup", id="auth-title")
            yield Static(
                "Authenticate with your Shotgun Account to get started",
                id="auth-subtitle",
            )

        with Vertical(id="content"):
            yield Label("Initializing...", id="status")
            yield Markdown("", id="auth-url")
            yield Markdown(
                "**Instructions:**\n"
                "1. A browser window will open automatically\n"
                "2. Sign in or create a Shotgun Account\n"
                "3. Complete payment if required\n"
                "4. This window will automatically detect completion",
                id="instructions",
            )

        with Vertical(id="actions"):
            yield Button("Cancel", variant="default", id="cancel")

    def on_mount(self) -> None:
        """Start authentication flow when screen is mounted."""
        self.run_worker(self._start_auth_flow(), exclusive=True)

    def action_cancel(self) -> None:
        """Cancel authentication and close screen."""
        if self.poll_worker and self.poll_worker.state == WorkerState.RUNNING:
            self.poll_worker.cancel()
        self.dismiss(False)

    @on(Button.Pressed, "#cancel")
    def _on_cancel_pressed(self) -> None:
        """Handle cancel button press."""
        self.action_cancel()

    @property
    def config_manager(self) -> ConfigManager:
        app = cast("ShotgunApp", self.app)
        return app.config_manager

    async def _start_auth_flow(self) -> None:
        """Start the authentication flow."""
        try:
            # Get shotgun instance ID from config
            shotgun_instance_id = await self.config_manager.get_shotgun_instance_id()
            logger.info("Starting auth flow with instance ID: %s", shotgun_instance_id)

            # Update status
            self.query_one("#status", Label).update(
                "🔄 Creating authentication token..."
            )

            # Create unification token
            client = ShotgunWebClient()
            response = client.create_unification_token(shotgun_instance_id)

            self.token = response.token
            self.auth_url = response.auth_url

            logger.info("Auth URL: %s", self.auth_url)

            # Update UI with auth URL
            self.query_one("#status", Label).update("✅ Authentication URL ready")
            self.query_one("#auth-url", Markdown).update(
                f"**Authentication URL:**\n\n[{self.auth_url}]({self.auth_url})"
            )

            # Try to open browser
            try:
                self.query_one("#status", Label).update("🌐 Opening browser...")
                webbrowser.open(self.auth_url)
                await asyncio.sleep(1)
                self.query_one("#status", Label).update(
                    "⏳ Waiting for authentication... (opened in browser)"
                )
            except Exception as e:
                logger.warning("Failed to open browser: %s", e)
                self.query_one("#status", Label).update(
                    "⚠️ Please click the link above to authenticate"
                )

            # Start polling for status
            self.poll_worker = self.run_worker(
                self._poll_token_status(), exclusive=False
            )

        except httpx.HTTPError as e:
            logger.error("Failed to create auth token: %s", e)
            self.query_one("#status", Label).update(
                f"❌ Error: Failed to create authentication token\n{e}"
            )
            self.notify("Failed to start authentication", severity="error")

        except Exception as e:
            logger.error("Unexpected error during auth flow: %s", e)
            self.query_one("#status", Label).update(f"❌ Unexpected error: {e}")
            self.notify("Authentication failed", severity="error")

    async def _poll_token_status(self) -> None:
        """Poll token status until completed or expired."""
        if not self.token:
            logger.error("No token available for polling")
            return

        client = ShotgunWebClient()
        poll_count = 0
        max_polls = 600  # 30 minutes with 3 second intervals

        while poll_count < max_polls:
            try:
                await asyncio.sleep(DEFAULT_POLL_INTERVAL_SECONDS)
                poll_count += 1

                logger.debug(
                    "Polling token status (attempt %d/%d)", poll_count, max_polls
                )

                status_response = client.check_token_status(self.token)

                if status_response.status == TokenStatus.COMPLETED:
                    # Success! Save keys and dismiss
                    logger.info("Authentication completed successfully")

                    if status_response.litellm_key and status_response.supabase_key:
                        await self.config_manager.update_shotgun_account(
                            api_key=status_response.litellm_key,
                            supabase_jwt=status_response.supabase_key,
                        )

                        self.query_one("#status", Label).update(
                            "✅ Authentication successful! Saving credentials..."
                        )
                        await asyncio.sleep(1)
                        self.notify(
                            "Shotgun Account configured successfully!",
                            severity="information",
                        )
                        self.dismiss(True)
                    else:
                        logger.error("Completed but missing keys")
                        self.query_one("#status", Label).update(
                            "❌ Error: Authentication completed but keys are missing"
                        )
                        self.notify("Authentication failed", severity="error")
                        await asyncio.sleep(3)
                        self.dismiss(False)
                    return

                elif status_response.status == TokenStatus.AWAITING_PAYMENT:
                    self.query_one("#status", Label).update(
                        "💳 Waiting for payment completion..."
                    )

                elif status_response.status == TokenStatus.EXPIRED:
                    logger.error("Token expired")
                    self.query_one("#status", Label).update(
                        "❌ Authentication token expired (30 minutes)\n"
                        "Please try again."
                    )
                    self.notify("Authentication token expired", severity="error")
                    await asyncio.sleep(3)
                    self.dismiss(False)
                    return

                elif status_response.status == TokenStatus.PENDING:
                    # Still waiting, update status message
                    elapsed_minutes = (poll_count * DEFAULT_POLL_INTERVAL_SECONDS) // 60
                    self.query_one("#status", Label).update(
                        f"⏳ Waiting for authentication... ({elapsed_minutes}m elapsed)"
                    )

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 410:
                    # Token expired
                    logger.error("Token expired (410)")
                    self.query_one("#status", Label).update(
                        "❌ Authentication token expired"
                    )
                    self.notify("Authentication token expired", severity="error")
                    await asyncio.sleep(3)
                    self.dismiss(False)
                    return
                else:
                    logger.error("HTTP error polling status: %s", e)
                    self.query_one("#status", Label).update(
                        f"❌ Error checking status: {e}"
                    )
                    await asyncio.sleep(5)  # Wait a bit longer on error

            except Exception as e:
                logger.error("Error polling token status: %s", e)
                self.query_one("#status", Label).update(f"⚠️ Error checking status: {e}")
                await asyncio.sleep(5)  # Wait a bit longer on error

        # Timeout reached
        logger.error("Polling timeout reached")
        self.query_one("#status", Label).update(
            "❌ Authentication timeout (30 minutes)\nPlease try again."
        )
        self.notify("Authentication timeout", severity="error")
        await asyncio.sleep(3)
        self.dismiss(False)
