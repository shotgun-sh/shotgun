"""Main CLI application for shotgun."""

# NOTE: These are before we import any Google library to stop the noisy gRPC logs.
import os  # noqa: I001

os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GLOG_minloglevel"] = "2"

import logging

# CRITICAL: Add NullHandler to root logger before ANY other imports.
# This prevents Python from automatically adding a StreamHandler when
# WARNING/ERROR messages are logged by modules during import.
# DO NOT MOVE THIS BELOW OTHER IMPORTS.
logging.getLogger().addHandler(logging.NullHandler())

# ruff: noqa: E402 (module import not at top - intentionally after NullHandler setup)
from typing import Annotated

import typer
from dotenv import load_dotenv

from shotgun import __version__
from shotgun.agents.config import get_config_manager
from shotgun.cli import (
    clear,
    codebase,
    compact,
    config,
    context,
    feedback,
    run,
    spec,
    update,
)
from shotgun.logging_config import configure_root_logger, get_logger
from shotgun.posthog_telemetry import setup_posthog_observability
from shotgun.telemetry import setup_logfire_observability
from shotgun.tui import app as tui_app
from shotgun.utils.update_checker import perform_auto_update_async

# Load environment variables from .env file
load_dotenv()

# Initialize telemetry FIRST (before logging setup to prevent handler conflicts)
_logfire_enabled = setup_logfire_observability()

# Initialize logging AFTER telemetry
configure_root_logger()
logger = get_logger(__name__)
logger.debug("Logfire observability enabled: %s", _logfire_enabled)

# Apply Gemini 3 patch early (before any agents are created)
# This fixes a pydantic-ai bug where TextPart(content=None) crashes the agent
from shotgun.agents.gemini3_patch import apply_gemini3_patch

apply_gemini3_patch()

# Initialize configuration
# Note: If config migration fails, ConfigManager will auto-create fresh config
# and set migration_failed flag for user notification
try:
    import asyncio

    config_manager = get_config_manager()
    asyncio.run(config_manager.load())  # Ensure config is loaded at startup
except Exception as e:
    logger.debug("Configuration initialization warning: %s", e)

# Initialize PostHog analytics (includes exception tracking)
_posthog_enabled = setup_posthog_observability()
logger.debug("PostHog analytics enabled: %s", _posthog_enabled)


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
app.add_typer(context.app, name="context", help="Analyze conversation context usage")
app.add_typer(compact.app, name="compact", help="Compact conversation history")
app.add_typer(clear.app, name="clear", help="Clear conversation history")
app.add_typer(run.app, name="run", help="Run a prompt using the Router agent")
app.add_typer(update.app, name="update", help="Check for and install updates")
app.add_typer(feedback.app, name="feedback", help="Send us feedback")
app.add_typer(spec.app, name="spec", help="Manage shared specifications")


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
    continue_session: Annotated[
        bool,
        typer.Option(
            "--continue",
            "-c",
            help="Continue previous TUI conversation",
        ),
    ] = False,
    web: Annotated[
        bool,
        typer.Option(
            "--web",
            help="Serve TUI as web application",
        ),
    ] = False,
    port: Annotated[
        int,
        typer.Option(
            "--port",
            help="Port for web server (only used with --web)",
        ),
    ] = 8000,
    host: Annotated[
        str,
        typer.Option(
            "--host",
            help="Host address for web server (only used with --web)",
        ),
    ] = "localhost",
    public_url: Annotated[
        str | None,
        typer.Option(
            "--public-url",
            help="Public URL if behind proxy (only used with --web)",
        ),
    ] = None,
    force_reindex: Annotated[
        bool,
        typer.Option(
            "--force-reindex",
            help="Force re-indexing of codebase (ignores existing index)",
        ),
    ] = False,
    model: Annotated[
        str | None,
        typer.Option(
            "--model",
            "-m",
            help="Model name to use (requires SHOTGUN_OPENAI_COMPAT_BASE_URL to be set)",
        ),
    ] = None,
    sub_agent_model: Annotated[
        str | None,
        typer.Option(
            "--sub-agent-model",
            help="Model name for sub-agents (requires --model to be set)",
        ),
    ] = None,
) -> None:
    """Shotgun - AI-powered CLI tool."""
    logger.debug("Starting shotgun CLI application")

    # Start async update check and install (non-blocking)
    if not ctx.resilient_parsing:
        perform_auto_update_async(no_update_check=no_update_check)

    if ctx.invoked_subcommand is None and not ctx.resilient_parsing:
        # If --model is specified, set it for OpenAI-compatible mode
        if model:
            from shotgun.agents.config.provider import (
                set_openai_compat_model,
                set_openai_compat_sub_agent_model,
            )

            set_openai_compat_model(model)
            if sub_agent_model:
                set_openai_compat_sub_agent_model(sub_agent_model)

        if web:
            logger.debug("Launching shotgun TUI as web application")
            try:
                tui_app.serve(
                    host=host,
                    port=port,
                    public_url=public_url,
                    no_update_check=no_update_check,
                    continue_session=continue_session,
                    force_reindex=force_reindex,
                    model_override=model,
                    sub_agent_model_override=sub_agent_model,
                )
            finally:
                # Ensure PostHog is shut down cleanly even if server exits unexpectedly
                from shotgun.posthog_telemetry import shutdown

                shutdown()
        else:
            logger.debug("Launching shotgun TUI application")
            try:
                tui_app.run(
                    no_update_check=no_update_check,
                    continue_session=continue_session,
                    force_reindex=force_reindex,
                )
            finally:
                # Ensure PostHog is shut down cleanly even if TUI exits unexpectedly
                from shotgun.posthog_telemetry import shutdown

                shutdown()
        raise typer.Exit()

    # For CLI commands, register PostHog shutdown handler
    if not ctx.resilient_parsing and ctx.invoked_subcommand is not None:
        import atexit

        # Register PostHog shutdown handler
        def shutdown_posthog() -> None:
            from shotgun.posthog_telemetry import shutdown

            shutdown()

        atexit.register(shutdown_posthog)


if __name__ == "__main__":
    app()
