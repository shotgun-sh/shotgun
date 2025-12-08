"""Router agent tools.

This module exports all tools available to the router agent.
"""

from shotgun.agents.router.tools.cascade_tools import (
    check_dependents,
    get_file_dependencies,
)
from shotgun.agents.router.tools.plan_tools import (
    add_step,
    clear_plan,
    create_plan,
    get_plan,
    mark_step_done,
    remove_step,
    reorder_steps,
    update_step,
)

__all__ = [
    # Plan management tools
    "create_plan",
    "get_plan",
    "mark_step_done",
    "add_step",
    "remove_step",
    "update_step",
    "reorder_steps",
    "clear_plan",
    # Cascade tools
    "check_dependents",
    "get_file_dependencies",
]
