"""Plan agent factory and functions using Pydantic AI with file-based memory."""

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


def _build_plan_agent_system_prompt(ctx: RunContext[AgentDeps]) -> str:
    """Build the system prompt for the plan agent.

    Args:
        ctx: RunContext containing AgentDeps with interactive_mode and other settings

    Returns:
        The complete system prompt string for the plan agent
    """
    return prompt_loader.render(
        "agents/plan.j2", interactive_mode=ctx.deps.interactive_mode, context="plans"
    )


def create_plan_agent(
    agent_runtime_options: AgentRuntimeOptions, provider: ProviderType | None = None
) -> tuple[Agent[AgentDeps, str | DeferredToolRequests], AgentDeps]:
    """Create a plan agent with file management capabilities.

    Args:
        agent_runtime_options: Agent runtime options for the agent
        provider: Optional provider override. If None, uses configured default

    Returns:
        Tuple of (Configured Pydantic AI agent for planning tasks, Agent dependencies)
    """
    logger.debug("Initializing plan agent")
    agent, deps = create_base_agent(
        _build_plan_agent_system_prompt, agent_runtime_options, provider=provider
    )
    return agent, deps


async def run_plan_agent(
    agent: Agent[AgentDeps, str | DeferredToolRequests],
    goal: str,
    deps: AgentDeps,
    message_history: list[ModelMessage] | None = None,
) -> AgentRunResult[str | DeferredToolRequests]:
    """Create or update a plan based on the given goal.

    Args:
        agent: The configured plan agent
        goal: The planning goal or instruction
        deps: Agent dependencies
        message_history: Optional message history for conversation continuity

    Returns:
        AgentRunResult containing the planning process output
    """
    logger.debug("📋 Starting planning for goal: %s", goal)

    # Ensure plan.md exists
    ensure_file_exists("plan.md", "# Plan")

    # Let the agent use its tools to read existing plan and research
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


def get_plan_history() -> str:
    """Get the full plan history from the file.

    Returns:
        Plan history content or fallback message
    """
    return get_file_history("plan.md")
