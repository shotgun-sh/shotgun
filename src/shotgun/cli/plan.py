"""Plan command for shotgun CLI."""

import asyncio
from typing import Annotated

import typer

from shotgun.agents.config import ProviderType
from shotgun.agents.models import UIOptions
from shotgun.agents.plan import create_plan_agent, get_plan_history, run_plan_agent
from shotgun.logging_config import setup_logger

from .utils import set_logging_level

app = typer.Typer(name="plan", help="Generate structured plans", no_args_is_help=True)
logger = setup_logger(__name__)


@app.callback(invoke_without_command=True)
def plan(
    goal: Annotated[str, typer.Argument(help="Goal or objective to plan for")],
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
    """Generate a structured plan for achieving the given goal.

    This command will create detailed, actionable plans broken down into steps
    and milestones to help achieve your specified objective. It can also update
    existing plans based on new requirements or refinements.
    """
    # Set log level based on verbose flag
    set_logging_level(verbose)
    if verbose:
        logger.debug("📊 Verbose mode enabled - DEBUG level logging active")

    logger.info("📋 Planning Goal: %s", goal)

    try:
        # Create agent dependencies
        ui_options = UIOptions(interactive_mode=not non_interactive)

        # Create the plan agent with deps and provider
        agent, deps = create_plan_agent(ui_options, provider)

        # Start planning process
        logger.info("🎯 Starting planning...")
        result = asyncio.run(run_plan_agent(agent, goal, deps))

        # Display results
        logger.info("✅ Planning Complete!")
        logger.info("📋 Results:")
        logger.info("%s", result.output)
        logger.info("📄 Plan saved to: .shotgun/plan.md")

        if verbose:
            logger.debug("📚 Current plan:")
            logger.debug("%s", get_plan_history())

    except Exception as e:
        logger.error("❌ Error during planning: %s", str(e))
        if verbose:
            import traceback

            logger.debug("Full traceback:\n%s", traceback.format_exc())
