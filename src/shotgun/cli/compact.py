"""Compact command for shotgun CLI."""

import asyncio
import json
from pathlib import Path
from typing import Annotated, Any

import typer
from pydantic_ai.usage import RequestUsage
from rich.console import Console

from shotgun.agents.config import get_provider_model
from shotgun.agents.conversation_manager import ConversationManager
from shotgun.agents.history.history_processors import token_limit_compactor
from shotgun.agents.history.token_estimation import estimate_tokens_from_messages
from shotgun.cli.models import OutputFormat
from shotgun.logging_config import get_logger

app = typer.Typer(
    name="compact", help="Compact the conversation history", no_args_is_help=False
)
logger = get_logger(__name__)
console = Console()


@app.callback(invoke_without_command=True)
def compact(
    format: Annotated[
        OutputFormat,
        typer.Option(
            "--format",
            "-f",
            help="Output format: markdown or json",
        ),
    ] = OutputFormat.MARKDOWN,
) -> None:
    """Compact the current conversation history to reduce size.

    This command compacts the conversation in ~/.shotgun-sh/conversation.json
    by summarizing older messages while preserving recent context. The compacted
    conversation is automatically saved back to the file.
    """
    try:
        result = asyncio.run(compact_conversation())

        if format == OutputFormat.JSON:
            # Output as JSON
            console.print_json(json.dumps(result, indent=2))
        else:
            # Output as markdown
            console.print(format_markdown(result))

    except FileNotFoundError as e:
        console.print(
            f"[red]Error:[/red] {e}\n\n"
            "No conversation found. Start a TUI session first with: [cyan]shotgun[/cyan]",
            style="bold",
        )
        raise typer.Exit(code=1) from e
    except Exception as e:
        console.print(
            f"[red]Error:[/red] Failed to compact conversation: {e}", style="bold"
        )
        logger.debug("Full traceback:", exc_info=True)
        raise typer.Exit(code=1) from e


async def compact_conversation() -> dict[str, Any]:
    """Compact the conversation and return statistics.

    Returns:
        Dictionary with compaction statistics including before/after metrics
    """
    # Get conversation file path
    conversation_file = Path.home() / ".shotgun-sh" / "conversation.json"

    if not conversation_file.exists():
        raise FileNotFoundError(f"Conversation file not found at {conversation_file}")

    # Load conversation
    manager = ConversationManager(conversation_file)
    conversation = await manager.load()

    if not conversation:
        raise ValueError("Conversation file is empty or corrupted")

    # Get agent messages only (not UI messages)
    agent_messages = conversation.get_agent_messages()

    if not agent_messages:
        raise ValueError("No agent messages found in conversation")

    # Get model config
    model_config = await get_provider_model()

    # Calculate before metrics
    original_message_count = len(agent_messages)
    original_tokens = await estimate_tokens_from_messages(agent_messages, model_config)

    # For CLI, we can call token_limit_compactor directly without full AgentDeps
    # since we only need the model config and message history
    # Create a minimal context object for compaction
    class CompactContext:
        def __init__(self, model_config: Any, usage: RequestUsage) -> None:
            self.deps = type("Deps", (), {"llm_model": model_config})()
            self.usage = usage

    # Create minimal usage info for compaction check
    usage = RequestUsage(input_tokens=original_tokens, output_tokens=0)
    ctx = CompactContext(model_config, usage)

    # Apply compaction with force=True to bypass threshold checks
    compacted_messages = await token_limit_compactor(ctx, agent_messages, force=True)

    # Calculate after metrics
    compacted_message_count = len(compacted_messages)
    compacted_tokens = await estimate_tokens_from_messages(
        compacted_messages, model_config
    )

    # Calculate reduction percentages
    message_reduction = (
        ((original_message_count - compacted_message_count) / original_message_count)
        * 100
        if original_message_count > 0
        else 0
    )
    token_reduction = (
        ((original_tokens - compacted_tokens) / original_tokens) * 100
        if original_tokens > 0
        else 0
    )

    # Save compacted conversation
    conversation.set_agent_messages(compacted_messages)
    await manager.save(conversation)

    logger.info(
        f"Compacted conversation: {original_message_count} → {compacted_message_count} messages "
        f"({message_reduction:.1f}% reduction)"
    )

    return {
        "success": True,
        "before": {
            "messages": original_message_count,
            "estimated_tokens": original_tokens,
        },
        "after": {
            "messages": compacted_message_count,
            "estimated_tokens": compacted_tokens,
        },
        "reduction": {
            "messages_percent": round(message_reduction, 1),
            "tokens_percent": round(token_reduction, 1),
        },
    }


def format_markdown(result: dict[str, Any]) -> str:
    """Format compaction result as markdown.

    Args:
        result: Dictionary with compaction statistics

    Returns:
        Formatted markdown string
    """
    before = result["before"]
    after = result["after"]
    reduction = result["reduction"]

    return f"""# Conversation Compacted ✓

## Before
- **Messages:** {before["messages"]:,}
- **Estimated Tokens:** {before["estimated_tokens"]:,}

## After
- **Messages:** {after["messages"]:,}
- **Estimated Tokens:** {after["estimated_tokens"]:,}

## Reduction
- **Messages:** {reduction["messages_percent"]}%
- **Tokens:** {reduction["tokens_percent"]}%
"""
