"""Main CLI application for shotgun."""

from typing import Annotated

import typer
from dotenv import load_dotenv

from shotgun.agents.config import get_config_manager
from shotgun.cli import codebase, config, plan, research, tasks
from shotgun.logging_config import configure_root_logger, get_logger
from shotgun.telemetry import setup_phoenix_observability

# Load environment variables from .env file
load_dotenv()

# Initialize logging
configure_root_logger()
logger = get_logger(__name__)

# Initialize configuration
try:
    config_manager = get_config_manager()
    config_manager.load()  # Ensure config is loaded at startup
except Exception as e:
    logger.debug("Configuration initialization warning: %s", e)

# Initialize telemetry
_telemetry_enabled = setup_phoenix_observability()
logger.debug("Phoenix observability enabled: %s", _telemetry_enabled)

app = typer.Typer(
    name="shotgun",
    help="Shotgun - AI-powered CLI tool for research, planning, and task management",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# Add commands
app.add_typer(config.app, name="config", help="Manage Shotgun configuration")
app.add_typer(
    codebase.app, name="codebase", help="Manage and query code knowledge graphs"
)
app.add_typer(research.app, name="research", help="Perform research with agentic loops")
app.add_typer(plan.app, name="plan", help="Generate structured plans")
app.add_typer(tasks.app, name="tasks", help="Generate task lists with agentic approach")


def version_callback(value: bool) -> None:
    """Show version and exit."""
    if value:
        logger.info("shotgun 0.1.0")
        raise typer.Exit()


@app.callback()
def main(
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
) -> None:
    """Shotgun - AI-powered CLI tool."""
    logger.debug("Starting shotgun CLI application")


if __name__ == "__main__":
    app()
