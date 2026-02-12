"""Escalation tool for the Router agent to escalate to the Planner.

When the cheap Router determines a task requires planning, delegation,
or complex multi-step work, it uses this tool to escalate to the
Planner agent which runs on the expensive model.
"""

from pydantic import BaseModel, Field
from pydantic_ai import RunContext

from shotgun.agents.router.models import RouterDeps
from shotgun.agents.tools.registry import ToolCategory, register_tool
from shotgun.logging_config import get_logger

logger = get_logger(__name__)


class EscalationInput(BaseModel):
    """Input for the escalate_to_planner tool."""

    reason: str = Field(
        ...,
        description="Why this request needs the Planner (e.g., 'needs multi-step plan', 'requires delegation to sub-agents')",
    )


class EscalationResult(BaseModel):
    """Result from the escalate_to_planner tool."""

    success: bool = Field(default=True, description="Always succeeds")
    message: str = Field(description="Confirmation message")


@register_tool(
    category=ToolCategory.PLANNING,
    display_text="Escalating to Planner",
    key_arg="reason",
)
async def escalate_to_planner(
    ctx: RunContext[RouterDeps],
    input: EscalationInput,
) -> EscalationResult:
    """Escalate the current request to the Planner agent.

    Use this when the user's request requires:
    - Creating or modifying execution plans
    - Delegating work to sub-agents (Research, Specify, Plan, Tasks, Export)
    - Multi-step tasks that need coordination
    - Complex analysis or file modifications

    The Planner has access to plan management tools and delegation tools
    that the Router does not have.

    Args:
        ctx: RunContext with RouterDeps.
        input: EscalationInput with reason for escalation.

    Returns:
        EscalationResult confirming escalation was requested.
    """
    deps = ctx.deps
    deps.escalation_requested = True
    deps.escalation_reason = input.reason

    logger.info("Escalation to Planner requested: %s", input.reason)

    return EscalationResult(
        success=True,
        message="Escalating to Planner for detailed handling.",
    )
