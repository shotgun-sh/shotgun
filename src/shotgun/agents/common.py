"""Common utilities for agent creation and management."""

import asyncio
from collections.abc import Callable
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
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
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
from .tools.artifact_management import (
    create_artifact,
    list_artifact_templates,
    list_artifacts,
    read_artifact,
    read_artifact_section,
    write_artifact_section,
)

logger = get_logger(__name__)

# Global prompt loader instance
prompt_loader = PromptLoader()


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
        # Use the Model instance directly (has API key baked in)
        model = model_config.model_instance

        # Create deps with model config and codebase service
        codebase_service = get_codebase_service()
        deps = AgentDeps(
            **agent_runtime_options.model_dump(),
            llm_model=model_config,
            codebase_service=codebase_service,
            system_prompt_fn=system_prompt_fn,
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

    # System prompt function is stored in deps and will be called manually in run_agent
    func_name = getattr(system_prompt_fn, "__name__", str(system_prompt_fn))
    logger.debug("🔧 System prompt function stored: %s", func_name)

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

    # Register artifact management tools (always available)
    agent.tool_plain(create_artifact)
    agent.tool_plain(list_artifacts)
    agent.tool_plain(list_artifact_templates)
    agent.tool_plain(read_artifact)
    agent.tool_plain(read_artifact_section)
    agent.tool_plain(write_artifact_section)

    # Register codebase understanding tools (conditional)
    if load_codebase_understanding_tools:
        agent.tool(query_graph)
        agent.tool(retrieve_code)
        agent.tool(file_read)
        agent.tool(directory_lister)
        agent.tool(codebase_shell)
        logger.debug("🧠 Codebase understanding tools registered")
    else:
        logger.debug("🚫🧠 Codebase understanding tools not registered")

    logger.debug("✅ Agent creation complete with artifact and codebase tools")
    return agent, deps


def build_agent_system_prompt(
    agent_type: str,
    ctx: RunContext[AgentDeps],
    context_name: str | None = None,
) -> str:
    """Build system prompt for any agent type.

    Args:
        agent_type: Type of agent ('research', 'plan', 'tasks')
        ctx: RunContext containing AgentDeps
        context_name: Optional context name for template rendering

    Returns:
        Rendered system prompt
    """
    prompt_loader = PromptLoader()

    # Add logging if research agent
    if agent_type == "research":
        logger.debug("🔧 Building research agent system prompt...")
        logger.debug("Interactive mode: %s", ctx.deps.interactive_mode)

    result = prompt_loader.render(
        f"agents/{agent_type}.j2",
        interactive_mode=ctx.deps.interactive_mode,
        mode=agent_type,
    )

    if agent_type == "research":
        logger.debug(
            "✅ Research system prompt built successfully (length: %d chars)",
            len(result),
        )

    return result


def create_usage_limits() -> UsageLimits:
    """Create reasonable usage limits for agent runs.

    Returns:
        UsageLimits configured for responsible API usage
    """
    return UsageLimits(
        request_limit=100,  # Maximum number of model requests per run
        tool_calls_limit=100,  # Maximum number of successful tool calls
    )


async def add_system_prompt_message(
    deps: AgentDeps,
    message_history: list[ModelMessage] | None = None,
) -> list[ModelMessage]:
    """Add the system prompt as the first message in the message history.

    Args:
        deps: Agent dependencies containing system_prompt_fn
        message_history: Existing message history

    Returns:
        Updated message history with system prompt prepended as first message
    """
    message_history = message_history or []

    # Create a minimal RunContext to call the system prompt function
    # We'll pass None for model and usage since they're not used by our system prompt functions
    context = type(
        "RunContext", (), {"deps": deps, "retry": 0, "model": None, "usage": None}
    )()

    # Render the system prompt using the stored function
    system_prompt_content = deps.system_prompt_fn(context)
    logger.debug(
        "🎯 Rendered system prompt (length: %d chars)", len(system_prompt_content)
    )

    # Create system message and prepend to message history
    system_message = ModelRequest(
        parts=[SystemPromptPart(content=system_prompt_content)]
    )
    message_history.insert(0, system_message)
    logger.debug("✅ System prompt prepended as first message")

    return message_history


async def run_agent(
    agent: Agent[AgentDeps, str | DeferredToolRequests],
    prompt: str,
    deps: AgentDeps,
    message_history: list[ModelMessage] | None = None,
    usage_limits: UsageLimits | None = None,
) -> AgentRunResult[str | DeferredToolRequests]:
    # Add system prompt as first message
    message_history = await add_system_prompt_message(deps, message_history)

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
