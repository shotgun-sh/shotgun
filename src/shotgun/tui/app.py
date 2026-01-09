from __future__ import annotations

import os
import platform
import sys
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from shotgun.codebase.core.errors import DatabaseIssue

from textual.app import App, SystemCommand
from textual.binding import Binding
from textual.screen import Screen

from shotgun.agents.agent_manager import AgentManager
from shotgun.agents.config import (
    ConfigManager,
    get_config_manager,
)
from shotgun.agents.models import AgentType
from shotgun.logging_config import get_logger
from shotgun.tui.containers import TUIContainer
from shotgun.tui.dependencies import create_default_router_deps
from shotgun.tui.screens.splash import SplashScreen
from shotgun.utils.file_system_utils import (
    ensure_shotgun_directory_exists,
    get_shotgun_base_path,
)
from shotgun.utils.update_checker import (
    detect_installation_method,
    perform_auto_update_async,
)

from .screens.chat import ChatScreen
from .screens.directory_setup import DirectorySetupScreen
from .screens.github_issue import GitHubIssueScreen
from .screens.model_picker import ModelPickerScreen
from .screens.pipx_migration import PipxMigrationScreen
from .screens.provider_config import ProviderConfigScreen
from .screens.welcome import WelcomeScreen

logger = get_logger(__name__)


class ShotgunApp(App[None]):
    # ChatScreen removed from SCREENS dict since it requires dependency injection
    # and is instantiated manually in refresh_startup_screen()
    # DirectorySetupScreen also removed since it requires error_message parameter
    SCREENS = {
        "provider_config": ProviderConfigScreen,
        "model_picker": ModelPickerScreen,
        "github_issue": GitHubIssueScreen,
    }
    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit the app"),
    ]

    CSS_PATH = "styles.tcss"

    def __init__(
        self,
        no_update_check: bool = False,
        continue_session: bool = False,
        force_reindex: bool = False,
        show_pull_hint: bool = False,
        pull_version_id: str | None = None,
        pending_db_issues: list[DatabaseIssue] | None = None,
    ) -> None:
        super().__init__()
        self.config_manager: ConfigManager = get_config_manager()
        self.no_update_check = no_update_check
        self.continue_session = continue_session
        self.force_reindex = force_reindex
        self.show_pull_hint = show_pull_hint
        self.pull_version_id = pull_version_id
        # Database issues detected at startup (locked, corrupted, timeout)
        # These will be shown to the user via dialogs when ChatScreen mounts
        self.pending_db_issues = pending_db_issues or []

        # Initialize dependency injection container
        self.container = TUIContainer()

        # Start async update check and install
        if not no_update_check:
            perform_auto_update_async(no_update_check=no_update_check)

    def on_mount(self) -> None:
        self.theme = "gruvbox"
        # Track TUI startup
        from shotgun.posthog_telemetry import track_event

        track_event(
            "tui_started",
            {
                "installation_method": detect_installation_method(),
                "terminal_width": self.size.width,
                "terminal_height": self.size.height,
            },
        )

        self.push_screen(
            SplashScreen(), callback=lambda _arg: self.refresh_startup_screen()
        )

    def refresh_startup_screen(self, skip_pipx_check: bool = False) -> None:
        """Push the appropriate screen based on configured providers."""
        # Check for pipx installation and show migration modal first
        if not skip_pipx_check:
            installation_method = detect_installation_method()
            if installation_method == "pipx":
                if isinstance(self.screen, PipxMigrationScreen):
                    return

                # Show pipx migration modal as a blocking modal screen
                self.push_screen(
                    PipxMigrationScreen(),
                    callback=lambda _arg: self.refresh_startup_screen(
                        skip_pipx_check=True
                    ),
                )
                return

        # Run async config loading in worker
        async def _check_config() -> None:
            # Show welcome screen if no providers are configured OR if user hasn't seen it yet
            # Note: If config migration fails, ConfigManager will auto-create fresh config
            # and set migration_failed flag, which WelcomeScreen will display
            config = await self.config_manager.load()

            has_any_key = await self.config_manager.has_any_provider_key()
            if not has_any_key or not config.shown_welcome_screen:
                if isinstance(self.screen, WelcomeScreen):
                    return

                self.push_screen(
                    WelcomeScreen(),
                    callback=lambda _arg: self.refresh_startup_screen(),
                )
                return

            # Try to create .shotgun directory if it doesn't exist
            if not self.check_local_shotgun_directory_exists():
                try:
                    path = ensure_shotgun_directory_exists()
                    # Verify directory was created successfully
                    if not path.is_dir():
                        # Show error screen if creation failed
                        if isinstance(self.screen, DirectorySetupScreen):
                            return
                        self.push_screen(
                            DirectorySetupScreen(
                                error_message="Unable to create .shotgun directory due to filesystem conflict."
                            ),
                            callback=lambda _arg: self.refresh_startup_screen(),
                        )
                        return
                except Exception as exc:
                    # Show error screen if creation failed with exception
                    if isinstance(self.screen, DirectorySetupScreen):
                        return
                    self.push_screen(
                        DirectorySetupScreen(error_message=str(exc)),
                        callback=lambda _arg: self.refresh_startup_screen(),
                    )
                    return

            if isinstance(self.screen, ChatScreen):
                return

            # If we have a version to pull, show pull screen first
            if self.pull_version_id:
                from .screens.spec_pull import SpecPullScreen

                self.push_screen(
                    SpecPullScreen(self.pull_version_id),
                    callback=self._handle_pull_complete,
                )
                return

            # Create ChatScreen with all dependencies injected from container
            # Get the default agent mode (ROUTER)
            agent_mode = AgentType.ROUTER

            # Create RouterDeps asynchronously (get_provider_model is now async)
            agent_deps = await create_default_router_deps()

            # Create AgentManager with async initialization
            agent_manager = AgentManager(deps=agent_deps, initial_type=agent_mode)

            # Create ProcessingStateManager - we'll pass the screen after creation
            # For now, create with None and the ChatScreen will set itself
            chat_screen = ChatScreen(
                agent_manager=agent_manager,
                conversation_manager=self.container.conversation_manager(),
                conversation_service=self.container.conversation_service(),
                widget_coordinator=self.container.widget_coordinator_factory(
                    screen=None
                ),
                processing_state=self.container.processing_state_factory(
                    screen=None,  # Will be set after ChatScreen is created
                    telemetry_context={"agent_mode": agent_mode.value},
                ),
                command_handler=self.container.command_handler(),
                placeholder_hints=self.container.placeholder_hints(),
                codebase_sdk=self.container.codebase_sdk(),
                deps=agent_deps,
                continue_session=self.continue_session,
                force_reindex=self.force_reindex,
                show_pull_hint=self.show_pull_hint,
            )

            # Update the ProcessingStateManager and WidgetCoordinator with the actual ChatScreen instance
            chat_screen.processing_state.screen = chat_screen
            chat_screen.widget_coordinator.screen = chat_screen

            self.push_screen(chat_screen)

        # Run the async config check in a worker
        self.run_worker(_check_config(), exclusive=False)

    def check_local_shotgun_directory_exists(self) -> bool:
        shotgun_dir = get_shotgun_base_path()
        return shotgun_dir.exists() and shotgun_dir.is_dir()

    def _handle_pull_complete(self, success: bool | None) -> None:
        """Handle completion of spec pull screen.

        Args:
            success: Whether the pull was successful, or None if dismissed.
        """
        # Clear version_id so we don't pull again on next refresh
        self.pull_version_id = None

        if success:
            # Enable hint for ChatScreen
            self.show_pull_hint = True

        # Continue to ChatScreen
        self.refresh_startup_screen()

    async def action_quit(self) -> None:
        """Quit the application."""
        # Shut down PostHog client to prevent threading errors
        from shotgun.posthog_telemetry import shutdown

        shutdown()
        self.exit()

    def get_system_commands(self, screen: Screen[Any]) -> Iterable[SystemCommand]:
        return [
            SystemCommand(
                "New Issue",
                "Report a bug or request a feature on GitHub",
                self.action_new_issue,
            )
        ]

    def action_new_issue(self) -> None:
        """Open GitHub issue screen to guide users to create an issue."""
        self.push_screen(GitHubIssueScreen())


