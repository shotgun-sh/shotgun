"""Tool wrapper for codebase understanding sub-agent delegation."""

from typing import TYPE_CHECKING

from pydantic_ai import RunContext

from shotgun.agents.models import AgentDeps, AgentRuntimeOptions, CodebaseQueryResult
from shotgun.agents.tools.registry import ToolCategory, register_tool
from shotgun.logging_config import get_logger

if TYPE_CHECKING:
    from shotgun.agents.codebase_understanding import (
        create_codebase_understanding_agent,
        run_codebase_understanding_agent,
    )

logger = get_logger(__name__)


@register_tool(
    category=ToolCategory.CODEBASE_UNDERSTANDING,
    display_text="Querying codebase",
    key_arg="query",
)
async def query_codebase(
    ctx: RunContext[AgentDeps], query: str
) -> CodebaseQueryResult:
    """Query codebase using specialized sub-agent.

    This tool delegates to a codebase understanding sub-agent that has access
    to all codebase exploration tools (query_graph, retrieve_code, file_read, etc.).
    The sub-agent analyzes the codebase and returns focused, concise results.

    Args:
        ctx: RunContext containing AgentDeps
        query: Natural language query about the codebase

    Returns:
        CodebaseQueryResult with success status, result text, and optional error
    """
    logger.debug("🔧 Delegating to codebase understanding sub-agent: %s", query)

    try:
        # Import at runtime to avoid circular imports
        from shotgun.agents.codebase_understanding import (
            create_codebase_understanding_agent,
            run_codebase_understanding_agent,
        )

        # Create agent runtime options from parent context
        agent_runtime_options = AgentRuntimeOptions(
            interactive_mode=False,  # Sub-agent runs non-interactively
            working_directory=ctx.deps.working_directory,
            is_tui_context=ctx.deps.is_tui_context,
            max_iterations=ctx.deps.max_iterations,
            queue=ctx.deps.queue,
            tasks=ctx.deps.tasks,
            usage_manager=ctx.deps.usage_manager,
        )

        # Create the sub-agent
        sub_agent, sub_deps = create_codebase_understanding_agent(
            agent_runtime_options=agent_runtime_options,
            provider=None,  # Use default provider
        )

        # Run the sub-agent with usage tracking
        # Pass ctx.usage to ensure sub-agent usage counts toward parent limits
        result = await run_codebase_understanding_agent(
            agent=sub_agent,
            query=query,
            deps=sub_deps,
            message_history=None,  # Sub-agent starts fresh
        )

        logger.debug(
            "✅ Codebase understanding sub-agent completed successfully"
        )

        # Convert AgentResponse to CodebaseQueryResult
        return CodebaseQueryResult(
            success=True,
            result=result.output.response,
            error=None,
        )

    except Exception as e:
        error_msg = f"Codebase understanding sub-agent failed: {str(e)}"
        logger.error("❌ %s", error_msg)
        return CodebaseQueryResult(
            success=False,
            result="",
            error=error_msg,
        )
