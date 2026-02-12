"""Router tools package."""

from typing import Any

from pydantic_ai import Agent, Tool

from shotgun.agents.router.tools.delegation_tools import (
    delegate_to_export,
    delegate_to_plan,
    delegate_to_research,
    delegate_to_specification,
    delegate_to_tasks,
    prepare_delegation_tool,
)
from shotgun.agents.router.tools.plan_tools import (
    add_step,
    create_plan,
    mark_step_done,
    remove_step,
)
from shotgun.agents.tools import read_file


def create_delegation_tools() -> list[Tool]:
    """Create the standard delegation tool list with prepare functions."""
    return [
        Tool(delegate_to_research, prepare=prepare_delegation_tool),  # type: ignore[arg-type]
        Tool(delegate_to_specification, prepare=prepare_delegation_tool),  # type: ignore[arg-type]
        Tool(delegate_to_plan, prepare=prepare_delegation_tool),  # type: ignore[arg-type]
        Tool(delegate_to_tasks, prepare=prepare_delegation_tool),  # type: ignore[arg-type]
        Tool(delegate_to_export, prepare=prepare_delegation_tool),  # type: ignore[arg-type]
    ]


def register_plan_management_tools(agent: Agent[Any, Any]) -> None:
    """Register plan management + read_file tools on an agent."""
    agent.tool(create_plan)
    agent.tool(mark_step_done)
    agent.tool(add_step)
    agent.tool(remove_step)
    agent.tool(read_file)


__all__ = [
    "add_step",
    "create_delegation_tools",
    "create_plan",
    "mark_step_done",
    "register_plan_management_tools",
    "remove_step",
]