def _log_startup_info() -> None:
    """Log startup information for debugging purposes."""
    # Import here to avoid circular import (shotgun.__init__ imports from submodules)
    from shotgun import __version__

    logger.info("=" * 60)
    logger.info("Shotgun TUI Starting")
    logger.info("=" * 60)
    logger.info(f"  Version: {__version__}")
    logger.info(f"  Python: {sys.version.split()[0]}")
    logger.info(f"  Platform: {platform.system()} {platform.release()}")
    logger.info(f"  Architecture: {platform.machine()}")
    logger.info(f"  Working Directory: {os.getcwd()}")
    logger.info("=" * 60)


def run(
    no_update_check: bool = False,
    continue_session: bool = False,
    force_reindex: bool = False,
    show_pull_hint: bool = False,
    pull_version_id: str | None = None,
) -> None:
    """Run the TUI application.

    Args:
        no_update_check: If True, disable automatic update checks.
        continue_session: If True, continue from previous conversation.
        force_reindex: If True, force re-indexing of codebase (ignores existing index).
        show_pull_hint: If True, show hint about recently pulled spec.
        pull_version_id: If provided, pull this spec version before showing ChatScreen.
    """
    # Log startup information
    _log_startup_info()

    # Detect database issues BEFORE starting the TUI (but don't auto-delete)
    # Issues will be presented to the user via dialogs once the TUI is running
    import asyncio

    from shotgun.codebase.core.errors import KuzuErrorType
    from shotgun.codebase.core.manager import CodebaseGraphManager
    from shotgun.utils import get_shotgun_home

    storage_dir = get_shotgun_home() / "codebases"
    manager = CodebaseGraphManager(storage_dir)

    pending_db_issues: list[DatabaseIssue] = []
    try:
        # First pass: 10-second timeout
        issues = asyncio.run(manager.detect_database_issues(timeout_seconds=10.0))
        if issues:
            # Categorize issues for logging
            for issue in issues:
                logger.info(
                    f"Detected database issue: {issue.graph_id} - "
                    f"{issue.error_type.value}: {issue.message}"
                )

            # Only pass issues that require user interaction to the TUI
            # Schema issues (incomplete builds) can be auto-cleaned silently
            user_facing_issues = [
                i
                for i in issues
                if i.error_type
                in (
                    KuzuErrorType.LOCKED,
                    KuzuErrorType.CORRUPTION,
                    KuzuErrorType.TIMEOUT,
                )
            ]

            # Auto-delete schema issues (incomplete builds) - safe to remove
            schema_issues = [i for i in issues if i.error_type == KuzuErrorType.SCHEMA]
            for issue in schema_issues:
                asyncio.run(manager.delete_database(issue.graph_id))
                logger.info(f"Auto-removed incomplete database: {issue.graph_id}")

            pending_db_issues = user_facing_issues
    except Exception as e:
        logger.error(f"Failed to detect database issues: {e}")
        # Continue anyway - the TUI can still function

    app = ShotgunApp(
        no_update_check=no_update_check,
        continue_session=continue_session,
        force_reindex=force_reindex,
        show_pull_hint=show_pull_hint,
        pull_version_id=pull_version_id,
        pending_db_issues=pending_db_issues,
    )
    app.run(inline_no_clear=True)


