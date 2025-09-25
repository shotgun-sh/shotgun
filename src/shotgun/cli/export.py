"""Export command for shotgun CLI."""

import asyncio
from typing import Annotated

import typer

from shotgun.agents.config import ProviderType
from shotgun.agents.export import (
    create_export_agent,
    run_export_agent,
)
from shotgun.agents.models import AgentRuntimeOptions
from shotgun.logging_config import get_logger

app = typer.Typer(
    name="export", help="Export artifacts to various formats with agentic approach"
)
logger = get_logger(__name__)


@app.callback(invoke_without_command=True)
def export(
    instruction: Annotated[
        str, typer.Argument(help="Export instruction or format specification")
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
    """Export artifacts and findings to various formats.

    This command exports research, plans, tasks, and other project artifacts
    to different formats like Markdown, HTML, JSON, CSV, or project management
    tool formats. The AI agent will analyze available content and transform
    it according to your export requirements.
    """

    logger.info("📤 Export Instruction: %s", instruction)

    try:
        # Track export command usage
        from shotgun.posthog_telemetry import track_event

        track_event(
            "export_command",
            {
                "non_interactive": non_interactive,
                "provider": provider.value if provider else "default",
            },
        )

        # Create agent dependencies
        agent_runtime_options = AgentRuntimeOptions(
            interactive_mode=not non_interactive
        )

        # Create the export agent with deps and provider
        agent, deps = create_export_agent(agent_runtime_options, provider)

        # Start export process
        logger.info("🎯 Starting export...")
        result = asyncio.run(run_export_agent(agent, instruction, deps))

        # Display results
        logger.info("✅ Export Complete!")
        logger.info("📤 Results:")
        logger.info("%s", result.output)

    except Exception as e:
        logger.error("❌ Error during export: %s", str(e))
        import traceback

        logger.debug("Full traceback:\n%s", traceback.format_exc())
