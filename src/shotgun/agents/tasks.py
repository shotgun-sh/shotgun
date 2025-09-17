"""Tasks agent factory and functions using Pydantic AI with file-based memory."""

from pydantic_ai import (
    Agent,
    DeferredToolRequests,
    RunContext,
)
from pydantic_ai.agent import AgentRunResult
from pydantic_ai.messages import ModelMessage

from shotgun.agents.config import ProviderType
from shotgun.logging_config import get_logger
from shotgun.prompts import PromptLoader

from .common import (
    add_system_status_message,
    create_base_agent,
    create_usage_limits,
    ensure_file_exists,
    get_file_history,
    run_agent,
)
from .models import AgentDeps, AgentRuntimeOptions

logger = get_logger(__name__)

# Global prompt loader instance
prompt_loader = PromptLoader()


def _build_tasks_agent_system_prompt(ctx: RunContext[AgentDeps]) -> str:
    """Build the system prompt for the tasks agent.

    Args:
        ctx: RunContext containing AgentDeps with interactive_mode and other settings

    Returns:
        The complete system prompt string for the tasks agent
    """
    return prompt_loader.render(
        "agents/tasks.j2",
        interactive_mode=ctx.deps.interactive_mode,
        context="task lists",
    )


def create_tasks_agent(
    agent_runtime_options: AgentRuntimeOptions, provider: ProviderType | None = None
) -> tuple[Agent[AgentDeps, str | DeferredToolRequests], AgentDeps]:
    """Create a tasks agent with file management capabilities.

    Args:
        agent_runtime_options: Agent runtime options for the agent
        provider: Optional provider override. If None, uses configured default

    Returns:
        Tuple of (Configured Pydantic AI agent for task management, Agent dependencies)
    """
    logger.debug("Initializing tasks agent")
    agent, deps = create_base_agent(
        _build_tasks_agent_system_prompt, agent_runtime_options, provider=provider
    )
    return agent, deps


async def run_tasks_agent(
    agent: Agent[AgentDeps, str | DeferredToolRequests],
    instruction: str,
    deps: AgentDeps,
    message_history: list[ModelMessage] | None = None,
) -> AgentRunResult[str | DeferredToolRequests]:
    """Create or update tasks based on the given instruction.

    Args:
        agent: The configured tasks agent
        instruction: The task creation/update instruction
        deps: Agent dependencies
        message_history: Optional message history for conversation continuity

    Returns:
        AgentRunResult containing the task creation process output
    """
    logger.debug("📋 Starting task creation for instruction: %s", instruction)

    # Ensure tasks.md exists
    ensure_file_exists("tasks.md", "# Tasks")

    message_history = await add_system_status_message(deps, message_history)

    # Let the agent use its tools to read existing tasks, plan, and research
    full_prompt = f"Create or update tasks based on: {instruction}"

    try:
        # Create usage limits for responsible API usage
        usage_limits = create_usage_limits()

        result = await run_agent(
            agent=agent,
            prompt=full_prompt,
            deps=deps,
            message_history=message_history,
            usage_limits=usage_limits,
        )

        logger.debug("✅ Task creation completed successfully")
        return result

    except Exception as e:
        import traceback

        logger.error("Full traceback:\n%s", traceback.format_exc())
        logger.error("❌ Task creation failed: %s", str(e))
        raise


def get_tasks_history() -> str:
    """Get the full tasks history from the file.

    Returns:
        Tasks history content or fallback message
    """
    return get_file_history("tasks.md")
