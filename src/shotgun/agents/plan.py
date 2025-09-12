"""Plan agent factory and functions using Pydantic AI with file-based memory."""

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


def _build_plan_agent_system_prompt(ctx: RunContext[AgentDeps]) -> str:
    """Build the system prompt for the plan agent.

    Args:
        ctx: RunContext containing AgentDeps with interactive_mode and other settings

    Returns:
        The complete system prompt string for the plan agent
    """
    interactive_note = get_interactive_note(ctx.deps.interactive_mode, "plans")

    return (
        """You are a planning assistant with access to research data and existing plans.
"""
        + interactive_note
        + """

Your job is to:
1. FIRST: Load previous research from research.md using read_file("research.md")
2. SECOND: Load existing plan from plan.md using read_file("plan.md") if it exists
3. ANALYZE: Understand the current context and user's goal/request
4. PLAN: Create or update a comprehensive, actionable plan
5. WRITE: Save the plan to plan.md using write_file("plan.md", content)

PLANNING PRINCIPLES:
- Build on existing research and previous plans
- Create specific, measurable, achievable, relevant, time-bound (SMART) goals
- Break down complex objectives into manageable phases and milestones
- Consider dependencies between tasks and potential risks
- Include resource requirements and success criteria
- Be explicit about whether you're creating new or updating existing content
- Preserve valuable information from existing plans unless specifically asked to remove it

"""
        + (
            "USER INTERACTION - REDUCE UNCERTAINTY:"
            if ctx.deps.interactive_mode
            else "NON-INTERACTIVE MODE - MAKE REASONABLE ASSUMPTIONS:"
        )
        + """
"""
        + (
            """- ALWAYS ask clarifying questions when the goal is vague or ambiguous
- Use ask_user tool frequently to gather specific details about:
  - Project scope and boundaries
  - Target timeline and deadlines
  - Available resources and constraints
  - Success criteria and measurable outcomes
  - Technology preferences or requirements
  - Target audience or users
  - Budget considerations
  - Risk tolerance and priorities
- Ask follow-up questions to drill down into specifics
- Don't assume - ask for confirmation of your understanding
- Better to ask 2-3 targeted questions than create a generic plan
- Confirm major changes to existing plans before proceeding"""
            if ctx.deps.interactive_mode
            else """- Make reasonable assumptions based on industry best practices
- Use sensible defaults when specific details are not provided
- Focus on creating a practical, actionable plan
- Include common project phases and considerations
- Assume standard timelines and resource allocations"""
        )
        + """

IMPORTANT RULES:
- Make at most 1 plan file write per request
- Always base plans on available research when relevant
- Create actionable, specific steps rather than vague suggestions
- Consider feasibility and prioritize high-impact actions
- Be concise but comprehensive
"""
        + (
            "- When in doubt about any aspect of the goal, ASK before proceeding"
            if ctx.deps.interactive_mode
            else "- When in doubt, make reasonable assumptions and proceed with best practices"
        )
    )


def create_plan_agent(deps: AgentDeps | None = None) -> Agent[AgentDeps, str]:
    """Create a plan agent with file management capabilities.

    Args:
        deps: Optional agent dependencies for conditional tool registration

    Returns:
        Configured Pydantic AI agent for planning tasks
    """
    logger.debug("Initializing plan agent")
    return create_base_agent(_build_plan_agent_system_prompt, None, deps)


async def run_plan_agent(
    agent: Agent[AgentDeps, str], goal: str, deps: AgentDeps
) -> str:
    """Create or update a plan based on the given goal.

    Args:
        agent: The configured plan agent
        goal: The planning goal or instruction
        deps: Agent dependencies

    Returns:
        Summary of the planning process and results
    """
    logger.debug("📋 Starting planning for goal: %s", goal)

    # Ensure plan.md exists
    ensure_file_exists("plan.md", "# Plan")

    # Let the agent use its tools to read existing plan and research
    full_prompt = f"Create a comprehensive plan for: {goal}"

    try:
        # Create usage limits for responsible API usage
        usage_limits = create_usage_limits()

        # Run the agent asynchronously with deps and usage limits
        result = await agent.run(full_prompt, deps=deps, usage_limits=usage_limits)
        summary = str(result.output)

        logger.debug("✅ Planning completed successfully")
        return summary

    except Exception as e:
        logger.error("❌ Planning failed: %s", str(e))
        return f"Planning failed: {str(e)}"


def get_plan_history() -> str:
    """Get the full plan history from the file.

    Returns:
        Plan history content or fallback message
    """
    return get_file_history("plan.md")
