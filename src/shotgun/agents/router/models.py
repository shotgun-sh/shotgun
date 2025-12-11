"""
Router Agent Data Models.

Type definitions for the Router Agent MVP.
These models define the contracts between router, sub-agents, and UI.

IMPORTANT: All tool inputs/outputs must use Pydantic models - no raw dict/list/tuple.
"""

from collections.abc import AsyncIterable, Awaitable, Callable
from enum import StrEnum
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from shotgun.agents.models import AgentDeps

from pydantic import BaseModel, Field

# Import SubAgentContext from the main models module
from shotgun.agents.models import SubAgentContext

# Re-export SubAgentContext for convenience
__all__ = ["SubAgentContext"]


# =============================================================================
# Mode & Status Enums
# =============================================================================


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


class SubAgentResultStatus(StrEnum):
    """Status of sub-agent execution."""

    SUCCESS = "success"
    PARTIAL = "partial"  # Interrupted or incomplete
    ERROR = "error"
    NEEDS_CLARIFICATION = "needs_clarification"


# =============================================================================
# Execution Plan Models (In-Memory, Not File-Based)
# =============================================================================


class ExecutionStep(BaseModel):
    """A single step in an execution plan."""

    id: str = Field(
        ..., description="Human-readable identifier (e.g., 'research-oauth')"
    )
    title: str = Field(..., description="Short title SHOWN to user in plan display")
    objective: str = Field(
        ..., description="Detailed goal HIDDEN from user (for sub-agent)"
    )
    done: bool = Field(
        default=False, description="Whether this step has been completed"
    )


class ExecutionPlan(BaseModel):
    """
    Router's execution plan.

    Stored IN-MEMORY in RouterDeps, NOT in a file.
    Shown to router in system status message every turn.
    """

    goal: str = Field(..., description="High-level goal from user request")
    steps: list[ExecutionStep] = Field(
        default_factory=list, description="Ordered list of execution steps"
    )
    current_step_index: int = Field(
        default=0, description="Index of currently executing step"
    )

    def needs_approval(self) -> bool:
        """
        Determine if plan requires user approval in Planning mode.

        All plans require approval - user should always see and approve
        the plan before execution begins.
        """
        return len(self.steps) >= 1

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

    def format_for_display(self) -> str:
        """Format plan for display in system status message."""
        lines = [f"**Goal:** {self.goal}", "", "**Steps:**"]
        for i, step in enumerate(self.steps):
            marker = "✅" if step.done else "⬜"
            current = " ◀" if i == self.current_step_index and not step.done else ""
            lines.append(f"{i + 1}. {marker} {step.title}{current}")
        return "\n".join(lines)


# =============================================================================
# Tool Input Models (Pydantic only - no dict/list/tuple)
# =============================================================================


class ExecutionStepInput(BaseModel):
    """Input model for creating a step."""

    id: str = Field(..., description="Human-readable identifier")
    title: str = Field(..., description="Short title shown to user")
    objective: str = Field(..., description="Detailed goal for sub-agent")


class CreatePlanInput(BaseModel):
    """Input model for create_plan tool."""

    goal: str = Field(..., description="High-level goal from user request")
    steps: list[ExecutionStepInput] = Field(..., description="Ordered list of steps")


class MarkStepDoneInput(BaseModel):
    """Input model for mark_step_done tool."""

    step_id: str = Field(..., description="ID of the step to mark as done")


class AddStepInput(BaseModel):
    """Input model for add_step tool."""

    step: ExecutionStepInput = Field(..., description="The step to add")
    after_step_id: str | None = Field(
        default=None, description="Insert after this step ID (None = append to end)"
    )


class RemoveStepInput(BaseModel):
    """Input model for remove_step tool."""

    step_id: str = Field(..., description="ID of the step to remove")


class DelegationInput(BaseModel):
    """Input model for delegation tools."""

    task: str = Field(..., description="The task to delegate to the sub-agent")
    context_hint: str | None = Field(
        default=None, description="Optional context to help the sub-agent"
    )


# =============================================================================
# Tool Output Models (Pydantic only - no dict/list/tuple)
# =============================================================================


class ToolResult(BaseModel):
    """Generic result from a tool operation."""

    success: bool = Field(..., description="Whether the operation succeeded")
    message: str = Field(..., description="Human-readable result message")


class DelegationResult(BaseModel):
    """Result from a sub-agent delegation."""

    success: bool = Field(..., description="Whether delegation succeeded")
    response: str = Field(default="", description="Sub-agent's response text")
    files_modified: list[str] = Field(
        default_factory=list, description="Files modified by sub-agent"
    )
    has_questions: bool = Field(
        default=False, description="Whether sub-agent has clarifying questions"
    )
    questions: list[str] = Field(
        default_factory=list, description="Clarifying questions from sub-agent"
    )
    error: str | None = Field(default=None, description="Error message if failed")


class SubAgentResult(BaseModel):
    """Full result from a sub-agent execution."""

    status: SubAgentResultStatus = Field(..., description="Execution status")
    response: str = Field(default="", description="Sub-agent's response text")
    questions: list[str] = Field(
        default_factory=list, description="Clarifying questions from sub-agent (if any)"
    )
    partial_response: str = Field(default="", description="Partial work if interrupted")
    error: str | None = Field(
        default=None, description="Error message if status is ERROR"
    )
    is_retryable: bool = Field(
        default=False, description="Whether the error is transient and retryable"
    )
    files_modified: list[str] = Field(
        default_factory=list, description="Files modified by this sub-agent"
    )


