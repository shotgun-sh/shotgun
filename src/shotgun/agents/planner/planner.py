"""Planner agent factory for the expensive-model orchestrator.

The Planner agent is the escalation target for the cheap Router.
It runs on the user's expensive model and has full access to:
- Plan management tools (create_plan, mark_step_done, etc.)
- Delegation tools (delegate_to_research, delegate_to_specification, etc.)
- File reading (read_file for .shotgun/ directory)

This is essentially the original Router agent before the tiered split.
"""

from functools import partial

from pydantic_ai import Agent
from pydantic_ai.agent import AgentRunResult
from pydantic_ai.messages import ModelMessage

from shotgun.agents.common import (
    build_agent_system_prompt,
    create_history_processor,
    run_orchestrator_agent,
)
from shotgun.agents.config import ProviderType, get_provider_model
from shotgun.agents.config.models import ANTHROPIC_CACHE_MODEL_SETTINGS
from shotgun.agents.models import (
    AgentResponse,
    AgentRuntimeOptions,
    AgentType,
    PromptTemplate,
)
from shotgun.agents.router.models import RouterDeps
from shotgun.agents.router.tools import (
    create_delegation_tools,
    register_plan_management_tools,
)
from shotgun.logging_config import get_logger
from shotgun.sdk.services import get_codebase_service
from shotgun.utils import ensure_shotgun_directory_exists

logger = get_logger(__name__)


async def create_planner_agent(
    agent_runtime_options: AgentRuntimeOptions,
    provider: ProviderType | None = None,
) -> tuple[Agent[RouterDeps, AgentResponse], RouterDeps]:
    """Create the Planner agent with plan management and delegation capabilities.

    The Planner is the expensive-model orchestrator that:
    - Creates and manages execution plans
    - Delegates work to specialized sub-agents
    - Handles complex multi-step task coordination

    It uses the expensive model (get_provider_model without for_sub_agent).

    Args:
        agent_runtime_options: Runtime options for the agent
        provider: Optional provider override. If None, uses configured default

    Returns:
        Tuple of (Configured Planner agent, RouterDeps with plan management state)
    """
    logger.debug("Initializing planner agent")
    ensure_shotgun_directory_exists()

    # Get expensive model (NOT for_sub_agent)
    try:
        model_config = await get_provider_model(provider)
        logger.debug(
            "Planner agent using %s model: %s",
            model_config.provider.value.upper(),
            model_config.name,
        )
        model = model_config.model_instance
    except Exception as e:
        logger.error("Failed to load configured model for planner: %s", e)
        raise ValueError("Configured model is required for planner agent") from e

    # Create RouterDeps (Planner shares the same deps type as Router)
    codebase_service = get_codebase_service()
    system_prompt_fn = partial(build_agent_system_prompt, PromptTemplate.PLANNER)

    deps = RouterDeps(
        **agent_runtime_options.model_dump(),
        llm_model=model_config,
        codebase_service=codebase_service,
        system_prompt_fn=system_prompt_fn,
        agent_mode=AgentType.PLANNER,
    )

    # Create the agent with delegation tools
    agent: Agent[RouterDeps, AgentResponse] = Agent(
        model,
        output_type=AgentResponse,
        deps_type=RouterDeps,
        instrument=True,
        history_processors=[create_history_processor(deps)],
        retries=3,
        tools=create_delegation_tools(),
        model_settings=ANTHROPIC_CACHE_MODEL_SETTINGS,
    )

    # Register plan management tools + read_file
    register_plan_management_tools(agent)

    logger.debug("Planner agent tools registered")
    logger.info(
        "Planner agent created in %s mode",
        deps.router_mode.value.upper(),
    )

    return agent, deps


async def run_planner_agent(
    agent: Agent[RouterDeps, AgentResponse],
    prompt: str,
    deps: RouterDeps,
    message_history: list[ModelMessage] | None = None,
) -> AgentRunResult[AgentResponse]:
    """Run the planner agent with a user prompt.

    Args:
        agent: The configured planner agent
        prompt: User's request (or escalation prompt)
        deps: RouterDeps with plan management state
        message_history: Optional existing message history

    Returns:
        Agent run result with response and any clarifying questions
    """
    return await run_orchestrator_agent(agent, prompt, deps, message_history, "Planner")
