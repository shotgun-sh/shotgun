"""Main CLI application for shotgun."""

from typing import Annotated

import typer

from shotgun.cli import plan, research, tasks

app = typer.Typer(
    name="shotgun",
    help="Shotgun - AI-powered CLI tool for research, planning, and task management",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# Add commands
app.add_typer(research.app, name="research", help="Perform research with agentic loops")
app.add_typer(plan.app, name="plan", help="Generate structured plans")
app.add_typer(tasks.app, name="tasks", help="Generate task lists with agentic approach")


def version_callback(value: bool) -> None:
    """Show version and exit."""
    if value:
        typer.echo("shotgun 0.1.0")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-v",
            callback=version_callback,
            is_eager=True,
            help="Show version and exit",
        ),
    ] = False,
) -> None:
    """Shotgun - AI-powered CLI tool."""


if __name__ == "__main__":
    app()
