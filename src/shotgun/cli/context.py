"""Context command for shotgun CLI."""

import asyncio
import json
from typing import Annotated

import httpx
import typer
from rich.console import Console

from shotgun.agents.config import get_provider_model
from shotgun.agents.context_analyzer import (
    ContextAnalysisOutput,
    ContextAnalyzer,
    ContextFormatter,
)
from shotgun.agents.conversation import ConversationManager
from shotgun.cli.models import OutputFormat
from shotgun.llm_proxy import BudgetInfo, LiteLLMProxyClient
from shotgun.logging_config import get_logger
from shotgun.utils import get_shotgun_home

app = typer.Typer(
    name="context", help="Analyze conversation context usage", no_args_is_help=False
)
logger = get_logger(__name__)
console = Console()


@app.callback(invoke_without_command=True)
def context(
    format: Annotated[
        OutputFormat,
        typer.Option(
            "--format",
            "-f",
            help="Output format: markdown or json",
        ),
    ] = OutputFormat.MARKDOWN,
) -> None:
    """Analyze the current conversation's context usage.

    This command analyzes the agent's message history from ~/.shotgun-sh/conversation.json
    and displays token usage breakdown by message type. Only agent context is counted
    (UI elements like hints are excluded).
    """
    try:
        result = asyncio.run(analyze_context())

        if format == OutputFormat.JSON:
            # Output as JSON
            console.print_json(json.dumps(result.json_data, indent=2))
        else:
            # Output as plain text (Markdown() reformats and makes categories inline)
            console.print(result.markdown)

    except FileNotFoundError as e:
        console.print(
            f"[red]Error:[/red] {e}\n\n"
            "No conversation found. Start a TUI session first with: [cyan]shotgun[/cyan]",
            style="bold",
        )
        raise typer.Exit(code=1) from e
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to analyze context: {e}", style="bold")
        logger.debug("Full traceback:", exc_info=True)
        raise typer.Exit(code=1) from e


async def analyze_context() -> ContextAnalysisOutput:
    """Analyze the conversation context and return structured data.

    Returns:
        ContextAnalysisOutput with both markdown and JSON representations of the analysis
    """
    # Get conversation file path
    conversation_file = get_shotgun_home() / "conversation.json"

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

    # Get model config (use default provider settings)
    model_config = await get_provider_model()

    # Debug: Log the model being used
    logger.debug(f"Using model: {model_config.name.value}")
    logger.debug(f"Provider: {model_config.provider.value}")
    logger.debug(f"Key provider: {model_config.key_provider.value}")
    logger.debug(f"Max input tokens: {model_config.max_input_tokens}")

    # Analyze with ContextAnalyzer
    analyzer = ContextAnalyzer(model_config)
    # For CLI, agent_messages and ui_message_history are the same (no hints in CLI mode)
    analysis = await analyzer.analyze_conversation(agent_messages, list(agent_messages))

    # Use formatter to generate markdown and JSON
    markdown = ContextFormatter.format_markdown(analysis)
    json_data = ContextFormatter.format_json(analysis)

    # Add budget info for Shotgun Account users
    if model_config.is_shotgun_account:
        try:
            logger.debug("Fetching budget info for Shotgun Account")
            client = LiteLLMProxyClient(model_config.api_key)
            budget_info = await client.get_budget_info()

            # Format budget section for markdown
            budget_markdown = _format_budget_markdown(budget_info)
            markdown = f"{markdown}\n\n{budget_markdown}"

            # Add budget info to JSON using Pydantic model
            json_data["budget"] = budget_info.model_dump()
            logger.debug("Successfully added budget info to context output")

        except httpx.HTTPError as e:
            logger.warning(f"Failed to fetch budget info: {e}")
            # Don't fail the entire command if budget fetch fails
        except Exception as e:
            logger.warning(f"Unexpected error fetching budget info: {e}")
            # Don't fail the entire command if budget fetch fails

    return ContextAnalysisOutput(markdown=markdown, json_data=json_data)


def _format_budget_markdown(budget_info: BudgetInfo) -> str:
    """Format budget information as markdown.

    Args:
        budget_info: BudgetInfo instance

    Returns:
        Formatted markdown string
    """
    source_label = "Key" if budget_info.source == "key" else "Team"

    return f"""## Shotgun Account Budget

* Max Budget:     ${budget_info.max_budget:.2f}
* Current Spend:  ${budget_info.spend:.2f}
* Remaining:      ${budget_info.remaining:.2f} ({100 - budget_info.percentage_used:.1f}%)
* Budget Source:  {source_label}-level"""
