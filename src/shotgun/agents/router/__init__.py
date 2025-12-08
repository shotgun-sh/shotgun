"""Router agent module.

The Router Agent is the single point of contact for users, orchestrating
work across specialized sub-agents (Research, Specify, Plan, Tasks, Export).
"""

from shotgun.agents.router.router import create_router_agent, run_router_agent

__all__ = [
    "create_router_agent",
    "run_router_agent",
]
