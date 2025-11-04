"""Common utilities for agent creation and management."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import aiofiles
from pydantic_ai import (
    Agent,
    RunContext,
    UsageLimits,
)
from pydantic_ai.agent import AgentRunResult
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
)

from shotgun.agents.config import ProviderType, get_provider_model
from shotgun.agents.models import AgentResponse, AgentType
from shotgun.logging_config import get_logger
from shotgun.prompts import PromptLoader
from shotgun.sdk.services import get_codebase_service
from shotgun.utils import ensure_shotgun_directory_exists
from shotgun.utils.datetime_utils import get_datetime_context
from shotgun.utils.file_system_utils import get_shotgun_base_path

from .history import token_limit_compactor
from .messages import AgentSystemPrompt, SystemStatusPrompt
from .models import AgentDeps, AgentRuntimeOptions, PipelineConfigEntry
from .tools import (
    append_file,
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
    # Only show graphs for the current working directory
    codebase_understanding_graphs = (
        await deps.codebase_service.list_graphs_for_directory()
    )

    # Get existing files for the agent
    existing_files = get_agent_existing_files(deps.agent_mode)

    # Extract table of contents from the agent's markdown file
    markdown_toc = await extract_markdown_toc(deps.agent_mode)

    # Get current datetime with timezone information
    dt_context = get_datetime_context()

    system_state = prompt_loader.render(
        "agents/state/system_state.j2",
        codebase_understanding_graphs=codebase_understanding_graphs,
        is_tui_context=deps.is_tui_context,
        existing_files=existing_files,
        markdown_toc=markdown_toc,
        current_datetime=dt_context.datetime_formatted,
        timezone_name=dt_context.timezone_name,
        utc_offset=dt_context.utc_offset,
    )

    message_history.append(
        ModelRequest(
            parts=[
                SystemStatusPrompt(content=system_state),
            ]
        )
    )
    return message_history


async def create_base_agent(
    system_prompt_fn: Callable[[RunContext[AgentDeps]], str],
    agent_runtime_options: AgentRuntimeOptions,
    load_codebase_understanding_tools: bool = True,
    additional_tools: list[Any] | None = None,
    provider: ProviderType | None = None,
    agent_mode: AgentType | None = None,
) -> tuple[Agent[AgentDeps, AgentResponse], AgentDeps]:
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

    # Get configured model or fall back to first available provider
    try:
        model_config = await get_provider_model(provider)
        provider_name = model_config.provider
        logger.debug(
            "🤖 Creating agent with configured %s model: %s",
            provider_name.value.upper(),
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
        output_type=AgentResponse,
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


async def _extract_file_toc_content(
    file_path: Path, max_depth: int | None = None, max_chars: int = 500
) -> str | None:
    """Extract TOC from a single file with depth and character limits.

    Args:
        file_path: Path to the markdown file
        max_depth: Maximum heading depth (1=#, 2=##, None=all)
        max_chars: Maximum characters for the TOC

    Returns:
        Formatted TOC string or None if file doesn't exist
    """
    if not file_path.exists():
        return None

    try:
        async with aiofiles.open(file_path, encoding="utf-8") as f:
            content = await f.read()
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

                # Skip if exceeds max_depth
                if max_depth and level > max_depth:
                    continue

                # Get the heading text (remove the # symbols and clean up)
                heading_text = stripped[level:].strip()
                if heading_text:
                    # Add indentation based on level
                    indent = "  " * (level - 1)
                    toc_lines.append(f"{indent}{'#' * level} {heading_text}")

                    # Check if we're approaching the character limit
                    current_length = sum(len(line) + 1 for line in toc_lines)
                    if current_length > max_chars:
                        # Remove the last line and add ellipsis
                        toc_lines.pop()
                        if toc_lines:
                            toc_lines.append("  ...")
                        break

        if not toc_lines:
            return None

        return "\n".join(toc_lines)

    except Exception as e:
        logger.debug(f"Failed to extract TOC from {file_path}: {e}")
        return None


async def extract_markdown_toc(agent_mode: AgentType | None) -> str | None:
    """Extract TOCs from current and prior agents' files in the pipeline.

    Shows full TOC of agent's own file and high-level summaries of prior agents'
    files to maintain context awareness while keeping context window tight.

    Args:
        agent_mode: The agent mode to extract TOC for

    Returns:
        Formatted multi-file TOC string or None if not applicable
    """
    # Skip if no mode
    if not agent_mode:
        return None

    # Define pipeline order and dependencies
    pipeline_config: dict[AgentType, PipelineConfigEntry] = {
        AgentType.RESEARCH: PipelineConfigEntry(
            own_file="research.md",
            prior_files=[],  # First in pipeline
        ),
        AgentType.SPECIFY: PipelineConfigEntry(
            own_file="specification.md",
            prior_files=["research.md"],
        ),
        AgentType.PLAN: PipelineConfigEntry(
            own_file="plan.md",
            prior_files=["research.md", "specification.md"],
        ),
        AgentType.TASKS: PipelineConfigEntry(
            own_file="tasks.md",
            prior_files=["research.md", "specification.md", "plan.md"],
        ),
        AgentType.EXPORT: PipelineConfigEntry(
            own_file=None,  # Export uses directory
            prior_files=["research.md", "specification.md", "plan.md", "tasks.md"],
        ),
    }

    # Get configuration for current agent
    if agent_mode not in pipeline_config:
        return None

    config = pipeline_config[agent_mode]
    base_path = get_shotgun_base_path()
    toc_sections: list[str] = []

    # Extract TOCs from prior files (high-level only)
    for prior_file in config.prior_files:
        file_path = base_path / prior_file
        # Only show # and ## headings from prior files, max 500 chars each
        prior_toc = await _extract_file_toc_content(
            file_path, max_depth=2, max_chars=500
        )
        if prior_toc:
            # Add section with XML tags
            toc_sections.append(
                f'<TABLE_OF_CONTENTS file_name="{prior_file}">\n'
                f"{prior_toc}\n"
                f"</TABLE_OF_CONTENTS>"
            )

    # Extract TOC from own file (full detail)
    if config.own_file:
        own_path = base_path / config.own_file
        own_toc = await _extract_file_toc_content(
            own_path, max_depth=None, max_chars=2000
        )
        if own_toc:
            # Put own file TOC at the beginning with XML tags
            toc_sections.insert(
                0,
                f'<TABLE_OF_CONTENTS file_name="{config.own_file}">\n'
                f"{own_toc}\n"
                f"</TABLE_OF_CONTENTS>",
            )

    # Combine all sections
    if not toc_sections:
        return None

    combined_toc = "\n\n".join(toc_sections)

    # Final truncation if needed (should rarely happen with our limits)
    max_total = 3500  # Conservative total limit
    if len(combined_toc) > max_total:
        combined_toc = combined_toc[: max_total - 3] + "..."

    return combined_toc


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
        # For other agents, check files/directories they have access to
        allowed_paths_raw = AGENT_DIRECTORIES[agent_mode]

        # Convert single Path/string to list of Paths for uniform handling
        if isinstance(allowed_paths_raw, str):
            # Special case: "*" means export agent (shouldn't reach here but handle it)
            allowed_paths = (
                [Path(allowed_paths_raw)] if allowed_paths_raw != "*" else []
            )
        elif isinstance(allowed_paths_raw, Path):
            allowed_paths = [allowed_paths_raw]
        else:
            # Already a list
            allowed_paths = allowed_paths_raw

        # Check each allowed path
        for allowed_path in allowed_paths:
            allowed_str = str(allowed_path)

            # Check if it's a directory (no .md suffix)
            if not allowed_path.suffix or not allowed_str.endswith(".md"):
                # It's a directory - list all files within it
                dir_path = base_path / allowed_str
                if dir_path.exists() and dir_path.is_dir():
                    for file_path in dir_path.rglob("*"):
                        if file_path.is_file():
                            relative_path = file_path.relative_to(base_path)
                            existing_files.append(str(relative_path))
            else:
                # It's a file - check if it exists
                file_path = base_path / allowed_str
                if file_path.exists():
                    existing_files.append(allowed_str)

                # Also check for associated directory (e.g., research/ for research.md)
                base_name = allowed_str.replace(".md", "")
                dir_path = base_path / base_name
                if dir_path.exists() and dir_path.is_dir():
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
    # We'll pass None for model and usage since they're not used
    # by our system prompt functions
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
        parts=[
            AgentSystemPrompt(content=system_prompt_content, agent_mode=deps.agent_mode)
        ]
    )
    message_history.insert(0, system_message)
    logger.debug("✅ System prompt prepended as first message")

    return message_history


async def run_agent(
    agent: Agent[AgentDeps, AgentResponse],
    prompt: str,
    deps: AgentDeps,
    message_history: list[ModelMessage] | None = None,
    usage_limits: UsageLimits | None = None,
) -> AgentRunResult[AgentResponse]:
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

    # Log file operations summary if any files were modified
    if deps.file_tracker.operations:
        summary = deps.file_tracker.format_summary()
        logger.info("📁 %s", summary)

    return result
