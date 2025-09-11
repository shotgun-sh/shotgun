"""Plan command for shotgun CLI."""

from typing import Annotated

import typer

from shotgun.agents.plan import PlanAgent
from shotgun.logging_config import set_global_log_level, setup_logger

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
) -> None:
    """Generate a structured plan for achieving the given goal.

    This command will create detailed, actionable plans broken down into steps
    and milestones to help achieve your specified objective. It can also update
    existing plans based on new requirements or refinements.
    """
    # Set log level based on verbose flag
    if verbose:
        set_global_log_level("DEBUG")
        logger.debug("📊 Verbose mode enabled - DEBUG level logging active")

    logger.info("📋 Planning Goal: %s", goal)

    try:
        # Initialize the plan agent
        agent = PlanAgent(non_interactive=non_interactive)

        # Start planning process
        logger.info("🎯 Starting planning...")
        results = agent.plan_sync(goal)

        # Display results
        logger.info("✅ Planning Complete!")
        logger.info("📋 Results:")
        logger.info("%s", results)
        logger.info("📄 Plan saved to: .shotgun/plan.md")

        if verbose:
            logger.debug("📚 Current plan:")
            logger.debug("%s", agent.get_plan_history())

    except Exception as e:
        logger.error("❌ Error during planning: %s", str(e))
        if verbose:
            import traceback

            logger.debug("Full traceback:\n%s", traceback.format_exc())
