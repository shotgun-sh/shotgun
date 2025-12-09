"""Message types for ChatScreen communication.

This module defines Textual message types used for communication
between widgets and the ChatScreen, particularly for step checkpoints
in the Router's Planning mode.
"""

from textual.message import Message

from shotgun.agents.router.models import ExecutionStep

__all__ = [
    "StepCompleted",
    "CheckpointContinue",
    "CheckpointModify",
    "CheckpointStop",
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
