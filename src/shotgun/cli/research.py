"""Research command for shotgun CLI."""

import asyncio
import sys
from typing import Annotated

import typer

from shotgun.agents.config import ProviderType
from shotgun.agents.models import AgentRuntimeOptions, UserAnswer, UserQuestion
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
        # Run everything in the same event loop
        asyncio.run(async_research(query, verbose, non_interactive, provider))

    except Exception as e:
        logger.error("❌ Error during research: %s", str(e))
        if verbose:
            import traceback

            logger.debug("Full traceback:\n%s", traceback.format_exc())


async def async_research(
    query: str,
    verbose: bool,
    non_interactive: bool,
    provider: ProviderType | None = None,
) -> None:
    """Async wrapper for research process."""
    # Create agent dependencies
    agent_runtime_options = AgentRuntimeOptions(interactive_mode=not non_interactive)

    # Create the research agent with deps and provider
    agent, deps = create_research_agent(agent_runtime_options, provider)

    # Create the worker task
    worker_task = asyncio.create_task(worker("research", deps.queue))

    try:
        # Start research process
        logger.info("🔬 Starting research...")
        result = await run_research_agent(agent, query, deps)

        # Display results
        logger.info("✅ Research Complete!")
        logger.info("📋 Findings:")
        logger.info("%s", result.output)
        logger.info("📄 Full research saved to: .shotgun/research.md")

        if verbose:
            logger.debug("📚 Research history:")
            logger.debug("%s", get_research_history())

    finally:
        # Cancel the worker task when done
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass


async def worker(name: str, queue: asyncio.Queue[UserQuestion]) -> None:
    while True:
        logger.info("🔍 Waiting for user input...")
        try:
            # Get a request from the queue
            request = await queue.get()
            logger.info("👉 %s\n", request.question)
            response = sys.stdin.readline().strip()
            logger.info(" Thanks!\n")
            logger.debug("User response received: %s", response)

            # Set the result on the future to notify the requester
            request.result.set_result(
                UserAnswer(answer=response, tool_call_id=request.tool_call_id)
            )
            queue.task_done()
        except asyncio.CancelledError:
            print(f"Worker '{name}' is shutting down.")
            break
