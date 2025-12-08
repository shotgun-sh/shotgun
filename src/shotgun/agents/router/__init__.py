"""Router Agent - The intelligent orchestrator for shotgun agents."""

from shotgun.agents.router.models import (
    CascadeScope,
    CreatePlanInput,
    DelegationInput,
    DelegationResult,
    ExecutionPlan,
    ExecutionStep,
    ExecutionStepInput,
    MarkStepDoneInput,
    PlanApprovalStatus,
    RemoveStepInput,
    RouterDeps,
    RouterMode,
    StepCheckpointAction,
    SubAgentResult,
    SubAgentResultStatus,
    ToolResult,
)
from shotgun.agents.router.router import create_router_agent, run_router_agent

__all__ = [
    # Agent factory
    "create_router_agent",
    "run_router_agent",
    # Enums
    "RouterMode",
    "PlanApprovalStatus",
    "StepCheckpointAction",
    "CascadeScope",
    "SubAgentResultStatus",
    # Plan models
    "ExecutionStep",
    "ExecutionPlan",
    # Tool I/O models
    "ExecutionStepInput",
    "CreatePlanInput",
    "MarkStepDoneInput",
    "RemoveStepInput",
    "DelegationInput",
    "ToolResult",
    "DelegationResult",
    "SubAgentResult",
    # Deps
    "RouterDeps",
]
