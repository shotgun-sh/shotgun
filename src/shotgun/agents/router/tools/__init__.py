"""Router tools package."""

from shotgun.agents.router.tools.delegation_tools import (
    delegate_to_export,
    delegate_to_plan,
    delegate_to_research,
    delegate_to_specification,
    delegate_to_tasks,
)
from shotgun.agents.router.tools.plan_tools import (
    add_step,
    create_plan,
    mark_step_done,
    remove_step,
)

__all__ = [
    # Plan management tools
    "create_plan",
    "mark_step_done",
    "add_step",
    "remove_step",
    # Delegation tools
    "delegate_to_research",
    "delegate_to_specification",
    "delegate_to_plan",
    "delegate_to_tasks",
    "delegate_to_export",
]
