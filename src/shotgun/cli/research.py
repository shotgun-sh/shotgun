"""Research command for shotgun CLI."""

import asyncio
from typing import Annotated

import typer

from shotgun.agents.config import ProviderType
from shotgun.agents.models import UIOptions
from shotgun.agents.research import (
    create_research_agent,
    get_research_history,
    run_research_agent,
)
from shotgun.logging_config import setup_logger

from .utils import set_logging_level

app = typer.Typer(
    name="research", help="Perform research with agentic loops", no_args_is_help=True
)
logger = setup_logger(__name__)


@app.callback(invoke_without_command=True)
def research(
    query: Annotated[str, typer.Argument(help="Research query or topic")],
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Verbose output")
    ] = False,
    non_interactive: Annotated[
        bool,
        typer.Option(
            "--non-interactive", "-n", help="Disable user interaction (for CI/CD)"
        ),
    ] = False,
    provider: Annotated[
        ProviderType | None,
        typer.Option("--provider", "-p", help="AI provider to use (overrides default)"),
    ] = None,
) -> None:
    """Perform research on a given query using agentic loops.

    This command will use AI agents to iteratively research the provided topic,
    gathering information from multiple sources and refining the search process.
    """
    # Set log level based on verbose flag
    set_logging_level(verbose)
    if verbose:
        logger.debug("📊 Verbose mode enabled - DEBUG level logging active")

    logger.info("🔍 Research Query: %s", query)

    try:
        # Create agent dependencies
        ui_options = UIOptions(interactive_mode=not non_interactive)

        # Create the research agent with deps and provider
        agent, deps = create_research_agent(ui_options, provider)

        # Start research process
        logger.info("🔬 Starting research...")
        asyncio.run(run_research_agent(agent, query, deps))

        # Display results
        logger.info("✅ Research Complete!")

        if verbose:
            logger.debug("📚 Research history:")
            logger.debug("%s", get_research_history())

    except Exception as e:
        logger.error("❌ Error during research: %s", str(e))
        if verbose:
            import traceback

            logger.debug("Full traceback:\n%s", traceback.format_exc())
