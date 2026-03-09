"""MCP server management CLI commands."""

import asyncio
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from shotgun.agents.config import get_config_manager
from shotgun.agents.config.models import MCPServerEntry, MCPTransport
from shotgun.logging_config import get_logger

logger = get_logger(__name__)
console = Console()

app = typer.Typer(
    name="mcp",
    help="Manage MCP servers (experimental)",
    no_args_is_help=True,
)


@app.command()
def add(
    name: Annotated[str, typer.Argument(help="Unique name for the MCP server")],
    command: Annotated[
        str | None,
        typer.Option("--command", "-c", help="Command to run (stdio transport)"),
    ] = None,
    args: Annotated[
        list[str] | None,
        typer.Option("--args", "-a", help="Arguments for the command"),
    ] = None,
    env: Annotated[
        list[str] | None,
        typer.Option("--env", "-e", help="Environment variables (KEY=VAL format)"),
    ] = None,
    url: Annotated[
        str | None,
        typer.Option("--url", "-u", help="URL for HTTP transport"),
    ] = None,
    header: Annotated[
        list[str] | None,
        typer.Option("--header", "-H", help="HTTP headers (KEY=VAL format)"),
    ] = None,
) -> None:
    """Add an MCP server.

    Use --command for stdio transport or --url for HTTP transport.
    """
    if command and url:
        console.print("[red]Error: Cannot specify both --command and --url[/red]")
        raise typer.Exit(1)

    if not command and not url:
        console.print("[red]Error: Must specify either --command or --url[/red]")
        raise typer.Exit(1)

    # Determine transport and build entry
    if command:
        transport = MCPTransport.STDIO
        env_dict: dict[str, str] = {}
        for item in env or []:
            if "=" not in item:
                console.print(
                    f"[red]Error: Invalid env format '{item}', expected KEY=VAL[/red]"
                )
                raise typer.Exit(1)
            key, val = item.split("=", 1)
            env_dict[key] = val

        entry = MCPServerEntry(
            name=name,
            transport=transport,
            command=command,
            args=args or [],
            env=env_dict,
        )
    else:
        transport = MCPTransport.HTTP
        headers_dict: dict[str, str] = {}
        for item in header or []:
            if "=" not in item:
                console.print(
                    f"[red]Error: Invalid header format '{item}', expected KEY=VAL[/red]"
                )
                raise typer.Exit(1)
            key, val = item.split("=", 1)
            headers_dict[key] = val

        entry = MCPServerEntry(
            name=name,
            transport=transport,
            url=url,
            headers=headers_dict,
        )

    config_manager = get_config_manager()
    try:
        asyncio.run(config_manager.add_mcp_server(entry))
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from None

    console.print(f"[green]Added MCP server '{name}' ({transport})[/green]")
    console.print(
        "[yellow]Note: MCP servers are experimental. "
        "Avoid giving agents access to destructive tools.[/yellow]"
    )


@app.command()
def remove(
    name: Annotated[str, typer.Argument(help="Name of the MCP server to remove")],
) -> None:
    """Remove an MCP server."""
    config_manager = get_config_manager()
    removed = asyncio.run(config_manager.remove_mcp_server(name))

    if removed:
        console.print(f"[green]Removed MCP server '{name}'[/green]")
    else:
        console.print(f"[red]Error: MCP server '{name}' not found[/red]")
        raise typer.Exit(1)


@app.command("list")
def list_servers() -> None:
    """List configured MCP servers."""
    config_manager = get_config_manager()
    servers = asyncio.run(config_manager.get_mcp_servers())

    if not servers:
        console.print("No MCP servers configured.")
        console.print(
            "\nAdd one with: [bold]shotgun mcp add <name> --command <cmd>[/bold]"
        )
        return

    table = Table(title="MCP Servers (experimental)")
    table.add_column("Name", style="cyan")
    table.add_column("Transport", style="green")
    table.add_column("Endpoint", style="white")

    for server in servers:
        if server.transport == MCPTransport.STDIO:
            endpoint = f"{server.command} {' '.join(server.args)}".strip()
        else:
            endpoint = server.url or ""
        table.add_row(server.name, server.transport.value, endpoint)

    console.print(table)
