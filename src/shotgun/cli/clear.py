"""Clear command for shotgun CLI."""

import asyncio
from pathlib import Path

import typer
from rich.console import Console

from shotgun.agents.conversation_manager import ConversationManager
from shotgun.logging_config import get_logger

app = typer.Typer(
    name="clear", help="Clear the conversation history", no_args_is_help=False
)
logger = get_logger(__name__)
console = Console()


@app.callback(invoke_without_command=True)
def clear() -> None:
    """Clear the current conversation history.

    This command deletes the conversation file at ~/.shotgun-sh/conversation.json,
    removing all conversation history. Other files in ~/.shotgun-sh/ (config, usage,
    codebases, logs) are preserved.
    """
    try:
        # Get conversation file path
        conversation_file = Path.home() / ".shotgun-sh" / "conversation.json"

        # Check if file exists
        if not conversation_file.exists():
            console.print(
                "[yellow]No conversation file found.[/yellow] Nothing to clear.",
                style="bold",
            )
            return

        # Clear the conversation
        manager = ConversationManager(conversation_file)
        asyncio.run(manager.clear())

        console.print(
            "[green]✓[/green] Conversation cleared successfully", style="bold"
        )
        logger.info("Conversation cleared successfully")

    except Exception as e:
        console.print(
            f"[red]Error:[/red] Failed to clear conversation: {e}", style="bold"
        )
        logger.debug("Full traceback:", exc_info=True)
        raise typer.Exit(code=1) from e
