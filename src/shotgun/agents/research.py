"""Research agent factory and functions using Pydantic AI with file-based memory."""

from functools import partial

from pydantic_ai import (
    Agent,
    DeferredToolRequests,
)
from pydantic_ai.agent import AgentRunResult
from pydantic_ai.messages import (
    ModelMessage,
)

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
from .tools import get_available_web_search_tools

logger = get_logger(__name__)


def create_research_agent(
    agent_runtime_options: AgentRuntimeOptions, provider: ProviderType | None = None
) -> tuple[Agent[AgentDeps, str | DeferredToolRequests], AgentDeps]:
    """Create a research agent with web search and artifact management capabilities.

    Args:
        agent_runtime_options: Agent runtime options for the agent
        provider: Optional provider override. If None, uses configured default

    Returns:
        Tuple of (Configured Pydantic AI agent for research tasks, Agent dependencies)
    """
    logger.debug("Initializing research agent")

    # Get available web search tools based on configured API keys
    web_search_tools = get_available_web_search_tools()
    if web_search_tools:
        logger.info(
            "Research agent configured with %d web search tool(s)",
            len(web_search_tools),
        )
    else:
        logger.warning("Research agent configured without web search tools")

    # Use partial to create system prompt function for research agent
    system_prompt_fn = partial(build_agent_system_prompt, "research")

    agent, deps = create_base_agent(
        system_prompt_fn,
        agent_runtime_options,
        load_codebase_understanding_tools=True,
        additional_tools=web_search_tools,
        provider=provider,
        agent_mode=AgentType.RESEARCH,
    )
    return agent, deps


async def run_research_agent(
    agent: Agent[AgentDeps, str | DeferredToolRequests],
    query: str,
    deps: AgentDeps,
    message_history: list[ModelMessage] | None = None,
) -> AgentRunResult[str | DeferredToolRequests]:
    """Perform research on the given query and update research artifacts.

    Args:
        agent: The configured research agent
        query: The research query to investigate
        deps: Agent dependencies

    Returns:
        Summary of research findings
    """
    logger.debug("🔬 Starting research for query: %s", query)

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

        logger.debug("✅ Research completed successfully")
        return result

    except Exception as e:
        import traceback

        logger.error("Full traceback:\n%s", traceback.format_exc())
        logger.error("❌ Research failed: %s", str(e))
        raise
