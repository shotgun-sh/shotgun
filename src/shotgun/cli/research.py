"""Research command for shotgun CLI."""

import asyncio
from typing import Annotated

import typer

from shotgun.agents.config import ProviderType
from shotgun.agents.models import AgentRuntimeOptions
from shotgun.agents.research import (
    create_research_agent,
    run_research_agent,
)
from shotgun.cli.error_handler import print_agent_error
from shotgun.exceptions import ErrorNotPickedUpBySentry
from shotgun.logging_config import get_logger
from shotgun.posthog_telemetry import track_event

app = typer.Typer(
    name="research", help="Perform research with agentic loops", no_args_is_help=True
)
logger = get_logger(__name__)


@app.callback(invoke_without_command=True)
def research(
    query: Annotated[str, typer.Argument(help="Research query or topic")],
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

    logger.info("🔍 Research Query: %s", query)

    try:
        # Run everything in the same event loop
        asyncio.run(async_research(query, non_interactive, provider))

    except Exception as e:
        logger.error("❌ Error during research: %s", str(e))
        import traceback

        logger.debug("Full traceback:\n%s", traceback.format_exc())


async def async_research(
    query: str,
    non_interactive: bool,
    provider: ProviderType | None = None,
) -> None:
    """Async wrapper for research process."""
    # Track research command usage
    track_event(
        "research_command",
        {
            "non_interactive": non_interactive,
            "provider": provider.value if provider else "default",
        },
    )

    # Create agent dependencies
    agent_runtime_options = AgentRuntimeOptions(interactive_mode=not non_interactive)

    # Create the research agent with deps and provider
    agent, deps = await create_research_agent(agent_runtime_options, provider)

    # Start research process with error handling
    logger.info("🔬 Starting research...")
    try:
        result = await run_research_agent(agent, query, deps)
        # Display results
        print("✅ Research Complete!")
        print("📋 Findings:")
        print(result.output)
    except ErrorNotPickedUpBySentry as e:
        # All user-actionable errors - display with plain text
        print_agent_error(e)
    except Exception as e:
        # Unexpected errors that weren't wrapped (shouldn't happen)
        logger.exception("Unexpected error in research command")
        print(f"⚠️  An unexpected error occurred: {str(e)}")
