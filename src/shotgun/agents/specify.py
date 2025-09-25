"""Specify agent factory and functions using Pydantic AI with file-based memory."""

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


def create_specify_agent(
    agent_runtime_options: AgentRuntimeOptions, provider: ProviderType | None = None
) -> tuple[Agent[AgentDeps, str | DeferredToolRequests], AgentDeps]:
    """Create a specify agent with artifact management capabilities.

    Args:
        agent_runtime_options: Agent runtime options for the agent
        provider: Optional provider override. If None, uses configured default

    Returns:
        Tuple of (Configured Pydantic AI agent for specification tasks, Agent dependencies)
    """
    logger.debug("Initializing specify agent")
    # Use partial to create system prompt function for specify agent
    system_prompt_fn = partial(build_agent_system_prompt, "specify")

    agent, deps = create_base_agent(
        system_prompt_fn,
        agent_runtime_options,
        load_codebase_understanding_tools=True,
        additional_tools=None,
        provider=provider,
        agent_mode=AgentType.SPECIFY,
    )
    return agent, deps


async def run_specify_agent(
    agent: Agent[AgentDeps, str | DeferredToolRequests],
    requirement: str,
    deps: AgentDeps,
    message_history: list[ModelMessage] | None = None,
) -> AgentRunResult[str | DeferredToolRequests]:
    """Create or update specifications based on the given requirement.

    Args:
        agent: The configured specify agent
        requirement: The specification requirement or instruction
        deps: Agent dependencies
        message_history: Optional message history for conversation continuity

    Returns:
        AgentRunResult containing the specification process output
    """
    logger.debug("📋 Starting specification for requirement: %s", requirement)

    # Simple prompt - the agent system prompt has all the artifact instructions
    full_prompt = f"Create a comprehensive specification for: {requirement}"

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

        logger.debug("✅ Specification completed successfully")
        return result

    except Exception as e:
        import traceback

        logger.error("Full traceback:\n%s", traceback.format_exc())
        logger.error("❌ Specification failed: %s", str(e))
        raise
