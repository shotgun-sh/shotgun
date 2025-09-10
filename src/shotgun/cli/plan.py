"""Plan command for shotgun CLI."""

from typing import Annotated

import typer

app = typer.Typer(name="plan", help="Generate structured plans")


@app.callback(invoke_without_command=True)  # type: ignore[misc]
def plan(
    ctx: typer.Context,
    goal: Annotated[str, typer.Argument(help="Goal or objective to plan for")],
    format: Annotated[
        str, typer.Option("--format", "-f", help="Output format (text, json, markdown)")
    ] = "text",
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Verbose output")
    ] = False,
) -> None:
    """Generate a structured plan for achieving the given goal.

    This command will create detailed, actionable plans broken down into steps
    and milestones to help achieve your specified objective.
    """
    typer.echo(f"📋 Plan command called with goal: {goal}")
    if verbose:
        typer.echo(f"Output format: {format}")
        typer.echo("Verbose mode enabled")
    typer.echo("⚠️  Planning functionality not yet implemented")
    typer.echo("🚧 Coming soon: AI-powered structured planning")
