"""Tasks agent factory and functions using Pydantic AI with file-based memory."""

from pydantic_ai import Agent, RunContext

from shotgun.logging_config import setup_logger

from .common import (
    create_base_agent,
    create_usage_limits,
    ensure_file_exists,
    get_file_history,
    get_interactive_note,
)
from .models import AgentDeps

logger = setup_logger(__name__)


def _build_tasks_agent_system_prompt(ctx: RunContext[AgentDeps]) -> str:
    """Build the system prompt for the tasks agent.

    Args:
        ctx: RunContext containing AgentDeps with interactive_mode and other settings

    Returns:
        The complete system prompt string for the tasks agent
    """
    interactive_note = get_interactive_note(ctx.deps.interactive_mode, "task lists")

    return (
        """You are a task management assistant with access to research data and project plans.
"""
        + interactive_note
        + """

Your job is to:
1. FIRST: Load previous research from research.md using read_file("research.md") if available
2. SECOND: Load existing plan from plan.md using read_file("plan.md") if available
3. THIRD: Load existing tasks from tasks.md using read_file("tasks.md") if it exists
4. ANALYZE: Understand current context and the user's task creation/update request
5. CREATE/UPDATE: Generate or modify actionable tasks based on research and plans
6. WRITE: Save the updated tasks to tasks.md using write_file("tasks.md", content)

TASK CREATION PRINCIPLES:
- Base tasks on available research findings and plan requirements
- Create specific, actionable tasks with clear acceptance criteria
- Include effort estimates and priority levels
- Organize tasks by categories or project phases
- Consider dependencies between tasks
- Make tasks testable and verifiable
- Align with goals and steps from the plan
- Include both development and testing/validation tasks

"""
        + (
            "USER INTERACTION - ASK CLARIFYING QUESTIONS:"
            if ctx.deps.interactive_mode
            else "NON-INTERACTIVE MODE - MAKE REASONABLE ASSUMPTIONS:"
        )
        + """
"""
        + (
            """- ALWAYS ask clarifying questions when the request is vague or ambiguous
- Use ask_user tool to gather specific details about:
  - Specific features or functionality to prioritize
  - Technical constraints or preferences
  - Timeline and resource constraints
  - Definition of "done" for key deliverables
  - Testing and quality requirements
  - Team size and skill levels
  - Integration requirements
- Ask follow-up questions to ensure tasks are properly scoped
- Confirm task priorities and dependencies with the user
- Better to ask 2-3 targeted questions than create generic tasks"""
            if ctx.deps.interactive_mode
            else """- Make reasonable assumptions based on industry best practices
- Use sensible defaults for technical constraints and timelines
- Create tasks with standard definitions of "done"
- Assume typical team sizes and skill levels
- Include common testing and quality assurance tasks
- Create tasks that follow standard project management practices"""
        )
        + """

INTEGRATION WITH RESEARCH & PLAN:
- Reference specific findings from research.md when creating tasks
- Align tasks with action steps outlined in plan.md
- Consider technical feasibility based on research
- Include tasks for addressing challenges identified in plan
- Create validation/testing tasks for success criteria from plan
- Break down high-level plan steps into granular, executable tasks

IMPORTANT RULES:
- Make at most 1 tasks file write per request
- Always base tasks on available research and plan when relevant
- Create specific, testable tasks rather than vague objectives
- Consider realistic timelines and team capabilities
- Include both implementation and validation/testing tasks
"""
        + (
            "- When in doubt about any aspect of the requirements, ASK before proceeding"
            if ctx.deps.interactive_mode
            else "- When in doubt, make reasonable assumptions and proceed with best practices"
        )
        + """
- Ensure tasks are properly prioritized and sequenced
"""
    )


def create_tasks_agent(deps: AgentDeps | None = None) -> Agent[AgentDeps, str]:
    """Create a tasks agent with file management capabilities.

    Args:
        deps: Optional agent dependencies for conditional tool registration

    Returns:
        Configured Pydantic AI agent for task management
    """
    logger.debug("Initializing tasks agent")
    return create_base_agent(_build_tasks_agent_system_prompt, None, deps)


async def run_tasks_agent(
    agent: Agent[AgentDeps, str], instruction: str, deps: AgentDeps
) -> str:
    """Create or update tasks based on the given instruction.

    Args:
        agent: The configured tasks agent
        instruction: The task creation/update instruction
        deps: Agent dependencies

    Returns:
        Summary of the task creation process and results
    """
    logger.debug("📋 Starting task creation for instruction: %s", instruction)

    # Ensure tasks.md exists
    ensure_file_exists("tasks.md", "# Tasks")

    # Let the agent use its tools to read existing tasks, plan, and research
    full_prompt = f"Create or update tasks based on: {instruction}"

    try:
        # Create usage limits for responsible API usage
        usage_limits = create_usage_limits()

        # Run the agent asynchronously with deps and usage limits
        result = await agent.run(full_prompt, deps=deps, usage_limits=usage_limits)
        summary = str(result.output)

        logger.debug("✅ Task creation completed successfully")
        return summary

    except Exception as e:
        logger.error("❌ Task creation failed: %s", str(e))
        return f"Task creation failed: {str(e)}"


def get_tasks_history() -> str:
    """Get the full tasks history from the file.

    Returns:
        Tasks history content or fallback message
    """
    return get_file_history("tasks.md")
