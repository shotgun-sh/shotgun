"""Research command for shotgun CLI."""

from typing import Annotated

import typer

app = typer.Typer(name="research", help="Perform research with agentic loops")


@app.callback(invoke_without_command=True)  # type: ignore[misc]
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
    typer.echo(f"🔍 Research command called with query: {query}")
    if verbose:
        typer.echo("Verbose mode enabled")
    typer.echo("⚠️  Research functionality not yet implemented")
    typer.echo("🚧 Coming soon: Agentic research loops with AI")
