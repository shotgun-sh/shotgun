"""Tasks command for shotgun CLI."""

import asyncio
from typing import Annotated

import typer

from shotgun.agents.config import ProviderType
from shotgun.agents.models import AgentRuntimeOptions
from shotgun.agents.tasks import (
    create_tasks_agent,
    run_tasks_agent,
)
from shotgun.cli.error_handler import print_agent_error
from shotgun.exceptions import ErrorNotPickedUpBySentry
from shotgun.logging_config import get_logger
from shotgun.posthog_telemetry import track_event

app = typer.Typer(name="tasks", help="Generate task lists with agentic approach")
logger = get_logger(__name__)


@app.callback(invoke_without_command=True)
def tasks(
    instruction: Annotated[
        str, typer.Argument(help="Task creation instruction or project description")
    ],
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
    """Generate actionable task lists based on existing research and plans.

    This command creates detailed task breakdowns using AI agents that analyze
    your research and plans to generate prioritized, actionable tasks with
    acceptance criteria and effort estimates.
    """

    logger.info("📋 Task Creation Instruction: %s", instruction)

    # Track tasks command usage
    track_event(
        "tasks_command",
        {
            "non_interactive": non_interactive,
            "provider": provider.value if provider else "default",
        },
    )

    # Create agent dependencies
    agent_runtime_options = AgentRuntimeOptions(interactive_mode=not non_interactive)

    # Create the tasks agent with deps and provider
    agent, deps = asyncio.run(create_tasks_agent(agent_runtime_options, provider))

    # Start task creation process with error handling
    logger.info("🎯 Starting task creation...")

    async def async_tasks() -> None:
        try:
            result = await run_tasks_agent(agent, instruction, deps)
            logger.info("✅ Task Creation Complete!")
            logger.info("📋 Results:")
            logger.info("%s", result.output)
        except ErrorNotPickedUpBySentry as e:
            print_agent_error(e)
        except Exception as e:
            logger.exception("Unexpected error in tasks command")
            print(f"⚠️  An unexpected error occurred: {str(e)}")

    asyncio.run(async_tasks())
