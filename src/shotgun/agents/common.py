"""Common utilities for agent creation and management."""

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic_ai import (
    Agent,
    DeferredToolRequests,
    DeferredToolResults,
    RunContext,
    UsageLimits,
)
from pydantic_ai.agent import AgentRunResult
from pydantic_ai.messages import (
    ModelMessage,
    ModelResponse,
    TextPart,
)

from shotgun.agents.config import ProviderType, get_config_manager, get_provider_model
from shotgun.logging_config import get_logger
from shotgun.prompts import PromptLoader
from shotgun.sdk.services import get_codebase_service
from shotgun.utils import ensure_shotgun_directory_exists

from .history import token_limit_compactor
from .models import AgentDeps, AgentRuntimeOptions
from .tools import (
    append_file,
    ask_user,
    codebase_shell,
    directory_lister,
    file_read,
    query_graph,
    read_file,
    retrieve_code,
    write_file,
)

logger = get_logger(__name__)

# Global prompt loader instance
prompt_loader = PromptLoader()


def ensure_file_exists(filename: str, header: str) -> str:
    """Ensure a markdown file exists with proper header and return its content.

    Args:
        filename: Name of the file (e.g., "research.md")
        header: Header to add if file is empty (e.g., "# Research")

    Returns:
        Current file content
    """
    shotgun_dir = Path.cwd() / ".shotgun"
    file_path = shotgun_dir / filename

    try:
        if file_path.exists():
            content = file_path.read_text(encoding="utf-8")
            if not content.strip():
                # File exists but is empty, add header
                header_content = f"{header}\n\n"
                file_path.write_text(header_content, encoding="utf-8")
                return header_content
            return content
        else:
            # File doesn't exist, create it with header
            shotgun_dir.mkdir(exist_ok=True)
            header_content = f"{header}\n\n"
            file_path.write_text(header_content, encoding="utf-8")
            return header_content
    except Exception as e:
        logger.error("Failed to initialize %s: %s", filename, str(e))
        return f"{header}\n\n"


def register_common_tools(
    agent: Agent[AgentDeps], additional_tools: list[Any], interactive_mode: bool
) -> None:
    """Register common tools with an agent.

    Args:
        agent: The Pydantic AI agent to register tools with
        additional_tools: List of additional tools specific to this agent
        interactive_mode: Whether to register interactive tools
    """
    logger.debug("📌 Registering tools with agent")

    # Register additional tools first (agent-specific)
    for tool in additional_tools:
        agent.tool_plain(tool)

    # Register interactive tool if enabled
    if interactive_mode:
        agent.tool(ask_user)
        logger.debug("📞 User interaction tool registered")
    else:
        logger.debug("🚫 User interaction disabled (non-interactive mode)")

    # Register common file management tools
    agent.tool_plain(read_file)
    agent.tool_plain(write_file)
    agent.tool_plain(append_file)

    logger.debug("✅ Tool registration complete")


async def add_system_status_message(
    deps: AgentDeps,
    message_history: list[ModelMessage] | None = None,
) -> list[ModelMessage]:
    """Add a system status message to the message history.

    Args:
        deps: Agent dependencies containing runtime options
        message_history: Existing message history

    Returns:
        Updated message history with system status message prepended
    """
    message_history = message_history or []
    codebase_understanding_graphs = await deps.codebase_service.list_graphs()

    system_state = prompt_loader.render(
        "agents/state/system_state.j2",
        codebase_understanding_graphs=codebase_understanding_graphs,
        context="system state",
    )
    message_history.append(
        ModelResponse(
            parts=[
                TextPart(content=system_state),
            ]
        )
    )
    return message_history


