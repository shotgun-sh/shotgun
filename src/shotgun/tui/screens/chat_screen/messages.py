"""Message types for ChatScreen communication.

This module defines Textual message types used for communication
between widgets and the ChatScreen, particularly for step checkpoints
and cascade confirmation in the Router's Planning mode.
"""

from textual.message import Message

from shotgun.agents.router.models import CascadeScope, ExecutionStep

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
