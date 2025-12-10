"""Export agent factory and functions using Pydantic AI with file-based memory."""

from functools import partial

from pydantic_ai.agent import AgentRunResult
from pydantic_ai.messages import ModelMessage

from shotgun.agents.config import ProviderType
from shotgun.agents.models import ShotgunAgent
from shotgun.logging_config import get_logger

from .common import (
    EventStreamHandler,
    add_system_status_message,
    build_agent_system_prompt,
    create_base_agent,
    create_usage_limits,
    run_agent,
)
from .models import AgentDeps, AgentResponse, AgentRuntimeOptions, AgentType

logger = get_logger(__name__)


async def create_export_agent(
    agent_runtime_options: AgentRuntimeOptions, provider: ProviderType | None = None
) -> tuple[ShotgunAgent, AgentDeps]:
    """Create an export agent with file management capabilities.

    Args:
        agent_runtime_options: Agent runtime options for the agent
        provider: Optional provider override. If None, uses configured default

    Returns:
        Tuple of (Configured Pydantic AI agent for export management, Agent dependencies)
    """
    logger.debug("Initializing export agent")
    # Use partial to create system prompt function for export agent
    system_prompt_fn = partial(build_agent_system_prompt, "export")

    agent, deps = await create_base_agent(
        system_prompt_fn,
        agent_runtime_options,
        provider=provider,
        agent_mode=AgentType.EXPORT,
    )
    return agent, deps


async def run_export_agent(
    agent: ShotgunAgent,
    prompt: str,
    deps: AgentDeps,
    message_history: list[ModelMessage] | None = None,
    event_stream_handler: EventStreamHandler | None = None,
) -> AgentRunResult[AgentResponse]:
    """Export artifacts based on the given prompt.

    Args:
        agent: The configured export agent
        prompt: The export prompt
        deps: Agent dependencies
        message_history: Optional message history for conversation continuity
        event_stream_handler: Optional callback for streaming events

    Returns:
        AgentRunResult containing the export process output
    """
    logger.debug("📤 Starting export for prompt: %s", prompt)

    message_history = await add_system_status_message(deps, message_history)

    try:
        # Create usage limits for responsible API usage
        usage_limits = create_usage_limits()

        result = await run_agent(
            agent=agent,
            prompt=prompt,
            deps=deps,
            message_history=message_history,
            usage_limits=usage_limits,
            event_stream_handler=event_stream_handler,
        )

        logger.debug("✅ Export completed successfully")
        return result

    except Exception as e:
        import traceback

        logger.error("Full traceback:\n%s", traceback.format_exc())
        logger.error("❌ Export failed: %s", str(e))
        raise
