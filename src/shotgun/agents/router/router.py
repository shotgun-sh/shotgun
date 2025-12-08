"""Router agent factory and functions using Pydantic AI.

The Router Agent is the single point of contact for users, orchestrating
work across specialized sub-agents while maintaining the Planning/Drafting
mode system for controlled execution.
"""

import traceback
from functools import partial

from pydantic_ai import Agent
from pydantic_ai.agent import AgentRunResult
from pydantic_ai.messages import ModelMessage

from shotgun.agents.config import ProviderType
from shotgun.agents.models import (
    AgentDeps,
    AgentResponse,
    AgentRuntimeOptions,
    AgentType,
)
from shotgun.logging_config import get_logger

from ..common import (
    add_system_status_message,
    build_agent_system_prompt,
    create_base_agent,
    create_usage_limits,
    run_agent,
)
from .tools import (
    add_step,
    check_dependents,
    clear_plan,
    create_plan,
    get_file_dependencies,
    get_plan,
    mark_step_done,
    remove_step,
    reorder_steps,
    update_step,
)

logger = get_logger(__name__)


async def create_router_agent(
    agent_runtime_options: AgentRuntimeOptions, provider: ProviderType | None = None
) -> tuple[Agent[AgentDeps, AgentResponse], AgentDeps]:
    """Create a router agent with plan management and cascade tools.

    The router agent orchestrates work across specialized sub-agents while
    providing a single point of contact for users.

    Args:
        agent_runtime_options: Agent runtime options for the agent
        provider: Optional provider override. If None, uses configured default

    Returns:
        Tuple of (Configured Pydantic AI agent for routing tasks, Agent dependencies)
    """
    logger.debug("Initializing router agent")

    # Collect router-specific tools
    router_tools = [
        # Plan management tools
        create_plan,
        get_plan,
        mark_step_done,
        add_step,
        remove_step,
        update_step,
        reorder_steps,
        clear_plan,
        # Cascade tools
        check_dependents,
        get_file_dependencies,
    ]

    logger.info("Router agent configured with %d router tools", len(router_tools))

    # Use partial to create system prompt function for router agent
    system_prompt_fn = partial(build_agent_system_prompt, "router")

    agent, deps = await create_base_agent(
        system_prompt_fn,
        agent_runtime_options,
        load_codebase_understanding_tools=True,
        additional_tools=router_tools,
        provider=provider,
        agent_mode=AgentType.ROUTER,
    )

    return agent, deps


async def run_router_agent(
    agent: Agent[AgentDeps, AgentResponse],
    query: str,
    deps: AgentDeps,
    message_history: list[ModelMessage] | None = None,
) -> AgentRunResult[AgentResponse]:
    """Run the router agent with the given query.

    Args:
        agent: The configured router agent
        query: The user's request
        deps: Agent dependencies
        message_history: Optional conversation history

    Returns:
        Agent run result with response
    """
    logger.debug("Starting router agent for query: %s", query)

    message_history = await add_system_status_message(deps, message_history)

    try:
        usage_limits = create_usage_limits()

        result = await run_agent(
            agent=agent,
            prompt=query,
            deps=deps,
            message_history=message_history,
            usage_limits=usage_limits,
        )

        logger.debug("Router agent completed successfully")
        return result

    except Exception as e:
        logger.error("Full traceback:\n%s", traceback.format_exc())
        logger.error("Router agent failed: %s", str(e))
        raise