def create_base_agent(
    system_prompt_fn: Callable[[RunContext[AgentDeps]], str],
    agent_runtime_options: AgentRuntimeOptions,
    load_codebase_understanding_tools: bool = True,
    additional_tools: list[Any] | None = None,
    provider: ProviderType | None = None,
) -> tuple[Agent[AgentDeps, str | DeferredToolRequests], AgentDeps]:
    """Create a base agent with common configuration.

    Args:
        system_prompt_fn: Function that will be decorated as system_prompt
        agent_runtime_options: Agent runtime options for the agent
        additional_tools: Optional list of additional tools
        provider: Optional provider override. If None, uses configured default

    Returns:
        Tuple of (Configured Pydantic AI agent, Agent dependencies)
    """
    ensure_shotgun_directory_exists()

    # Get configured model or fall back to hardcoded default
    try:
        model_config = get_provider_model(provider)
        config_manager = get_config_manager()
        provider_name = provider or config_manager.load().default_provider
        logger.debug(
            "🤖 Creating agent with configured %s model: %s",
            provider_name.upper(),
            model_config.name,
        )
        model = model_config.pydantic_model_name

        # Create deps with model config and codebase service
        codebase_service = get_codebase_service()
        deps = AgentDeps(
            **agent_runtime_options.model_dump(),
            llm_model=model_config,
            codebase_service=codebase_service,
        )

    except Exception as e:
        logger.warning("Failed to load configured model, using fallback: %s", e)
        logger.debug("🤖 Creating agent with fallback OpenAI GPT-4o")
        raise ValueError("Configured model is required") from e

    agent = Agent(
        model,
        output_type=[str, DeferredToolRequests],
        deps_type=AgentDeps,
        instrument=True,
        history_processors=[token_limit_compactor],
    )

    # Decorate the system prompt function
    agent.system_prompt(system_prompt_fn)

    # Register additional tools first (agent-specific)
    for tool in additional_tools or []:
        agent.tool_plain(tool)

    # Register interactive tool conditionally based on deps
    if deps.interactive_mode:
        agent.tool(ask_user)
        logger.debug("📞 Interactive mode enabled - ask_user tool registered")

    # Register common file management tools (always available)
    agent.tool_plain(read_file)
    agent.tool_plain(write_file)
    agent.tool_plain(append_file)

    # Register codebase understanding tools (always available)
    if load_codebase_understanding_tools:
        agent.tool(query_graph)
        agent.tool(retrieve_code)
        agent.tool(file_read)
        agent.tool(directory_lister)
        agent.tool(codebase_shell)
        logger.debug("🧠 Codebase understanding tools registered")
    else:
        logger.debug("🚫🧠 Codebase understanding tools not registered")

    logger.debug("✅ Agent creation complete")
    return agent, deps


def create_usage_limits() -> UsageLimits:
    """Create reasonable usage limits for agent runs.

    Returns:
        UsageLimits configured for responsible API usage
    """
    return UsageLimits(
        request_limit=100,  # Maximum number of model requests per run
        tool_calls_limit=100,  # Maximum number of successful tool calls
    )


def get_file_history(filename: str) -> str:
    """Get the history content from a file.

    Args:
        filename: Name of the file (e.g., "research.md")

    Returns:
        File content or fallback message
    """
    try:
        return read_file(filename)
    except Exception as e:
        logger.debug("Could not load %s history: %s", filename, str(e))
        return f"No {filename.replace('.md', '')} history available."


async def run_agent(
    agent: Agent[AgentDeps, str | DeferredToolRequests],
    prompt: str,
    deps: AgentDeps,
    message_history: list[ModelMessage] | None = None,
    usage_limits: UsageLimits | None = None,
) -> AgentRunResult[str | DeferredToolRequests]:
    result = await agent.run(
        prompt,
        deps=deps,
        usage_limits=usage_limits,
        message_history=message_history,
    )

    messages = result.all_messages()
    while isinstance(result.output, DeferredToolRequests):
        logger.info("got deferred tool requests")
        await deps.queue.join()
        requests = result.output
        done, _ = await asyncio.wait(deps.tasks)

        task_results = [task.result() for task in done]
        task_results_by_tool_call_id = {
            result.tool_call_id: result.answer for result in task_results
        }
        logger.info("got task results", task_results_by_tool_call_id)
        results = DeferredToolResults()
        for call in requests.calls:
            results.calls[call.tool_call_id] = task_results_by_tool_call_id[
                call.tool_call_id
            ]
        result = await agent.run(
            deps=deps,
            usage_limits=usage_limits,
            message_history=messages,
            deferred_tool_results=results,
        )
        messages = result.all_messages()

    return result
