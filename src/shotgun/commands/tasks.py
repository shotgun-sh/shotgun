"""Tasks command for shotgun CLI."""

from typing import Annotated

import typer

app = typer.Typer(name="tasks", help="Generate task lists with agentic approach")


@app.command()  # type: ignore[misc]
def generate(
    project: Annotated[str, typer.Argument(help="Project description or requirements")],
    priority: Annotated[
        str, typer.Option("--priority", "-p", help="Priority level (high, medium, low)")
    ] = "medium",
    format: Annotated[
        str, typer.Option("--format", "-f", help="Output format (text, json, markdown)")
    ] = "text",
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Verbose output")
    ] = False,
) -> None:
    """Generate a prioritized task list for the given project.

    This command will break down complex projects into manageable tasks,
    using agentic approaches to ensure comprehensive coverage and proper prioritization.
    """
    typer.echo(f"📝 Tasks command called with project: {project}")
    if verbose:
        typer.echo(f"Priority level: {priority}")
        typer.echo(f"Output format: {format}")
        typer.echo("Verbose mode enabled")
    typer.echo("⚠️  Task generation functionality not yet implemented")
    typer.echo("🚧 Coming soon: Agentic task breakdown and prioritization")
