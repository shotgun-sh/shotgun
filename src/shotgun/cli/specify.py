"""Specify command for shotgun CLI."""

import asyncio
from typing import Annotated

import typer

from shotgun.agents.config import ProviderType
from shotgun.agents.models import AgentRuntimeOptions
from shotgun.agents.specify import (
    create_specify_agent,
    run_specify_agent,
)
from shotgun.logging_config import get_logger

app = typer.Typer(
    name="specify", help="Generate comprehensive specifications", no_args_is_help=True
)
logger = get_logger(__name__)


@app.callback(invoke_without_command=True)
def specify(
    requirement: Annotated[
        str, typer.Argument(help="Requirement or feature to specify")
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
    """Generate comprehensive specifications for software features and systems.

    This command creates detailed technical specifications including requirements,
    architecture, implementation details, and acceptance criteria based on your
    provided requirement or feature description.
    """

    logger.info("📝 Specification Requirement: %s", requirement)

    from shotgun.agents.models import AgentType
    from shotgun.cli.error_handler import run_with_error_handling

    # Create agent dependencies
    agent_runtime_options = AgentRuntimeOptions(interactive_mode=not non_interactive)

    # Create the specify agent with deps and provider
    agent, deps = asyncio.run(create_specify_agent(agent_runtime_options, provider))

    # Start specification process with error handling
    logger.info("📋 Starting specification generation...")
    result = asyncio.run(
        run_with_error_handling(
            run_specify_agent, deps, AgentType.SPECIFY, agent, requirement, deps
        )
    )

    # Display results if successful
    if result:
        logger.info("✅ Specification Complete!")
        logger.info("📋 Results:")
        logger.info("%s", result.output)
