"""Plan agent factory and functions using Pydantic AI with file-based memory."""

from functools import partial

from pydantic_ai import (
    Agent,
    DeferredToolRequests,
)
from pydantic_ai.agent import AgentRunResult
from pydantic_ai.messages import ModelMessage

from shotgun.agents.config import ProviderType
from shotgun.logging_config import get_logger

from .common import (
    add_system_status_message,
    build_agent_system_prompt,
    create_base_agent,
    create_usage_limits,
    run_agent,
)
from .models import AgentDeps, AgentRuntimeOptions, AgentType

logger = get_logger(__name__)


def create_plan_agent(
    agent_runtime_options: AgentRuntimeOptions, provider: ProviderType | None = None
) -> tuple[Agent[AgentDeps, str | DeferredToolRequests], AgentDeps]:
    """Create a plan agent with artifact management capabilities.

    Args:
        agent_runtime_options: Agent runtime options for the agent
        provider: Optional provider override. If None, uses configured default

    Returns:
        Tuple of (Configured Pydantic AI agent for planning tasks, Agent dependencies)
    """
    logger.debug("Initializing plan agent")
    # Use partial to create system prompt function for plan agent
    system_prompt_fn = partial(build_agent_system_prompt, "plan")

    agent, deps = create_base_agent(
        system_prompt_fn,
        agent_runtime_options,
        load_codebase_understanding_tools=True,
        additional_tools=None,
        provider=provider,
        agent_mode=AgentType.PLAN,
    )
    return agent, deps


async def run_plan_agent(
    agent: Agent[AgentDeps, str | DeferredToolRequests],
    goal: str,
    deps: AgentDeps,
    message_history: list[ModelMessage] | None = None,
) -> AgentRunResult[str | DeferredToolRequests]:
    """Create or update a plan based on the given goal using artifacts.

    Args:
        agent: The configured plan agent
        goal: The planning goal or instruction
        deps: Agent dependencies
        message_history: Optional message history for conversation continuity

    Returns:
        AgentRunResult containing the planning process output
    """
    logger.debug("📋 Starting planning for goal: %s", goal)

    # Simple prompt - the agent system prompt has all the artifact instructions
    full_prompt = f"Create a comprehensive plan for: {goal}"

    try:
        # Create usage limits for responsible API usage
        usage_limits = create_usage_limits()

        message_history = await add_system_status_message(deps, message_history)

        result = await run_agent(
            agent=agent,
            prompt=full_prompt,
            deps=deps,
            message_history=message_history,
            usage_limits=usage_limits,
        )

        logger.debug("✅ Planning completed successfully")
        return result

    except Exception as e:
        import traceback

        logger.error("Full traceback:\n%s", traceback.format_exc())
        logger.error("❌ Planning failed: %s", str(e))
        raise
