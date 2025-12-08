"""
Router Agent Data Models.

Type definitions for the Router Agent MVP.
These models define the contracts between router, sub-agents, and UI.
"""

from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

# Import SubAgentContext from main models to avoid duplication
from shotgun.agents.models import SubAgentContext

if TYPE_CHECKING:
    from pydantic_ai import Agent

    from shotgun.agents.models import AgentDeps, AgentResponse, AgentType

# Re-export for backwards compatibility
__all__ = ["SubAgentContext"]


class RouterMode(StrEnum):
    """Router execution modes."""

    PLANNING = "planning"  # Incremental, confirmatory - asks before acting
    DRAFTING = "drafting"  # Auto-execute - runs full plan without stopping


class PlanApprovalStatus(StrEnum):
    """Status of plan approval in Planning mode."""

    PENDING = "pending"  # Plan shown, awaiting user decision
    APPROVED = "approved"  # User approved, ready to execute
    REJECTED = "rejected"  # User wants to clarify/modify
    SKIPPED = "skipped"  # Simple request, no approval needed


class StepCheckpointAction(StrEnum):
    """User action at step checkpoint (Planning mode only)."""

    CONTINUE = "continue"  # Proceed to next step
    MODIFY = "modify"  # User wants to adjust the plan
    STOP = "stop"  # Stop execution, keep remaining steps


class CascadeScope(StrEnum):
    """Scope for cascade updates to dependent files."""

    ALL = "all"  # Update all dependent files
    PLAN_ONLY = "plan_only"  # Update only plan.md
    TASKS_ONLY = "tasks_only"  # Update only tasks.md
    NONE = "none"  # Don't update any dependents


class ExecutionStep(BaseModel):
    """A single step in an execution plan."""

    id: str = Field(
        ...,
        description="Human-readable identifier (e.g., 'research-oauth', 'write-spec')",
    )
    title: str = Field(..., description="Short title SHOWN to user in plan display")
    objective: str = Field(
        ..., description="Detailed goal HIDDEN from user (for sub-agent)"
    )
    success_criteria: list[str] = Field(
        default_factory=list, description="Completion checklist HIDDEN from user"
    )
    done: bool = Field(
        default=False, description="Whether this step has been completed"
    )
    affects_files: list[str] = Field(
        default_factory=list,
        description="Files this step will modify (e.g., ['specification.md'])",
    )
    dependent_files: list[str] = Field(
        default_factory=list,
        description="Files that depend on affected_files (for cascade confirmation)",
    )


class ExecutionPlan(BaseModel):
    """
    Router's execution plan.

    Stored externally in .shotgun/execution_plan.json to keep
    router context lean.
    """

    goal: str = Field(..., description="High-level goal from user request")
    steps: list[ExecutionStep] = Field(
        default_factory=list, description="Ordered list of execution steps"
    )
    current_step_index: int = Field(
        default=0, description="Index of currently executing step (for checkpoints)"
    )

    def needs_approval(self) -> bool:
        """
        Determine if plan requires user approval in Planning mode.

        Single-step plans execute immediately.
        Multi-step plans require approval.
        """
        return len(self.steps) > 1

    def current_step(self) -> ExecutionStep | None:
        """Get the current step being executed."""
        if 0 <= self.current_step_index < len(self.steps):
            return self.steps[self.current_step_index]
        return None

    def next_step(self) -> ExecutionStep | None:
        """Get the next step to execute."""
        next_idx = self.current_step_index + 1
        if next_idx < len(self.steps):
            return self.steps[next_idx]
        return None

    def is_complete(self) -> bool:
        """Check if all steps are done."""
        return all(step.done for step in self.steps)

    def pending_steps(self) -> list[ExecutionStep]:
        """Get steps that haven't been completed."""
        return [step for step in self.steps if not step.done]


class SubAgentResultStatus(StrEnum):
    """Status of sub-agent execution."""

    SUCCESS = "success"
    PARTIAL = "partial"  # Interrupted or incomplete
    ERROR = "error"
    NEEDS_CLARIFICATION = "needs_clarification"


class SubAgentResult(BaseModel):
    """Result from a sub-agent delegation."""

    status: SubAgentResultStatus = Field(..., description="Execution status")
    response: str = Field(default="", description="Sub-agent's response text")
    questions: list[str] = Field(
        default_factory=list,
        description="Clarifying questions from sub-agent (if any)",
    )
    partial_response: str = Field(default="", description="Partial work if interrupted")
    error: str | None = Field(
        default=None, description="Error message if status is ERROR"
    )
    is_retryable: bool = Field(
        default=False, description="Whether the error is transient and retryable"
    )
    files_modified: list[str] = Field(
        default_factory=list,
        description="Files that were modified by this sub-agent",
    )


class QueuedUserMessage(BaseModel):
    """User message received during sub-agent execution."""

    content: str = Field(..., description="The user's message text")
    timestamp: float = Field(
        ..., description="Unix timestamp when message was received"
    )


class ClarifyingQuestion(BaseModel):
    """A clarifying question to ask the user before starting work."""

    question: str = Field(..., description="The question text")
    default: str | None = Field(
        default=None, description="Optional default answer (e.g., 'no, can add later')"
    )
    options: list[str] = Field(
        default_factory=list, description="Optional predefined answer choices"
    )


class CascadeConfirmation(BaseModel):
    """Request for user confirmation before updating dependent files."""

    updated_file: str = Field(..., description="File that was just updated")
    dependent_files: list[str] = Field(
        ..., description="Files that depend on the updated file"
    )
    suggested_scope: CascadeScope = Field(
        default=CascadeScope.ALL, description="Suggested default scope for updates"
    )


# File dependency map for cascade confirmation
FILE_DEPENDENCIES: dict[str, list[str]] = {
    "research.md": ["specification.md", "plan.md", "tasks.md"],
    "specification.md": ["plan.md", "tasks.md"],
    "plan.md": ["tasks.md"],
    "tasks.md": [],  # Leaf node, no dependents
}


def get_dependent_files(file_path: str) -> list[str]:
    """Get files that depend on the given file."""
    # Normalize path to just the filename
    file_name = file_path.split("/")[-1]
    return FILE_DEPENDENCIES.get(file_name, [])


class RouterDeps(BaseModel):
    """
    Router-specific dependencies extending AgentDeps.

    This model is used as the deps type for the router agent and includes
    all the state needed for plan management and mode-aware execution.
    """

    router_mode: RouterMode = Field(
        default=RouterMode.PLANNING,
        description="Current router execution mode",
    )
    pending_plan: ExecutionPlan | None = Field(
        default=None,
        description="Plan awaiting user approval",
    )
    approval_status: PlanApprovalStatus = Field(
        default=PlanApprovalStatus.SKIPPED,
        description="Current approval state for pending plan",
    )
    active_sub_agent: "AgentType | None" = Field(
        default=None,
        description="Currently executing sub-agent (for mode indicator)",
    )
    queued_messages: list[QueuedUserMessage] = Field(
        default_factory=list,
        description="User messages received during sub-agent execution",
    )
    sub_agent_cache: "dict[str, tuple[Agent[AgentDeps, AgentResponse], AgentDeps]]" = (
        Field(
            default_factory=dict,
            description="Cache of sub-agent instances (agent, deps) by agent type",
        )
    )
    current_step_index: int = Field(
        default=0,
        description="Index of current step for checkpoint tracking",
    )
    awaiting_cascade_confirmation: bool = Field(
        default=False,
        description="Whether waiting for user cascade decision",
    )
    is_delegating: bool = Field(
        default=False,
        description="Whether currently delegating to a sub-agent",
    )
