"""Codebase understanding sub-agent for specialized code analysis."""

from functools import partial

from pydantic_ai import Agent
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
from .models import AgentDeps, AgentResponse, AgentRuntimeOptions, AgentType

logger = get_logger(__name__)


def create_codebase_understanding_agent(
    agent_runtime_options: AgentRuntimeOptions, provider: ProviderType | None = None
) -> tuple[Agent[AgentDeps, AgentResponse], AgentDeps]:
    """Create a codebase understanding sub-agent.

    This sub-agent is specialized for code exploration and analysis. It has access
    to all codebase understanding tools (query_graph, retrieve_code, file_read, etc.)
    and returns focused, concise results suitable for delegation from parent agents.

    Args:
        agent_runtime_options: Agent runtime options for the agent
        provider: Optional provider override. If None, uses configured default

    Returns:
        Tuple of (Configured Pydantic AI agent for codebase understanding, Agent dependencies)
    """
    logger.debug("Initializing codebase understanding sub-agent")

    # Use partial to create system prompt function for codebase understanding agent
    system_prompt_fn = partial(build_agent_system_prompt, "codebase_understanding")

    agent, deps = create_base_agent(
        system_prompt_fn,
        agent_runtime_options,
        load_codebase_understanding_tools=True,
        additional_tools=None,
        provider=provider,
        agent_mode=AgentType.RESEARCH,  # Use RESEARCH mode for now
        include_write_tools=False,  # Read-only sub-agent
    )

    # For now, we return the agent as-is with AgentResponse output type
    # The sub-agent will use AgentResponse and we'll extract result field in the tool wrapper
    logger.debug("✅ Codebase understanding sub-agent created")
    return agent, deps


async def run_codebase_understanding_agent(
    agent: Agent[AgentDeps, AgentResponse],
    query: str,
    deps: AgentDeps,
    message_history: list[ModelMessage] | None = None,
) -> AgentRunResult[AgentResponse]:
    """Run the codebase understanding sub-agent.

    Args:
        agent: The configured codebase understanding agent
        query: The codebase exploration query
        deps: Agent dependencies
        message_history: Optional message history for conversation continuity

    Returns:
        AgentRunResult containing CodebaseQueryResult
    """
    logger.debug("🔍 Running codebase understanding sub-agent with query: %s", query)

    message_history = await add_system_status_message(deps, message_history)

    try:
        # Create usage limits for responsible API usage
        usage_limits = create_usage_limits()

        result = await run_agent(
            agent=agent,
            prompt=query,
            deps=deps,
            message_history=message_history,
            usage_limits=usage_limits,
        )

        logger.debug("✅ Codebase understanding sub-agent completed successfully")
        return result

    except Exception as e:
        import traceback

        logger.error("Full traceback:\n%s", traceback.format_exc())
        logger.error("❌ Codebase understanding sub-agent failed: %s", str(e))
        raise
