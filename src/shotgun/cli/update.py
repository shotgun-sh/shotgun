"""Update command for shotgun CLI."""

from typing import Annotated

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from shotgun.logging_config import get_logger
from shotgun.utils.update_checker import (
    detect_installation_method,
    get_latest_version,
    is_dev_version,
    perform_update,
)

logger = get_logger(__name__)
console = Console()
app = typer.Typer()


@app.callback(invoke_without_command=True)
def update(
    ctx: typer.Context,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Force update even for development versions",
        ),
    ] = False,
    check_only: Annotated[
        bool,
        typer.Option(
            "--check",
            "-c",
            help="Check for updates without installing",
        ),
    ] = False,
) -> None:
    """Check for and install updates to shotgun-sh.

    This command will:
    - Check PyPI for the latest version
    - Detect your installation method (pipx, pip, or venv)
    - Perform the appropriate upgrade command

    Examples:
        shotgun update         # Check and install updates
        shotgun update --check # Only check for updates
        shotgun update --force # Force update (even for dev versions)
    """
    if ctx.resilient_parsing:
        return

    # Handle check-only mode
    if check_only:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task("Checking for updates...", total=None)

            latest = get_latest_version()
            if not latest:
                console.print(
                    "[red]✗[/red] Failed to check for updates", style="bold red"
                )
                raise typer.Exit(1)

        from shotgun import __version__
        from shotgun.utils.update_checker import compare_versions

        if compare_versions(__version__, latest):
            console.print(
                f"[green]✓[/green] Update available: [cyan]{__version__}[/cyan] → [green]{latest}[/green]",
                style="bold",
            )
            console.print("Run 'shotgun update' to install the update")
        else:
            console.print(
                f"[green]✓[/green] You're on the latest version ([cyan]{__version__}[/cyan])",
                style="bold",
            )
        return

    # Check for dev version
    if is_dev_version() and not force:
        console.print(
            "[yellow]⚠[/yellow] You're running a development version",
            style="bold yellow",
        )
        console.print(
            "Use --force to update anyway, or install the stable version with:\n"
            "  pipx install shotgun-sh\n"
            "  or\n"
            "  pip install shotgun-sh",
        )
        raise typer.Exit(1)

    # Confirm if forcing dev version update
    if is_dev_version() and force:
        confirm = typer.confirm(
            "⚠️  You're about to replace a development version. Continue?",
            default=False,
        )
        if not confirm:
            console.print("Update cancelled", style="dim")
            raise typer.Exit(0)

    # Detect installation method
    method = detect_installation_method()
    console.print(f"Installation method: [cyan]{method}[/cyan]", style="dim")

    # Perform update
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Updating shotgun-sh...", total=None)

        success, message = perform_update(force=force)

        if success:
            progress.update(task, description="[green]✓[/green] Update complete!")
            console.print(f"\n[green]✓[/green] {message}", style="bold green")
            console.print(
                "\n[dim]Restart your terminal or run 'shotgun --version' to verify the update[/dim]"
            )
        else:
            progress.update(task, description="[red]✗[/red] Update failed")
            console.print(f"\n[red]✗[/red] {message}", style="bold red")

            # Provide manual update instructions
            if method == "pipx":
                console.print(
                    "\n[yellow]Try updating manually:[/yellow]\n"
                    "  pipx upgrade shotgun-sh"
                )
            else:
                console.print(
                    "\n[yellow]Try updating manually:[/yellow]\n"
                    "  pip install --upgrade shotgun-sh"
                )
            raise typer.Exit(1)


if __name__ == "__main__":
    app()
