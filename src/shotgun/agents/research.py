"""Research agent factory and functions using Pydantic AI with file-based memory."""

from pydantic_ai import (
    Agent,
    DeferredToolRequests,
    RunContext,
)
from pydantic_ai.agent import AgentRunResult
from pydantic_ai.messages import (
    ModelMessage,
)

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
from .tools import web_search_tool

logger = get_logger(__name__)

# Global prompt loader instance
prompt_loader = PromptLoader()


def _build_research_agent_system_prompt(ctx: RunContext[AgentDeps]) -> str:
    """Build the system prompt for the research agent.

    Args:
        ctx: RunContext containing AgentDeps with interactive_mode and other settings

    Returns:
        The complete system prompt string for the research agent
    """
    return prompt_loader.render(
        "agents/research.j2",
        interactive_mode=ctx.deps.interactive_mode,
        context="research output",
    )


def create_research_agent(
    agent_runtime_options: AgentRuntimeOptions, provider: ProviderType | None = None
) -> tuple[Agent[AgentDeps, str | DeferredToolRequests], AgentDeps]:
    """Create a research agent with web search capabilities.

    Args:
        agent_runtime_options: Agent runtime options for the agent
        provider: Optional provider override. If None, uses configured default

    Returns:
        Tuple of (Configured Pydantic AI agent for research tasks, Agent dependencies)
    """
    logger.debug("Initializing research agent")
    agent, deps = create_base_agent(
        _build_research_agent_system_prompt,
        agent_runtime_options,
        load_codebase_understanding_tools=True,
        additional_tools=[web_search_tool],
        provider=provider,
    )
    return agent, deps


async def run_research_agent(
    agent: Agent[AgentDeps, str | DeferredToolRequests],
    query: str,
    deps: AgentDeps,
    message_history: list[ModelMessage] | None = None,
) -> AgentRunResult[str | DeferredToolRequests]:
    """Perform research on the given query and update the research file.

    Args:
        agent: The configured research agent
        query: The research query to investigate
        deps: Agent dependencies

    Returns:
        Summary of research findings
    """
    logger.debug("🔬 Starting research for query: %s", query)

    # Ensure research.md exists
    ensure_file_exists("research.md", "# Research")

    message_history = await add_system_status_message(deps, message_history)

    user_prompt = prompt_loader.render(
        "user/research.j2",
        user_query=query,
        context="research output",
    )

    try:
        # Create usage limits for responsible API usage
        usage_limits = create_usage_limits()

        result = await run_agent(
            agent=agent,
            prompt=user_prompt,
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


def get_research_history() -> str:
    """Get the full research history from the file.

    Returns:
        Research history content or fallback message
    """
    return get_file_history("research.md")
