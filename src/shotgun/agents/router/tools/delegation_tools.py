"""Delegation tools for the Router agent.

These tools allow the Router to delegate work to specialized sub-agents
(Research, Specify, Plan, Tasks, Export) for specific tasks.

Sub-agents run with isolated message histories to prevent context window bloat.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from pydantic_ai import RunContext

from shotgun.agents.export import create_export_agent, run_export_agent
from shotgun.agents.models import (
    AgentDeps,
    AgentRuntimeOptions,
    AgentType,
    ShotgunAgent,
    SubAgentContext,
)
from shotgun.agents.plan import create_plan_agent, run_plan_agent
from shotgun.agents.research import create_research_agent, run_research_agent
from shotgun.agents.router.models import (
    DelegationInput,
    DelegationResult,
    RouterDeps,
    SubAgentCacheEntry,
)
from shotgun.agents.specify import create_specify_agent, run_specify_agent
from shotgun.agents.tasks import create_tasks_agent, run_tasks_agent
from shotgun.agents.tools.registry import ToolCategory, register_tool
from shotgun.logging_config import get_logger

logger = get_logger(__name__)

# Type aliases for factory functions
CreateAgentFn = Callable[
    [AgentRuntimeOptions], Awaitable[tuple[ShotgunAgent, AgentDeps]]
]
RunAgentFn = Callable[..., Awaitable[Any]]

# Maximum retries for transient errors
MAX_RETRIES = 2

# Map agent types to their factory and run functions
AGENT_FACTORIES: dict[AgentType, tuple[CreateAgentFn, RunAgentFn]] = {
    AgentType.RESEARCH: (create_research_agent, run_research_agent),
    AgentType.SPECIFY: (create_specify_agent, run_specify_agent),
    AgentType.PLAN: (create_plan_agent, run_plan_agent),
    AgentType.TASKS: (create_tasks_agent, run_tasks_agent),
    AgentType.EXPORT: (create_export_agent, run_export_agent),
}


def _is_retryable_error(exception: BaseException) -> bool:
    """Check if exception should trigger a retry.

    Args:
        exception: The exception to check.

    Returns:
        True if the exception is a transient error that should be retried.
    """
    # ValueError for truncated/incomplete JSON
    if isinstance(exception, ValueError):
        error_str = str(exception)
        return "EOF while parsing" in error_str or (
            "JSON" in error_str and "parsing" in error_str
        )

    # API errors (overload, rate limits)
    exception_name = type(exception).__name__
    if "APIStatusError" in exception_name:
        error_str = str(exception)
        return "overload" in error_str.lower() or "rate" in error_str.lower()

    # Network errors
    if "ConnectionError" in exception_name or "TimeoutError" in exception_name:
        return True

    return False


def _create_agent_runtime_options(deps: RouterDeps) -> AgentRuntimeOptions:
    """Create AgentRuntimeOptions from RouterDeps for sub-agent creation.

    Args:
        deps: RouterDeps containing shared runtime configuration.

    Returns:
        AgentRuntimeOptions configured for sub-agent creation.
    """
    return AgentRuntimeOptions(
        interactive_mode=deps.interactive_mode,
        working_directory=deps.working_directory,
        is_tui_context=deps.is_tui_context,
        max_iterations=deps.max_iterations,
        queue=deps.queue,
        tasks=deps.tasks,
    )


async def _get_or_create_sub_agent(
    deps: RouterDeps,
    agent_type: AgentType,
) -> SubAgentCacheEntry:
    """Get a cached sub-agent or create a new one.

    Args:
        deps: RouterDeps with sub_agent_cache.
        agent_type: The type of agent to get or create.

    Returns:
        Tuple of (agent, agent_deps) for the requested agent type.

    Raises:
        ValueError: If agent_type is not supported for delegation.
    """
    # Check cache first
    if agent_type in deps.sub_agent_cache:
        logger.debug("Using cached %s agent", agent_type.value)
        return deps.sub_agent_cache[agent_type]

    # Get factory functions
    if agent_type not in AGENT_FACTORIES:
        raise ValueError(f"Agent type {agent_type} is not supported for delegation")

    create_fn, _ = AGENT_FACTORIES[agent_type]
    runtime_options = _create_agent_runtime_options(deps)

    logger.debug("Creating new %s agent for delegation", agent_type.value)
    agent, agent_deps = await create_fn(runtime_options)

    # Cache for reuse
    cache_entry: SubAgentCacheEntry = (agent, agent_deps)
    deps.sub_agent_cache[agent_type] = cache_entry

    return cache_entry


def _build_sub_agent_context(deps: RouterDeps) -> SubAgentContext:
    """Build SubAgentContext with plan information.

    Args:
        deps: RouterDeps with current plan.

    Returns:
        SubAgentContext configured for delegation.
    """
    current_step = deps.current_plan.current_step() if deps.current_plan else None

    return SubAgentContext(
        is_router_delegated=True,
        plan_goal=deps.current_plan.goal if deps.current_plan else "",
        current_step_id=current_step.id if current_step else "",
        current_step_title=current_step.title if current_step else "",
    )


async def _run_sub_agent(
    ctx: RunContext[RouterDeps],
    agent_type: AgentType,
    task: str,
    context_hint: str | None = None,
) -> DelegationResult:
    """Run a sub-agent with the given task.

    This helper function handles:
    - Getting or creating the sub-agent from cache
    - Setting up SubAgentContext
    - Managing active_sub_agent state for UI updates
    - Running the sub-agent with isolated message history
    - Extracting files_modified and handling errors with retries

    Args:
        ctx: RunContext with RouterDeps.
        agent_type: The type of sub-agent to run.
        task: The task to delegate to the sub-agent.
        context_hint: Optional context to help the sub-agent.

    Returns:
        DelegationResult with success/failure status, response, and files_modified.
    """
    deps = ctx.deps

    # Build the prompt with context hint if provided
    prompt = task
    if context_hint:
        prompt = f"{task}\n\nContext: {context_hint}"

    # Get or create the sub-agent
    try:
        agent, sub_agent_deps = await _get_or_create_sub_agent(deps, agent_type)
    except ValueError as e:
        return DelegationResult(
            success=False,
            error=str(e),
            response="",
            files_modified=[],
        )

    # Set up SubAgentContext so sub-agent knows it's being orchestrated
    sub_agent_deps.sub_agent_context = _build_sub_agent_context(deps)

    # Clear sub-agent's file tracker for fresh tracking
    sub_agent_deps.file_tracker.clear()

    # Set active_sub_agent for UI mode indicator
    deps.active_sub_agent = agent_type
    logger.info("Delegating to %s agent: %s", agent_type.value, task[:100])

    # Get the run function for this agent type
    _, run_fn = AGENT_FACTORIES[agent_type]

    # Retry loop for transient errors
    last_error: BaseException | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            # Run sub-agent with isolated message history and streaming support
            result = await run_fn(
                agent=agent,
                query=prompt,  # Most agents use 'query' parameter
                deps=sub_agent_deps,
                message_history=[],  # Isolated context
                event_stream_handler=deps.parent_stream_handler,  # Forward streaming
            )

            # Extract response text
            response_text = ""
            if result and result.output:
                response_text = result.output.response

            # Extract files modified
            files_modified = [
                op.file_path for op in sub_agent_deps.file_tracker.operations
            ]

            # Check for clarifying questions
            has_questions = False
            questions: list[str] = []
            if result and result.output and result.output.clarifying_questions:
                has_questions = True
                questions = result.output.clarifying_questions

            logger.info(
                "Sub-agent %s completed. Files modified: %s",
                agent_type.value,
                files_modified,
            )

            # Clear active_sub_agent
            deps.active_sub_agent = None

            return DelegationResult(
                success=True,
                response=response_text,
                files_modified=files_modified,
                has_questions=has_questions,
                questions=questions,
            )

        except Exception as e:
            last_error = e
            if _is_retryable_error(e) and attempt < MAX_RETRIES:
                logger.warning(
                    "Sub-agent %s failed (attempt %d/%d), retrying: %s",
                    agent_type.value,
                    attempt + 1,
                    MAX_RETRIES + 1,
                    str(e),
                )
                continue

            # Non-retryable error or max retries exceeded
            logger.error(
                "Sub-agent %s failed after %d attempts: %s",
                agent_type.value,
                attempt + 1,
                str(e),
            )
            break

    # Clear active_sub_agent on failure
    deps.active_sub_agent = None

    return DelegationResult(
        success=False,
        error=str(last_error) if last_error else "Unknown error",
        response="",
        files_modified=[],
    )


# =============================================================================
# Delegation Tools
# =============================================================================


@register_tool(
    category=ToolCategory.DELEGATION,
    display_text="Delegating to Research agent",
    key_arg="task",
)
async def delegate_to_research(
    ctx: RunContext[RouterDeps],
    input: DelegationInput,
) -> DelegationResult:
    """Delegate a task to the Research agent.

    The Research agent specializes in:
    - Finding information via web search
    - Analyzing code and documentation
    - Gathering background research
    - Saving research findings to .shotgun/research.md

    Args:
        ctx: RunContext with RouterDeps.
        input: DelegationInput with task and optional context_hint.

    Returns:
        DelegationResult with the research findings.
    """
    return await _run_sub_agent(
        ctx,
        AgentType.RESEARCH,
        input.task,
        input.context_hint,
    )


@register_tool(
    category=ToolCategory.DELEGATION,
    display_text="Delegating to Specification agent",
    key_arg="task",
)
async def delegate_to_specification(
    ctx: RunContext[RouterDeps],
    input: DelegationInput,
) -> DelegationResult:
    """Delegate a task to the Specification agent.

    The Specification agent specializes in:
    - Writing and updating .shotgun/specification.md
    - Creating Pydantic contracts in .shotgun/contracts/
    - Defining technical requirements and interfaces

    Args:
        ctx: RunContext with RouterDeps.
        input: DelegationInput with task and optional context_hint.

    Returns:
        DelegationResult with the specification updates.
    """
    return await _run_sub_agent(
        ctx,
        AgentType.SPECIFY,
        input.task,
        input.context_hint,
    )


@register_tool(
    category=ToolCategory.DELEGATION,
    display_text="Delegating to Plan agent",
    key_arg="task",
)
async def delegate_to_plan(
    ctx: RunContext[RouterDeps],
    input: DelegationInput,
) -> DelegationResult:
    """Delegate a task to the Plan agent.

    The Plan agent specializes in:
    - Writing and updating .shotgun/plan.md
    - Creating implementation plans with stages
    - Defining technical approach and architecture

    Args:
        ctx: RunContext with RouterDeps.
        input: DelegationInput with task and optional context_hint.

    Returns:
        DelegationResult with the plan updates.
    """
    return await _run_sub_agent(
        ctx,
        AgentType.PLAN,
        input.task,
        input.context_hint,
    )


@register_tool(
    category=ToolCategory.DELEGATION,
    display_text="Delegating to Tasks agent",
    key_arg="task",
)
async def delegate_to_tasks(
    ctx: RunContext[RouterDeps],
    input: DelegationInput,
) -> DelegationResult:
    """Delegate a task to the Tasks agent.

    The Tasks agent specializes in:
    - Writing and updating .shotgun/tasks.md
    - Creating actionable implementation tasks
    - Breaking down work into manageable items

    Args:
        ctx: RunContext with RouterDeps.
        input: DelegationInput with task and optional context_hint.

    Returns:
        DelegationResult with the task list updates.
    """
    return await _run_sub_agent(
        ctx,
        AgentType.TASKS,
        input.task,
        input.context_hint,
    )


@register_tool(
    category=ToolCategory.DELEGATION,
    display_text="Delegating to Export agent",
    key_arg="task",
)
async def delegate_to_export(
    ctx: RunContext[RouterDeps],
    input: DelegationInput,
) -> DelegationResult:
    """Delegate a task to the Export agent.

    The Export agent specializes in:
    - Exporting artifacts and deliverables
    - Generating outputs to .shotgun/export/
    - Creating documentation exports

    Args:
        ctx: RunContext with RouterDeps.
        input: DelegationInput with task and optional context_hint.

    Returns:
        DelegationResult with the export results.
    """
    return await _run_sub_agent(
        ctx,
        AgentType.EXPORT,
        input.task,
        input.context_hint,
    )
