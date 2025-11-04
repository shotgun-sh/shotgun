"""Configuration management CLI commands."""

from typing import Annotated

import typer
from rich.console import Console

from shotgun.agents.config import get_config_manager
from shotgun.logging_config import get_logger
from shotgun.posthog_telemetry import Feedback, FeedbackKind, submit_feedback_survey

logger = get_logger(__name__)
console = Console()

app = typer.Typer(
    name="feedback",
    help="Send us feedback",
    no_args_is_help=True,
)


@app.callback(invoke_without_command=True)
def send_feedback(
    description: Annotated[str, typer.Argument(help="Description of the feedback")],
    kind: Annotated[
        FeedbackKind,
        typer.Option("--type", "-t", help="Feedback type"),
    ],
) -> None:
    """Initialize Shotgun configuration."""
    import asyncio

    config_manager = get_config_manager()
    asyncio.run(config_manager.load())
    shotgun_instance_id = asyncio.run(config_manager.get_shotgun_instance_id())

    if not description:
        console.print(
            '❌ Please add your feedback (shotgun feedback "<your feedback>").',
            style="red",
        )
        raise typer.Exit(1)

    feedback = Feedback(
        kind=kind, description=description, shotgun_instance_id=shotgun_instance_id
    )

    submit_feedback_survey(feedback)

    console.print("Feedback sent. Thank you!")
