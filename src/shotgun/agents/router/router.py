"""Router agent factory for the intelligent orchestrator.

The Router agent is the single user-facing interface that orchestrates
sub-agents (Research, Specify, Plan, Tasks, Export) based on user intent.
"""

import traceback
from functools import partial

from pydantic_ai import Agent, Tool
from pydantic_ai.agent import AgentRunResult
from pydantic_ai.messages import ModelMessage

from shotgun.agents.common import (
    add_system_status_message,
    build_agent_system_prompt,
    create_usage_limits,
    run_agent,
)
from shotgun.agents.config import ProviderType, get_provider_model
from shotgun.agents.conversation.history import token_limit_compactor
from shotgun.agents.models import AgentResponse, AgentRuntimeOptions, AgentType
from shotgun.agents.router.models import RouterDeps
from shotgun.agents.router.tools import (
    add_step,
    create_plan,
    mark_step_done,
    remove_step,
)
from shotgun.agents.router.tools.delegation_tools import (
    delegate_to_export,
    delegate_to_plan,
    delegate_to_research,
    delegate_to_specification,
    delegate_to_tasks,
    prepare_delegation_tool,
)
from shotgun.agents.tools import read_file
from shotgun.logging_config import get_logger
from shotgun.sdk.services import get_codebase_service
from shotgun.utils import ensure_shotgun_directory_exists

logger = get_logger(__name__)


async def create_router_agent(
    agent_runtime_options: AgentRuntimeOptions,
    provider: ProviderType | None = None,
) -> tuple[Agent[RouterDeps, AgentResponse], RouterDeps]:
    """Create the Router agent with plan management and delegation capabilities.

    The Router is the intelligent orchestrator that:
    - Understands user intent
    - Creates and manages execution plans
    - Delegates work to specialized sub-agents
    - Operates in Planning (incremental) or Drafting (auto-execute) mode

    Args:
        agent_runtime_options: Runtime options for the agent
        provider: Optional provider override. If None, uses configured default

    Returns:
        Tuple of (Configured Router agent, RouterDeps with plan management state)
    """
    logger.debug("Initializing router agent")
    ensure_shotgun_directory_exists()

    # Get configured model
    try:
        model_config = await get_provider_model(provider)
        logger.debug(
            "Router agent using %s model: %s",
            model_config.provider.value.upper(),
            model_config.name,
        )
        model = model_config.model_instance
    except Exception as e:
        logger.error("Failed to load configured model for router: %s", e)
        raise ValueError("Configured model is required for router agent") from e

    # Create RouterDeps (extends AgentDeps with router-specific state)
    codebase_service = get_codebase_service()
    system_prompt_fn = partial(build_agent_system_prompt, "router")

    deps = RouterDeps(
        **agent_runtime_options.model_dump(),
        llm_model=model_config,
        codebase_service=codebase_service,
        system_prompt_fn=system_prompt_fn,
        agent_mode=AgentType.ROUTER,
    )

    # Create history processor with access to deps via closure
    async def history_processor(messages: list[ModelMessage]) -> list[ModelMessage]:
        """History processor with access to deps via closure."""

        class ProcessorContext:
            def __init__(self, deps: RouterDeps):
                self.deps = deps
                self.usage = None

        ctx = ProcessorContext(deps)
        return await token_limit_compactor(ctx, messages)  # type: ignore[arg-type]

    # Delegation tools with prepare function - only visible after plan is approved
    # in Planning mode, always available in Drafting mode
    delegation_tools = [
        Tool(delegate_to_research, prepare=prepare_delegation_tool),
        Tool(delegate_to_specification, prepare=prepare_delegation_tool),
        Tool(delegate_to_plan, prepare=prepare_delegation_tool),
        Tool(delegate_to_tasks, prepare=prepare_delegation_tool),
        Tool(delegate_to_export, prepare=prepare_delegation_tool),
    ]

    # Create the agent with delegation tools that have prepare functions
    agent: Agent[RouterDeps, AgentResponse] = Agent(
        model,
        output_type=AgentResponse,
        deps_type=RouterDeps,
        instrument=True,
        history_processors=[history_processor],
        retries=3,
        tools=delegation_tools,
    )

    # Register plan management tools (router-specific, always available)
    agent.tool(create_plan)
    agent.tool(mark_step_done)
    agent.tool(add_step)
    agent.tool(remove_step)

    # Register read-only file access for .shotgun/ directory
    agent.tool(read_file)

    # Note: The Router does NOT have write_file, append_file, or codebase tools.
    # All file modifications and codebase understanding must be delegated to
    # the appropriate sub-agent (Research, Specify, Plan, Tasks, Export).

    logger.debug("Router agent tools registered")
    logger.info(
        "Router agent created in %s mode",
        deps.router_mode.value.upper(),
    )

    return agent, deps


async def run_router_agent(
    agent: Agent[RouterDeps, AgentResponse],
    prompt: str,
    deps: RouterDeps,
    message_history: list[ModelMessage] | None = None,
) -> AgentRunResult[AgentResponse]:
    """Run the router agent with a user prompt.

    Args:
        agent: The configured router agent
        prompt: User's request
        deps: RouterDeps with plan management state
        message_history: Optional existing message history

    Returns:
        Agent run result with response and any clarifying questions
    """
    logger.debug("Running router agent with prompt: %s", prompt[:100])

    message_history = await add_system_status_message(deps, message_history)

    try:
        usage_limits = create_usage_limits()

        result = await run_agent(
            agent=agent,  # type: ignore[arg-type]
            prompt=prompt,
            deps=deps,
            message_history=message_history,
            usage_limits=usage_limits,
        )

        logger.debug("Router agent completed successfully")
        return result

    except Exception:
        logger.error("Router agent error:\n%s", traceback.format_exc())
        raise
