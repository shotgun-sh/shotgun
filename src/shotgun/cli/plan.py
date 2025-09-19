"""Plan command for shotgun CLI."""

import asyncio
from typing import Annotated

import typer

from shotgun.agents.config import ProviderType
from shotgun.agents.models import AgentRuntimeOptions
from shotgun.agents.plan import create_plan_agent, run_plan_agent
from shotgun.logging_config import get_logger

app = typer.Typer(name="plan", help="Generate structured plans", no_args_is_help=True)
logger = get_logger(__name__)


@app.callback(invoke_without_command=True)
def plan(
    goal: Annotated[str, typer.Argument(help="Goal or objective to plan for")],
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

    logger.info("📋 Planning Goal: %s", goal)

    try:
        # Track plan command usage
        from shotgun.posthog_telemetry import track_event

        track_event(
            "plan_command",
            {
                "non_interactive": non_interactive,
                "provider": provider.value if provider else "default",
            },
        )

        # Create agent dependencies
        agent_runtime_options = AgentRuntimeOptions(
            interactive_mode=not non_interactive
        )

        # Create the plan agent with deps and provider
        agent, deps = create_plan_agent(agent_runtime_options, provider)

        # Start planning process
        logger.info("🎯 Starting planning...")
        result = asyncio.run(run_plan_agent(agent, goal, deps))

        # Display results
        logger.info("✅ Planning Complete!")
        logger.info("📋 Results:")
        logger.info("%s", result.output)

    except Exception as e:
        logger.error("❌ Error during planning: %s", str(e))
        import traceback

        logger.debug("Full traceback:\n%s", traceback.format_exc())
