"""Plan command for shotgun CLI."""

import asyncio
from typing import Annotated

import typer

from shotgun.agents.config import ProviderType
from shotgun.agents.models import AgentRuntimeOptions
from shotgun.agents.plan import create_plan_agent, run_plan_agent
from shotgun.cli.error_handler import print_agent_error
from shotgun.exceptions import ErrorNotPickedUpBySentry
from shotgun.logging_config import get_logger
from shotgun.posthog_telemetry import track_event

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

    # Track plan command usage
    track_event(
        "plan_command",
        {
            "non_interactive": non_interactive,
            "provider": provider.value if provider else "default",
        },
    )

    # Create agent dependencies
    agent_runtime_options = AgentRuntimeOptions(interactive_mode=not non_interactive)

    # Create the plan agent with deps and provider
    agent, deps = asyncio.run(create_plan_agent(agent_runtime_options, provider))

    # Start planning process with error handling
    logger.info("🎯 Starting planning...")

    async def async_plan() -> None:
        try:
            result = await run_plan_agent(agent, goal, deps)
            logger.info("✅ Planning Complete!")
            logger.info("📋 Results:")
            logger.info("%s", result.output)
        except ErrorNotPickedUpBySentry as e:
            print_agent_error(e)
        except Exception as e:
            logger.exception("Unexpected error in plan command")
            print(f"⚠️  An unexpected error occurred: {str(e)}")

    asyncio.run(async_plan())
