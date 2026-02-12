"""Router agent factory for the triage agent.

The Router agent is the first user-facing interface. In tiered mode, it runs
on the cheap model and handles simple requests directly or escalates complex
tasks to the Planner agent. When the cheap and expensive models are the same
(e.g., user selected Haiku), it falls back to single-tier mode with full tools.
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
from shotgun.agents.tools import read_file
from shotgun.logging_config import get_logger
from shotgun.sdk.services import get_codebase_service
from shotgun.utils import ensure_shotgun_directory_exists

logger = get_logger(__name__)


async def create_router_agent(
    agent_runtime_options: AgentRuntimeOptions,
    provider: ProviderType | None = None,
) -> tuple[Agent[RouterDeps, AgentResponse], RouterDeps]:
    """Create the Router agent for triage and simple request handling.

    In tiered mode (cheap != expensive model), the Router:
    - Runs on the cheap model (for_sub_agent=True)
    - Has only read_file tool
    - Handles simple questions directly, escalates complex work via AgentResponse

    In single-tier mode (cheap == expensive model), the Router:
    - Uses the full tool suite (delegation, plan management, read_file)
    - Uses the planner prompt template
    - Behaves like the original Router (no Planner needed)

    Args:
        agent_runtime_options: Runtime options for the agent
        provider: Optional provider override. If None, uses configured default

    Returns:
        Tuple of (Configured Router agent, RouterDeps with plan management state)
    """
    logger.debug("Initializing router agent")
    ensure_shotgun_directory_exists()

    # Get both cheap and expensive models to determine tiering mode
    try:
        cheap_config = await get_provider_model(provider, for_sub_agent=True)
        expensive_config = await get_provider_model(provider)
    except Exception as e:
        logger.error("Failed to load configured model for router: %s", e)
        raise ValueError("Configured model is required for router agent") from e

    # Determine if we're in tiered mode (different cheap vs expensive models)
    is_tiered = cheap_config.name != expensive_config.name

    if is_tiered:
        model_config = cheap_config
        prompt_template = PromptTemplate.ROUTER
        logger.info(
            "Router in TIERED mode: cheap=%s, expensive=%s",
            cheap_config.name,
            expensive_config.name,
        )
    else:
        model_config = expensive_config
        # Use full planner prompt in single-tier mode
        prompt_template = PromptTemplate.PLANNER
        logger.info(
            "Router in SINGLE-TIER mode: model=%s (no Planner needed)",
            expensive_config.name,
        )

    model = model_config.model_instance

    # Create RouterDeps
    codebase_service = get_codebase_service()
    system_prompt_fn = partial(build_agent_system_prompt, prompt_template)

    deps = RouterDeps(
        **agent_runtime_options.model_dump(),
        llm_model=model_config,
        codebase_service=codebase_service,
        system_prompt_fn=system_prompt_fn,
        agent_mode=AgentType.ROUTER,
    )

    if is_tiered:
        # Tiered mode: Router has only read_file (escalation via structured output)
        agent: Agent[RouterDeps, AgentResponse] = Agent(
            model,
            output_type=AgentResponse,
            deps_type=RouterDeps,
            instrument=True,
            history_processors=[create_history_processor(deps)],
            retries=3,
            model_settings=ANTHROPIC_CACHE_MODEL_SETTINGS,
        )

        # Triage tools only - escalation is via AgentResponse.escalation_requested
        agent.tool(read_file)

        logger.debug("Router agent tools registered (tiered mode: read_file only)")
    else:
        # Single-tier mode: Router has full tool suite (original behavior)
        agent = Agent(
            model,
            output_type=AgentResponse,
            deps_type=RouterDeps,
            instrument=True,
            history_processors=[create_history_processor(deps)],
            retries=3,
            tools=create_delegation_tools(),
            model_settings=ANTHROPIC_CACHE_MODEL_SETTINGS,
        )

        register_plan_management_tools(agent)

        logger.debug("Router agent tools registered (single-tier mode: full tools)")

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
    return await run_orchestrator_agent(agent, prompt, deps, message_history, "Router")
