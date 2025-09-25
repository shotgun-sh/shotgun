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
    SystemPromptPart,
)

from shotgun.agents.config import ProviderType, get_config_manager, get_provider_model
from shotgun.agents.models import AgentType
from shotgun.logging_config import get_logger
from shotgun.prompts import PromptLoader
from shotgun.sdk.services import get_codebase_service
from shotgun.utils import ensure_shotgun_directory_exists
from shotgun.utils.file_system_utils import get_shotgun_base_path

from .history import token_limit_compactor
from .history.compaction import apply_persistent_compaction
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
from .tools.file_management import AGENT_DIRECTORIES

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

    # Get existing files for the agent
    existing_files = get_agent_existing_files(deps.agent_mode)

    # Extract table of contents from the agent's markdown file
    markdown_toc = extract_markdown_toc(deps.agent_mode)

    system_state = prompt_loader.render(
        "agents/state/system_state.j2",
        codebase_understanding_graphs=codebase_understanding_graphs,
        is_tui_context=deps.is_tui_context,
        existing_files=existing_files,
        markdown_toc=markdown_toc,
    )

    message_history.append(
        ModelRequest(
            parts=[
                SystemPromptPart(content=system_state),
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
    agent_mode: AgentType | None = None,
) -> tuple[Agent[AgentDeps, str | DeferredToolRequests], AgentDeps]:
    """Create a base agent with common configuration.

    Args:
        system_prompt_fn: Function that will be decorated as system_prompt
        agent_runtime_options: Agent runtime options for the agent
        load_codebase_understanding_tools: Whether to load codebase understanding tools
        additional_tools: Optional list of additional tools
        provider: Optional provider override. If None, uses configured default
        agent_mode: The mode of the agent (research, plan, tasks, specify, export)

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

        # Create deps with model config and services
        codebase_service = get_codebase_service()
        deps = AgentDeps(
            **agent_runtime_options.model_dump(),
            llm_model=model_config,
            codebase_service=codebase_service,
            system_prompt_fn=system_prompt_fn,
            agent_mode=agent_mode,
        )

    except Exception as e:
        logger.warning("Failed to load configured model, using fallback: %s", e)
        logger.debug("🤖 Creating agent with fallback OpenAI GPT-4o")
        raise ValueError("Configured model is required") from e

    # Create a history processor that has access to deps via closure
    async def history_processor(messages: list[ModelMessage]) -> list[ModelMessage]:
        """History processor with access to deps via closure."""

        # Create a minimal context for compaction
        class ProcessorContext:
            def __init__(self, deps: AgentDeps):
                self.deps = deps
                self.usage = None  # Will be estimated from messages

        ctx = ProcessorContext(deps)
        return await token_limit_compactor(ctx, messages)

    agent = Agent(
        model,
        output_type=[str, DeferredToolRequests],
        deps_type=AgentDeps,
        instrument=True,
        history_processors=[history_processor],
        retries=3,  # Default retry count for tool calls and output validation
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
    agent.tool(write_file)
    agent.tool(append_file)
    agent.tool(read_file)

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

    logger.debug("✅ Agent creation complete with codebase tools")
    return agent, deps


def extract_markdown_toc(agent_mode: AgentType | None) -> str | None:
    """Extract table of contents from agent's markdown file.

    Args:
        agent_mode: The agent mode to extract TOC for

    Returns:
        Formatted TOC string (up to 2000 chars) or None if not applicable
    """
    # Skip for EXPORT mode or no mode
    if (
        not agent_mode
        or agent_mode == AgentType.EXPORT
        or agent_mode not in AGENT_DIRECTORIES
    ):
        return None

    base_path = get_shotgun_base_path()
    md_file = AGENT_DIRECTORIES[agent_mode]
    md_path = base_path / md_file

    # Check if the markdown file exists
    if not md_path.exists():
        return None

    try:
        content = md_path.read_text(encoding="utf-8")
        lines = content.split("\n")

        # Extract headings
        toc_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("#"):
                # Count the heading level
                level = 0
                for char in stripped:
                    if char == "#":
                        level += 1
                    else:
                        break

                # Get the heading text (remove the # symbols and clean up)
                heading_text = stripped[level:].strip()
                if heading_text:
                    # Add indentation based on level
                    indent = "  " * (level - 1)
                    toc_lines.append(f"{indent}{'#' * level} {heading_text}")

        if not toc_lines:
            return None

        # Join and truncate to 2000 characters
        toc = "\n".join(toc_lines)
        if len(toc) > 2000:
            toc = toc[:1997] + "..."

        return toc

    except Exception as e:
        logger.debug(f"Failed to extract TOC from {md_file}: {e}")
        return None


def get_agent_existing_files(agent_mode: AgentType | None = None) -> list[str]:
    """Get list of existing files for the given agent mode.

    Args:
        agent_mode: The agent mode to check files for. If None, lists all files.

    Returns:
        List of existing file paths relative to .shotgun directory
    """
    base_path = get_shotgun_base_path()
    existing_files = []

    # If no agent mode, list all files in base path and first level subdirectories
    if agent_mode is None:
        # List files in the root .shotgun directory
        for item in base_path.iterdir():
            if item.is_file():
                existing_files.append(item.name)
            elif item.is_dir():
                # List files in first-level subdirectories
                for subitem in item.iterdir():
                    if subitem.is_file():
                        relative_path = subitem.relative_to(base_path)
                        existing_files.append(str(relative_path))
        return existing_files

    # Handle specific agent modes
    if agent_mode not in AGENT_DIRECTORIES:
        return []

    if agent_mode == AgentType.EXPORT:
        # For export agent, list all files in exports directory
        exports_dir = base_path / "exports"
        if exports_dir.exists():
            for file_path in exports_dir.rglob("*"):
                if file_path.is_file():
                    relative_path = file_path.relative_to(base_path)
                    existing_files.append(str(relative_path))
    else:
        # For other agents, check both .md file and directory with same name
        allowed_file = AGENT_DIRECTORIES[agent_mode]

        # Check for the .md file
        md_file_path = base_path / allowed_file
        if md_file_path.exists():
            existing_files.append(allowed_file)

        # Check for directory with same base name (e.g., research/ for research.md)
        base_name = allowed_file.replace(".md", "")
        dir_path = base_path / base_name
        if dir_path.exists() and dir_path.is_dir():
            # List all files in the directory
            for file_path in dir_path.rglob("*"):
                if file_path.is_file():
                    relative_path = file_path.relative_to(base_path)
                    existing_files.append(str(relative_path))

    return existing_files


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
    # Clear file tracker for new run
    deps.file_tracker.clear()
    logger.debug("🔧 Cleared file tracker for new agent run")

    # Add system prompt as first message
    message_history = await add_system_prompt_message(deps, message_history)

    result = await agent.run(
        prompt,
        deps=deps,
        usage_limits=usage_limits,
        message_history=message_history,
    )

    # Apply persistent compaction to prevent cascading token growth across CLI commands
    messages = await apply_persistent_compaction(result.all_messages(), deps)
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
        # Apply persistent compaction to prevent cascading token growth in multi-turn loops
        messages = await apply_persistent_compaction(result.all_messages(), deps)

    # Log file operations summary if any files were modified
    if deps.file_tracker.operations:
        summary = deps.file_tracker.format_summary()
        logger.info("📁 %s", summary)

    return result
