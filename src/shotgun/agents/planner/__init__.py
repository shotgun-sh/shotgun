"""Planner Agent - The expensive-model orchestrator for complex tasks.

The Planner agent runs on the user's expensive model and handles:
- Creating and managing execution plans
- Delegating work to specialized sub-agents
- Complex multi-step task orchestration

It is invoked via escalation from the cheap Router agent.
"""

from shotgun.agents.planner.planner import create_planner_agent, run_planner_agent

__all__ = [
    "create_planner_agent",
    "run_planner_agent",
]
