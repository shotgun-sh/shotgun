from collections.abc import Iterable
from typing import Any

from textual.app import App, SystemCommand
from textual.binding import Binding
from textual.screen import Screen

from shotgun.agents.config import ConfigManager, get_config_manager
from shotgun.logging_config import get_logger
from shotgun.tui.screens.splash import SplashScreen
from shotgun.utils.file_system_utils import get_shotgun_base_path
from shotgun.utils.update_checker import perform_auto_update_async

from .screens.chat import ChatScreen
from .screens.directory_setup import DirectorySetupScreen
from .screens.provider_config import ProviderConfigScreen

logger = get_logger(__name__)


class ShotgunApp(App[None]):
    SCREENS = {
        "chat": ChatScreen,
        "provider_config": ProviderConfigScreen,
        "directory_setup": DirectorySetupScreen,
    }
    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit the app"),
    ]
    CSS_PATH = "styles.tcss"

    def __init__(
        self, no_update_check: bool = False, continue_session: bool = False
    ) -> None:
        super().__init__()
        self.config_manager: ConfigManager = get_config_manager()
        self.no_update_check = no_update_check
        self.continue_session = continue_session

        # Start async update check and install
        if not no_update_check:
            perform_auto_update_async(no_update_check=no_update_check)

    def on_mount(self) -> None:
        self.theme = "gruvbox"
        # Track TUI startup
        from shotgun.posthog_telemetry import track_event

        track_event("tui_started", {})

        self.push_screen(
            SplashScreen(), callback=lambda _arg: self.refresh_startup_screen()
        )

    def refresh_startup_screen(self) -> None:
        """Push the appropriate screen based on configured providers."""
        if not self.config_manager.has_any_provider_key():
            if isinstance(self.screen, ProviderConfigScreen):
                return

            self.push_screen(
                "provider_config", callback=lambda _arg: self.refresh_startup_screen()
            )
            return

        if not self.check_local_shotgun_directory_exists():
            if isinstance(self.screen, DirectorySetupScreen):
                return

            self.push_screen(
                "directory_setup", callback=lambda _arg: self.refresh_startup_screen()
            )
            return

        if isinstance(self.screen, ChatScreen):
            return
        # Pass continue_session flag to ChatScreen
        self.push_screen(ChatScreen(continue_session=self.continue_session))

    def check_local_shotgun_directory_exists(self) -> bool:
        shotgun_dir = get_shotgun_base_path()
        return shotgun_dir.exists() and shotgun_dir.is_dir()

    async def action_quit(self) -> None:
        """Quit the application."""
        # Shut down PostHog client to prevent threading errors
        from shotgun.posthog_telemetry import shutdown

        shutdown()
        self.exit()

    def get_system_commands(self, screen: Screen[Any]) -> Iterable[SystemCommand]:
        return []  # we don't want any system commands


def run(no_update_check: bool = False, continue_session: bool = False) -> None:
    """Run the TUI application.

    Args:
        no_update_check: If True, disable automatic update checks.
        continue_session: If True, continue from previous conversation.
    """
    # Clean up any corrupted databases BEFORE starting the TUI
    # This prevents crashes from corrupted databases during initialization
    import asyncio

    from shotgun.codebase.core.manager import CodebaseGraphManager
    from shotgun.utils import get_shotgun_home

    storage_dir = get_shotgun_home() / "codebases"
    manager = CodebaseGraphManager(storage_dir)

    try:
        removed = asyncio.run(manager.cleanup_corrupted_databases())
        if removed:
            logger.info(
                f"Cleaned up {len(removed)} corrupted database(s) before TUI startup"
            )
    except Exception as e:
        logger.error(f"Failed to cleanup corrupted databases: {e}")
        # Continue anyway - the TUI can still function

    app = ShotgunApp(no_update_check=no_update_check, continue_session=continue_session)
    app.run(inline_no_clear=True)


if __name__ == "__main__":
    run()
