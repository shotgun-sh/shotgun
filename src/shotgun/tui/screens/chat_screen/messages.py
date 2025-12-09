"""Message types for ChatScreen communication.

This module defines Textual message types used for communication
between widgets and the ChatScreen, particularly for step checkpoints
and cascade confirmation in the Router's Planning mode.
"""

from textual.message import Message

from shotgun.agents.models import AgentType
from shotgun.agents.router.models import CascadeScope, ExecutionPlan, ExecutionStep

__all__ = [
    # Step checkpoint messages (Stage 4)
    "StepCompleted",
    "CheckpointContinue",
    "CheckpointModify",
    "CheckpointStop",
    # Cascade confirmation messages (Stage 5)
    "CascadeConfirmationRequired",
    "CascadeConfirmed",
    "CascadeDeclined",
    # Plan approval messages (Stage 7)
    "PlanApprovalRequired",
    "PlanApproved",
    "PlanRejected",
    # Sub-agent lifecycle messages (Stage 8)
    "SubAgentStarted",
    "SubAgentCompleted",
    # Plan panel messages (Stage 11)
    "PlanUpdated",
    "PlanPanelClosed",
]


class StepCompleted(Message):
    """Posted when a plan step completes in Planning mode.

    This message triggers the checkpoint UI to appear, allowing the user
    to choose whether to continue, modify the plan, or stop execution.

    Attributes:
        step: The step that was just completed.
        next_step: The next step to execute, or None if this was the last step.
    """

    def __init__(self, step: ExecutionStep, next_step: ExecutionStep | None) -> None:
        super().__init__()
        self.step = step
        self.next_step = next_step


class CheckpointContinue(Message):
    """Posted when user chooses to continue to next step.

    This message indicates the user wants to proceed with the next
    step in the execution plan.
    """


class CheckpointModify(Message):
    """Posted when user wants to modify the plan.

    This message indicates the user wants to return to the prompt input
    to make adjustments to the plan before continuing.
    """


class CheckpointStop(Message):
    """Posted when user wants to stop execution.

    This message indicates the user wants to halt execution while
    keeping the remaining steps in the plan as pending.
    """


# =============================================================================
# Cascade Confirmation Messages (Stage 5)
# =============================================================================


class CascadeConfirmationRequired(Message):
    """Posted when a file with dependents was modified and needs cascade confirmation.

    In Planning mode, after modifying a file like specification.md that has
    dependent files (plan.md, tasks.md), this message triggers the cascade
    confirmation UI to appear.

    Attributes:
        updated_file: The file that was just updated (e.g., "specification.md").
        dependent_files: List of files that depend on the updated file.
    """

    def __init__(self, updated_file: str, dependent_files: list[str]) -> None:
        super().__init__()
        self.updated_file = updated_file
        self.dependent_files = dependent_files


class CascadeConfirmed(Message):
    """Posted when user confirms cascade update.

    This message indicates the user wants to proceed with updating
    dependent files based on the selected scope.

    Attributes:
        scope: The scope of files to update (ALL, PLAN_ONLY, TASKS_ONLY, NONE).
    """

    def __init__(self, scope: CascadeScope) -> None:
        super().__init__()
        self.scope = scope


class CascadeDeclined(Message):
    """Posted when user declines cascade update.

    This message indicates the user does not want to update dependent
    files and will handle them manually.
    """


# =============================================================================
# Plan Approval Messages (Stage 7)
# =============================================================================


class PlanApprovalRequired(Message):
    """Posted when a multi-step plan is created and needs user approval.

    In Planning mode, after the router creates a plan with multiple steps,
    this message triggers the approval UI to appear.

    Attributes:
        plan: The execution plan that needs user approval.
    """

    def __init__(self, plan: ExecutionPlan) -> None:
        super().__init__()
        self.plan = plan


class PlanApproved(Message):
    """Posted when user approves the plan.

    This message indicates the user wants to proceed with executing
    the plan ("Go Ahead").
    """


class PlanRejected(Message):
    """Posted when user rejects the plan to clarify/modify.

    This message indicates the user wants to return to the prompt input
    to modify or clarify the request ("No, Let Me Clarify").
    """


# =============================================================================
# Sub-Agent Lifecycle Messages (Stage 8)
# =============================================================================


class SubAgentStarted(Message):
    """Posted when router starts delegating to a sub-agent.

    This message triggers the mode indicator to show the active sub-agent
    in the format "📋 Planning → Research".

    Attributes:
        agent_type: The type of sub-agent that started executing.
    """

    def __init__(self, agent_type: AgentType) -> None:
        super().__init__()
        self.agent_type = agent_type


class SubAgentCompleted(Message):
    """Posted when sub-agent delegation completes.

    This message triggers the mode indicator to clear the sub-agent
    display and return to showing just the mode.

    Attributes:
        agent_type: The type of sub-agent that completed.
    """

    def __init__(self, agent_type: AgentType) -> None:
        super().__init__()
        self.agent_type = agent_type


# =============================================================================
# Plan Panel Messages (Stage 11)
# =============================================================================


class PlanUpdated(Message):
    """Posted when the current plan changes.

    This message triggers the plan panel to auto-show/hide based on
    whether a plan exists.

    Attributes:
        plan: The updated execution plan, or None if plan was cleared.
    """

    def __init__(self, plan: ExecutionPlan | None) -> None:
        super().__init__()
        self.plan = plan


class PlanPanelClosed(Message):
    """Posted when user closes the plan panel with × button.

    This message indicates the user wants to dismiss the plan panel
    temporarily. The panel will reopen when the plan changes.
    """
