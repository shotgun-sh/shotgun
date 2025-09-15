"""Common utilities for agent creation and management."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic_ai import Agent, RunContext, UsageLimits

from shotgun.agents.config import ProviderType, get_config_manager, get_provider_model
from shotgun.logging_config import setup_logger
from shotgun.utils import ensure_shotgun_directory_exists

from .history import token_limit_compactor
from .models import AgentDeps, UIOptions
from .tools import append_file, ask_user, read_file, write_file

logger = setup_logger(__name__)


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


def get_interactive_note(interactive_mode: bool, context: str) -> str:
    """Generate interactive mode note for system prompts.

    Args:
        interactive_mode: Whether user interaction is enabled
        context: Context-specific text (e.g., "research output", "plans")

    Returns:
        Formatted note for system prompt
    """
    if interactive_mode:
        return ""

    return f"""
IMPORTANT: USER INTERACTION IS DISABLED (non-interactive mode).
- You cannot ask clarifying questions using ask_user tool
- Make reasonable assumptions based on best practices
- Use sensible defaults when information is missing
- Focus on creating minimal but functional {context}
"""


def register_common_tools(
    agent: Agent, additional_tools: list[Any], interactive_mode: bool
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
        agent.tool_plain(ask_user)
        logger.debug("📞 User interaction tool registered")
    else:
        logger.debug("🚫 User interaction disabled (non-interactive mode)")

    # Register common file management tools
    agent.tool_plain(read_file)
    agent.tool_plain(write_file)
    agent.tool_plain(append_file)

    logger.debug("✅ Tool registration complete")


def create_base_agent(
    system_prompt_fn: Callable[[RunContext[AgentDeps]], str],
    ui_options: UIOptions,
    additional_tools: list[Any] | None = None,
    provider: ProviderType | None = None,
) -> tuple[Agent[AgentDeps, str], AgentDeps]:
    """Create a base agent with common configuration.

    Args:
        system_prompt_fn: Function that will be decorated as system_prompt
        ui_options: UI options for the agent
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

        # Create deps with model config
        deps = AgentDeps(**ui_options.model_dump(), llm_model=model_config)

    except Exception as e:
        logger.warning("Failed to load configured model, using fallback: %s", e)
        logger.debug("🤖 Creating agent with fallback OpenAI GPT-4o")
        raise ValueError("Configured model is required") from e

    agent = Agent(
        model,
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
        agent.tool_plain(ask_user)
        logger.debug("📞 Interactive mode enabled - ask_user tool registered")

    # Register common file management tools (always available)
    agent.tool_plain(read_file)
    agent.tool_plain(write_file)
    agent.tool_plain(append_file)

    logger.debug("✅ Agent creation complete")
    return agent, deps


def create_usage_limits() -> UsageLimits:
    """Create reasonable usage limits for agent runs.

    Returns:
        UsageLimits configured for responsible API usage
    """
    return UsageLimits(
        request_limit=15,  # Maximum number of model requests per run
        tool_calls_limit=12,  # Maximum number of successful tool calls
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
