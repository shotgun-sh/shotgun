"""Spec management commands for shotgun CLI."""

import asyncio
from datetime import datetime, timezone
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn

from shotgun.logging_config import get_logger
from shotgun.shotgun_web.exceptions import (
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
)
from shotgun.shotgun_web.specs_client import SpecsClient
from shotgun.shotgun_web.supabase_client import download_file_from_url
from shotgun.tui import app as tui_app
from shotgun.utils.file_system_utils import get_shotgun_base_path

from .backup import clear_shotgun_dir, create_backup
from .models import SpecMeta

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
    client = SpecsClient()
    shotgun_dir = get_shotgun_base_path()

    try:
        # Fetch version metadata and files
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            progress.add_task("Fetching version info...", total=None)
            response = await client.get_version_with_files(version_id)

        spec_name = response.spec_name
        files = response.files
        console.print(f"[bold]Pulling spec:[/bold] {spec_name}")
        console.print(f"[dim]Version: {version_id}[/dim]")
        console.print(f"[dim]Files: {len(files)}[/dim]")

        if not files:
            console.print("[yellow]No files in this version.[/yellow]")
            raise typer.Exit(1)

        # Backup existing .shotgun/ if it has content
        backup_path: str | None = None
        if shotgun_dir.exists():
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                transient=True,
            ) as progress:
                progress.add_task("Backing up existing .shotgun/...", total=None)
                backup_path = await create_backup(shotgun_dir)

            if backup_path:
                console.print(
                    f"[yellow]Existing files backed up to:[/yellow] {backup_path}"
                )
                # Clear existing content after successful backup
                clear_shotgun_dir(shotgun_dir)

        # Ensure .shotgun/ directory exists
        shotgun_dir.mkdir(parents=True, exist_ok=True)

        # Download files with progress
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        ) as progress:
            task = progress.add_task("Downloading files...", total=len(files))

            for file_info in files:
                if not file_info.download_url:
                    logger.warning(
                        "Skipping file without download URL: %s",
                        file_info.relative_path,
                    )
                    progress.advance(task)
                    continue

                # Download file content
                content = await download_file_from_url(file_info.download_url)

                # Write to local path
                local_path = shotgun_dir / file_info.relative_path
                local_path.parent.mkdir(parents=True, exist_ok=True)
                local_path.write_bytes(content)
                logger.debug("Downloaded: %s", file_info.relative_path)

                progress.advance(task)

        # Write meta.json
        meta = SpecMeta(
            version_id=response.version.id,
            spec_id=response.spec_id,
            spec_name=response.spec_name,
            workspace_id=response.workspace_id,
            is_latest=response.version.is_latest,
            pulled_at=datetime.now(timezone.utc),
            backup_path=backup_path,
            web_url=response.web_url,
        )
        meta_path = shotgun_dir / "meta.json"
        meta_path.write_text(meta.model_dump_json(indent=2))

        # Success message
        console.print()
        console.print(f"[green]Successfully pulled '{spec_name}'[/green]")
        console.print(f"  [dim]Files downloaded:[/dim] {len(files)}")
        if backup_path:
            console.print(f"  [dim]Previous backup:[/dim] {backup_path}")
        if response.web_url:
            console.print(f"  [blue]View in browser:[/blue] {response.web_url}")

        return True

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
    except Exception as e:
        logger.exception("Unexpected error in spec pull")
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise typer.Exit(1) from None
