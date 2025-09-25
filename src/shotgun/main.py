"""Main CLI application for shotgun."""

from typing import Annotated

import typer
from dotenv import load_dotenv

from shotgun import __version__
from shotgun.agents.config import get_config_manager
from shotgun.cli import codebase, config, export, plan, research, specify, tasks, update
from shotgun.logging_config import configure_root_logger, get_logger
from shotgun.posthog_telemetry import setup_posthog_observability
from shotgun.sentry_telemetry import setup_sentry_observability
from shotgun.telemetry import setup_logfire_observability
from shotgun.tui import app as tui_app
from shotgun.utils.update_checker import check_for_updates_async

# Load environment variables from .env file
load_dotenv()

# Initialize telemetry FIRST (before logging setup to prevent handler conflicts)
_logfire_enabled = setup_logfire_observability()

# Initialize logging AFTER telemetry
configure_root_logger()
logger = get_logger(__name__)
logger.debug("Logfire observability enabled: %s", _logfire_enabled)

# Initialize configuration
try:
    config_manager = get_config_manager()
    config_manager.load()  # Ensure config is loaded at startup
except Exception as e:
    logger.debug("Configuration initialization warning: %s", e)

# Initialize Sentry telemetry
_sentry_enabled = setup_sentry_observability()
logger.debug("Sentry observability enabled: %s", _sentry_enabled)

# Initialize PostHog analytics
_posthog_enabled = setup_posthog_observability()
logger.debug("PostHog analytics enabled: %s", _posthog_enabled)

# Global variable to store update notification
_update_notification: str | None = None


def _update_callback(notification: str) -> None:
    """Callback to store update notification."""
    global _update_notification
    _update_notification = notification


app = typer.Typer(
    name="shotgun",
    help="Shotgun - AI-powered CLI tool for research, planning, and task management",
    rich_markup_mode="rich",
)

# Add commands
app.add_typer(config.app, name="config", help="Manage Shotgun configuration")
app.add_typer(
    codebase.app, name="codebase", help="Manage and query code knowledge graphs"
)
app.add_typer(research.app, name="research", help="Perform research with agentic loops")
app.add_typer(plan.app, name="plan", help="Generate structured plans")
app.add_typer(specify.app, name="specify", help="Generate comprehensive specifications")
app.add_typer(tasks.app, name="tasks", help="Generate task lists with agentic approach")
app.add_typer(export.app, name="export", help="Export artifacts to various formats")
app.add_typer(update.app, name="update", help="Check for and install updates")


def version_callback(value: bool) -> None:
    """Show version and exit."""
    if value:
        from rich.console import Console

        console = Console()
        console.print(f"shotgun {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-v",
            callback=version_callback,
            is_eager=True,
            help="Show version and exit",
        ),
    ] = False,
    no_update_check: Annotated[
        bool,
        typer.Option(
            "--no-update-check",
            help="Disable automatic update checks",
        ),
    ] = False,
) -> None:
    """Shotgun - AI-powered CLI tool."""
    logger.debug("Starting shotgun CLI application")

    # Start async update check (non-blocking)
    if not ctx.resilient_parsing:
        check_for_updates_async(
            callback=_update_callback, no_update_check=no_update_check
        )

    if ctx.invoked_subcommand is None and not ctx.resilient_parsing:
        logger.debug("Launching shotgun TUI application")
        tui_app.run(no_update_check=no_update_check)

        # Show update notification after TUI exits
        if _update_notification:
            from rich.console import Console

            console = Console()
            console.print(f"\n[cyan]{_update_notification}[/cyan]", style="bold")

        raise typer.Exit()

    # For CLI commands, we'll show notification at the end
    # This is handled by registering an atexit handler
    if not ctx.resilient_parsing and ctx.invoked_subcommand is not None:
        import atexit

        def show_update_notification() -> None:
            if _update_notification:
                from rich.console import Console

                console = Console()
                console.print(f"\n[cyan]{_update_notification}[/cyan]", style="bold")

        atexit.register(show_update_notification)

        # Register PostHog shutdown handler
        def shutdown_posthog() -> None:
            from shotgun.posthog_telemetry import shutdown

            shutdown()

        atexit.register(shutdown_posthog)


if __name__ == "__main__":
    app()
