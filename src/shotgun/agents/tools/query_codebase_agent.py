"""Tool wrapper for codebase understanding sub-agent delegation."""

from typing import TYPE_CHECKING
from uuid import uuid4

import logfire
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
    # Generate unique execution ID for this sub-agent invocation
    execution_id = f"sub-agent-{uuid4().hex[:8]}"
    sub_agent_name = "Codebase Understanding"

    logger.debug(
        "🔧 Delegating to codebase understanding sub-agent (execution_id=%s): %s",
        execution_id,
        query,
    )

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

        # Extract original user prompt from message history for context
        user_context = None
        if hasattr(ctx, "messages") and ctx.messages:
            # Find the most recent user prompt from message history
            from pydantic_ai.messages import ModelRequest, UserPromptPart

            for message in reversed(ctx.messages):
                if isinstance(message, ModelRequest):
                    for part in message.parts:
                        if isinstance(part, UserPromptPart):
                            user_context = part.content
                            break
                if user_context:
                    break

        # Tag sub-agent deps with execution context and event stream handler
        sub_deps.sub_agent_execution_id = execution_id
        sub_deps.sub_agent_name = sub_agent_name
        sub_deps.event_stream_handler = ctx.deps.event_stream_handler
        sub_deps.user_context = user_context

        # Wrap sub-agent execution in Logfire span for proper tracing
        with logfire.span(
            "codebase_understanding_sub_agent",
            execution_id=execution_id,
            agent_name=sub_agent_name,
            query=query[:200] if len(query) > 200 else query,  # Truncate long queries
            user_context=(
                user_context[:200] if user_context and len(user_context) > 200 else user_context
            ),
        ):
            # Run the sub-agent with usage tracking
            # The execution_id in deps will be picked up by the event stream handler
            # The event_stream_handler will forward sub-agent events to the parent
            # Pass parent's message history so sub-agent has full conversation context
            result = await run_codebase_understanding_agent(
                agent=sub_agent,
                query=query,
                deps=sub_deps,
                message_history=ctx.messages,  # Pass parent conversation context
            )

            # Log completion with result metadata
            logfire.info(
                "Sub-agent completed",
                success=True,
                result_length=len(result.output.response)
                if result.output.response
                else 0,
            )

        logger.debug(
            "✅ Codebase understanding sub-agent (execution_id=%s) completed successfully",
            execution_id,
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

        # Log error to Logfire
        logfire.error(
            "Sub-agent failed",
            execution_id=execution_id,
            error=error_msg,
            error_type=type(e).__name__,
        )

        return CodebaseQueryResult(
            success=False,
            result="",
            error=error_msg,
        )
