"""Context command for shotgun CLI."""

import asyncio
import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from shotgun.agents.config import get_provider_model
from shotgun.agents.context_analyzer import ContextAnalyzer
from shotgun.agents.conversation_manager import ConversationManager
from shotgun.logging_config import get_logger

app = typer.Typer(
    name="context", help="Analyze conversation context usage", no_args_is_help=False
)
logger = get_logger(__name__)
console = Console()


@app.callback(invoke_without_command=True)
def context(
    format: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help="Output format: markdown or json",
        ),
    ] = "markdown",
) -> None:
    """Analyze the current conversation's context usage.

    This command analyzes the agent's message history from ~/.shotgun-sh/conversation.json
    and displays token usage breakdown by message type. Only agent context is counted
    (UI elements like hints are excluded).
    """
    if format not in ["markdown", "json"]:
        console.print(
            f"[red]Error:[/red] Invalid format '{format}'. Use 'markdown' or 'json'.",
            style="bold",
        )
        raise typer.Exit(code=1)

    try:
        result = asyncio.run(analyze_context())

        if format == "json":
            # Output as JSON
            console.print_json(json.dumps(result, indent=2))
        else:
            # Output as markdown (default)
            console.print(result["markdown"])

    except FileNotFoundError as e:
        console.print(
            f"[red]Error:[/red] {e}\n\n"
            "No conversation found. Start a TUI session first with: [cyan]shotgun[/cyan]",
            style="bold",
        )
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to analyze context: {e}", style="bold")
        logger.debug("Full traceback:", exc_info=True)
        raise typer.Exit(code=1)


async def analyze_context() -> dict:
    """Analyze the conversation context and return structured data.

    Returns:
        Dictionary containing both markdown and JSON representations of the analysis
    """
    # Get conversation file path
    conversation_file = Path.home() / ".shotgun-sh" / "conversation.json"

    if not conversation_file.exists():
        raise FileNotFoundError(
            f"Conversation file not found at {conversation_file}"
        )

    # Load conversation
    manager = ConversationManager(conversation_file)
    conversation = manager.load()

    if not conversation:
        raise ValueError("Conversation file is empty or corrupted")

    # Get agent messages only (not UI messages)
    agent_messages = conversation.get_agent_messages()

    if not agent_messages:
        raise ValueError("No agent messages found in conversation")

    # Get model config (use default provider settings)
    model_config = get_provider_model()

    # Debug: Log the model being used
    logger.debug(f"Using model: {model_config.name.value}")
    logger.debug(f"Provider: {model_config.provider.value}")
    logger.debug(f"Key provider: {model_config.key_provider.value}")
    logger.debug(f"Max input tokens: {model_config.max_input_tokens}")

    # Analyze with ContextAnalyzer
    analyzer = ContextAnalyzer(model_config)
    analysis = await analyzer.analyze_conversation(agent_messages, agent_messages)

    # Build JSON representation
    json_data = {
        "user_messages": {
            "count": analysis.user_messages.count,
            "tokens": analysis.user_messages.tokens,
        },
        "assistant_messages": {
            "count": analysis.assistant_messages.count,
            "tokens": analysis.assistant_messages.tokens,
        },
        "system_prompts": {
            "count": analysis.system_prompts.count,
            "tokens": analysis.system_prompts.tokens,
        },
        "system_status": {
            "count": analysis.system_status.count,
            "tokens": analysis.system_status.tokens,
        },
        "tool_calls": {
            "count": analysis.tool_calls.count,
            "tokens": analysis.tool_calls.tokens,
        },
        "tool_results": {
            "count": analysis.tool_results.count,
            "tokens": analysis.tool_results.tokens,
        },
        "summary": {
            "total_messages": analysis.total_messages - analysis.hint_messages.count,
            "agent_context_tokens": analysis.agent_context_tokens,
            "context_window": analysis.context_window,
            "usage_percentage": round(
                (analysis.agent_context_tokens / analysis.context_window * 100)
                if analysis.context_window > 0
                else 0,
                1,
            ),
        },
    }

    return {
        "markdown": analysis.format_analysis(),
        "json": json_data,
    }
