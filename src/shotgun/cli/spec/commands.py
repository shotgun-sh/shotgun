"""Spec management commands for shotgun CLI."""

import asyncio
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskID, TextColumn

from shotgun.logging_config import get_logger
from shotgun.shotgun_web.exceptions import (
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
)
from shotgun.tui import app as tui_app
from shotgun.utils.file_system_utils import get_shotgun_base_path

from .models import PullSource
from .pull_service import CancelledError, PullProgress, SpecPullService

app = typer.Typer(
    name="spec",
    help="Manage shared specifications",
    no_args_is_help=True,
)
logger = get_logger(__name__)
console = Console()


@app.command()
def pull(
    version_id: Annotated[str, typer.Argument(help="Version ID to pull")],
    no_tui: Annotated[
        bool,
        typer.Option("--no-tui", help="Run in CLI-only mode (requires existing auth)"),
    ] = False,
) -> None:
    """Pull a spec version from the cloud to local .shotgun/ directory.

    Downloads all files for the specified version and writes them to the
    local .shotgun/ directory. If the directory already has content, it
    will be backed up to ~/.shotgun-sh/backups/ before being replaced.

    By default, launches the TUI which handles authentication and shows
    the pull progress. Use --no-tui for scripted/headless use (requires
    existing authentication).

    Example:
        shotgun spec pull 2532e1c7-7068-4d23-9379-58ea439c592f
    """
    if no_tui:
        # CLI-only mode: do pull directly (requires existing auth)
        success = asyncio.run(_async_pull(version_id))
        if not success:
            raise typer.Exit(1)
    else:
        # TUI mode: launch TUI which handles auth and pull
        tui_app.run(pull_version_id=version_id)


async def _async_pull(version_id: str) -> bool:
    """Async implementation of spec pull command.

    Returns:
        True if pull was successful, False otherwise.
    """
    shotgun_dir = get_shotgun_base_path()
    service = SpecPullService()

    # Track current progress state for rich display
    current_task_id: TaskID | None = None
    progress_ctx: Progress | None = None

    def on_progress(p: PullProgress) -> None:
        nonlocal current_task_id, progress_ctx
        # For CLI, we just update the description - progress bar handled by result
        if progress_ctx and current_task_id is not None:
            progress_ctx.update(current_task_id, description=p.phase)
            if p.total_files and p.file_index is not None:
                pct = ((p.file_index + 1) / p.total_files) * 100
                progress_ctx.update(current_task_id, completed=pct)

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        ) as progress:
            progress_ctx = progress
            current_task_id = progress.add_task("Starting...", total=100)

            result = await service.pull_version(
                version_id=version_id,
                shotgun_dir=shotgun_dir,
                on_progress=on_progress,
                source=PullSource.CLI,
            )

        if result.success:
            console.print()
            console.print(f"[green]Successfully pulled '{result.spec_name}'[/green]")
            console.print(f"  [dim]Files downloaded:[/dim] {result.file_count}")
            if result.backup_path:
                console.print(f"  [dim]Previous backup:[/dim] {result.backup_path}")
            if result.web_url:
                console.print(f"  [blue]View in browser:[/blue] {result.web_url}")
            return True
        else:
            console.print(f"[red]Error: {result.error}[/red]")
            return False

    except UnauthorizedError:
        console.print(
            "[red]Not authenticated. Please re-run the command to login.[/red]"
        )
        raise typer.Exit(1) from None
    except NotFoundError:
        console.print(f"[red]Version not found: {version_id}[/red]")
        console.print("[dim]Check the version ID and try again.[/dim]")
        raise typer.Exit(1) from None
    except ForbiddenError:
        console.print("[red]You don't have access to this spec.[/red]")
        raise typer.Exit(1) from None
    except CancelledError:
        console.print("[yellow]Pull cancelled.[/yellow]")
        raise typer.Exit(1) from None
    except Exception as e:
        logger.exception("Unexpected error in spec pull")
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise typer.Exit(1) from None