def serve(
    host: str = "localhost",
    port: int = 8000,
    public_url: str | None = None,
    no_update_check: bool = False,
    continue_session: bool = False,
    force_reindex: bool = False,
) -> None:
    """Serve the TUI application as a web application.

    Args:
        host: Host address for the web server.
        port: Port number for the web server.
        public_url: Public URL if behind a proxy.
        no_update_check: If True, disable automatic update checks.
        continue_session: If True, continue from previous conversation.
        force_reindex: If True, force re-indexing of codebase (ignores existing index).
    """
    # Detect database issues BEFORE starting the TUI
    # Note: In serve mode, issues are logged but user interaction happens in
    # the spawned process via run()
    import asyncio

    from textual_serve.server import Server

    from shotgun.codebase.core.errors import KuzuErrorType
    from shotgun.codebase.core.manager import CodebaseGraphManager
    from shotgun.utils import get_shotgun_home

    storage_dir = get_shotgun_home() / "codebases"
    manager = CodebaseGraphManager(storage_dir)

    try:
        issues = asyncio.run(manager.detect_database_issues(timeout_seconds=10.0))
        if issues:
            for issue in issues:
                logger.info(
                    f"Detected database issue: {issue.graph_id} - "
                    f"{issue.error_type.value}: {issue.message}"
                )
            # Auto-delete only schema issues (incomplete builds)
            schema_issues = [i for i in issues if i.error_type == KuzuErrorType.SCHEMA]
            for issue in schema_issues:
                asyncio.run(manager.delete_database(issue.graph_id))
                logger.info(f"Auto-removed incomplete database: {issue.graph_id}")
    except Exception as e:
        logger.error(f"Failed to detect database issues: {e}")
        # Continue anyway - the TUI can still function

    # Create a new event loop after asyncio.run() closes the previous one
    # This is needed for the Server.serve() method
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Build the command string based on flags
    command = "shotgun"
    if no_update_check:
        command += " --no-update-check"
    if continue_session:
        command += " --continue"
    if force_reindex:
        command += " --force-reindex"

    # Create and start the server with hardcoded title and debug=False
    server = Server(
        command=command,
        host=host,
        port=port,
        title="The Shotgun",
        public_url=public_url,
    )

    # Set up graceful shutdown on SIGTERM/SIGINT
    import signal
    import sys

    def signal_handler(_signum: int, _frame: Any) -> None:
        """Handle shutdown signals gracefully."""
        from shotgun.posthog_telemetry import shutdown

        logger.info("Received shutdown signal, cleaning up...")
        # Restore stdout/stderr before shutting down
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        shutdown()
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Suppress the textual-serve banner by redirecting stdout/stderr
    import io

    # Capture and suppress the banner, but show the actual serving URL
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    captured_output = io.StringIO()
    sys.stdout = captured_output
    sys.stderr = captured_output

    try:
        # This will print the banner to our captured output
        import logging

        # Temporarily set logging to ERROR level to suppress INFO messages
        textual_serve_logger = logging.getLogger("textual_serve")
        original_level = textual_serve_logger.level
        textual_serve_logger.setLevel(logging.ERROR)

        # Print our own message to the original stdout
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        print(f"Serving Shotgun TUI at http://{host}:{port}")
        print("Press Ctrl+C to quit")

        # Now suppress output again for the serve call
        sys.stdout = captured_output
        sys.stderr = captured_output

        server.serve(debug=False)
    finally:
        # Restore original stdout/stderr
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        if "textual_serve_logger" in locals():
            textual_serve_logger.setLevel(original_level)


if __name__ == "__main__":
    run()