# =============================================================================
# Pending State Models (for UI coordination)
# =============================================================================


class PendingCheckpoint(BaseModel):
    """Pending checkpoint state for Planning mode step-by-step execution.

    Set by mark_step_done tool to trigger checkpoint UI.
    """

    completed_step: ExecutionStep = Field(
        ..., description="The step that was just completed"
    )
    next_step: ExecutionStep | None = Field(
        default=None, description="The next step to execute, or None if plan complete"
    )


class PendingCascade(BaseModel):
    """Pending cascade confirmation state for Planning mode.

    Set when a file with dependents is modified and cascade confirmation is needed.
    """

    updated_file: str = Field(..., description="The file that was just updated")
    dependent_files: list[str] = Field(
        default_factory=list, description="Files that depend on the updated file"
    )


class PendingApproval(BaseModel):
    """Pending approval state for Planning mode multi-step plans.

    Set by create_plan tool when plan.needs_approval() returns True
    (i.e., the plan has more than one step) in Planning mode.
    """

    plan: "ExecutionPlan" = Field(..., description="The plan that needs user approval")


# =============================================================================
# File Dependency Map (for Cascade Confirmation)
# =============================================================================

FILE_DEPENDENCIES: Final[dict[str, tuple[str, ...]]] = {
    "research.md": ("specification.md", "plan.md", "tasks.md"),
    "specification.md": ("plan.md", "tasks.md"),
    "plan.md": ("tasks.md",),
    "tasks.md": (),  # Leaf node, no dependents
}


def get_dependent_files(file_path: str) -> list[str]:
    """Get files that depend on the given file."""
    # Normalize path to just filename
    file_name = file_path.split("/")[-1]
    return list(FILE_DEPENDENCIES.get(file_name, ()))


# =============================================================================
# RouterDeps (extends AgentDeps)
# =============================================================================

# Import AgentDeps for inheritance - must be done here to avoid circular imports
from shotgun.agents.models import AgentDeps, AgentType  # noqa: E402

# Type alias for sub-agent cache entries
# Each entry is a tuple of (Agent instance, AgentDeps instance)
# Using object for agent to avoid forward reference issues with pydantic
SubAgentCacheEntry = tuple[object, AgentDeps]

# Type alias for event stream handler callback
# Matches the signature expected by pydantic_ai's agent.run()
# Using object to avoid forward reference issues with pydantic
EventStreamHandler = Callable[[object, AsyncIterable[object]], Awaitable[None]]


class RouterDeps(AgentDeps):
    """
    Router-specific dependencies that extend AgentDeps.

    This class contains router-specific state on top of the base AgentDeps.
    It is used by the router agent and its tools to manage execution plans
    and sub-agent orchestration.

    Fields:
        router_mode: Current execution mode (Planning or Drafting)
        current_plan: The execution plan stored in-memory (NOT file-based)
        approval_status: Current approval state for the plan
        active_sub_agent: Which sub-agent is currently executing (for UI)
        is_executing: Whether a plan is currently being executed
        sub_agent_cache: Cached sub-agent instances for lazy initialization
    """

    router_mode: RouterMode = Field(default=RouterMode.PLANNING)
    current_plan: ExecutionPlan | None = Field(default=None)
    approval_status: PlanApprovalStatus = Field(default=PlanApprovalStatus.SKIPPED)
    active_sub_agent: AgentType | None = Field(default=None)
    is_executing: bool = Field(default=False)
    sub_agent_cache: dict[AgentType, SubAgentCacheEntry] = Field(default_factory=dict)
    # Checkpoint state for Planning mode step-by-step execution
    # Set by mark_step_done tool to trigger checkpoint UI
    # Excluded from serialization as it's transient UI state
    pending_checkpoint: PendingCheckpoint | None = Field(default=None, exclude=True)
    # Cascade confirmation state for Planning mode
    # Set when a file with dependents is modified
    # Excluded from serialization as it's transient UI state
    pending_cascade: PendingCascade | None = Field(default=None, exclude=True)
    # Approval state for Planning mode multi-step plans
    # Set by create_plan tool when plan.needs_approval() returns True
    # Excluded from serialization as it's transient UI state
    pending_approval: PendingApproval | None = Field(default=None, exclude=True)
    # Completion state for Drafting mode
    # Set by mark_step_done when plan completes in drafting mode
    # Excluded from serialization as it's transient UI state
    pending_completion: bool = Field(default=False, exclude=True)
    # Event stream handler for forwarding sub-agent streaming events to UI
    # This is set by the AgentManager when running the router with streaming
    # Excluded from serialization as it's a callable
    parent_stream_handler: EventStreamHandler | None = Field(
        default=None,
        exclude=True,
        description="Event stream handler from parent context for forwarding sub-agent events",
    )
    # Callback for notifying TUI when plan changes (Stage 11)
    # Set by ChatScreen to receive plan updates for the Plan Panel widget
    # Excluded from serialization as it's a callable
    on_plan_changed: Callable[["ExecutionPlan | None"], None] | None = Field(
        default=None,
        exclude=True,
        description="Callback to notify TUI when plan changes",
    )
