"""Research command for shotgun CLI."""

from typing import Annotated

import typer

from shotgun.agents.research import ResearchAgent
from shotgun.logging_config import set_global_log_level, setup_logger

app = typer.Typer(name="research", help="Perform research with agentic loops")
logger = setup_logger(__name__)


@app.callback(invoke_without_command=True)
def research(
    ctx: typer.Context,
    query: Annotated[str, typer.Argument(help="Research query or topic")],
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Verbose output")
    ] = False,
) -> None:
    """Perform research on a given query using agentic loops.

    This command will use AI agents to iteratively research the provided topic,
    gathering information from multiple sources and refining the search process.
    """
    # Set log level based on verbose flag
    if verbose:
        set_global_log_level("DEBUG")
        logger.debug("📊 Verbose mode enabled - DEBUG level logging active")

    logger.info("🔍 Research Query: %s", query)

    try:
        # Initialize the research agent
        agent = ResearchAgent()

        # Start research process
        logger.info("🔬 Starting research...")
        findings = agent.research_sync(query)

        # Display results
        logger.info("✅ Research Complete!")
        logger.info("📋 Findings:")
        logger.info("%s", findings)
        logger.info("📄 Full research saved to: .shotgun/research.md")

        if verbose:
            logger.debug("📚 Research history:")
            logger.debug("%s", agent.get_research_history())

    except Exception as e:
        logger.error("❌ Error during research: %s", str(e))
        if verbose:
            import traceback

            logger.debug("Full traceback:\n%s", traceback.format_exc())
