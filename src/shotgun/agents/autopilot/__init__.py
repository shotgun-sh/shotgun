"""Autopilot agent for stage-based execution of tasks.md.

The Autopilot agent orchestrates Claude Code CLI to work through
implementation stages defined in .shotgun/tasks.md.
"""

from shotgun.agents.autopilot.autopilot_orchestrator import (
    AutopilotConfig,
    AutopilotOrchestrator,
)
from shotgun.agents.autopilot.claude_subprocess import (
    ClaudeSubprocess,
    ClaudeSubprocessConfig,
)
from shotgun.agents.autopilot.llm_parser import LLMTasksParser
from shotgun.agents.autopilot.models import (
    AutopilotMode,
    AutopilotState,
    ClaudeOutput,
    ClaudeOutputType,
    FileStatus,
    ParsedStage,
    ParsedTask,
    ParsedTasksOutput,
    PrerequisiteValidation,
    Stage,
    StagePhase,
    StageStatus,
    Task,
)
from shotgun.agents.autopilot.tasks_parser import ParsedTasksFile, TasksParser

__all__ = [
    "AutopilotConfig",
    "AutopilotMode",
    "AutopilotOrchestrator",
    "AutopilotState",
    "ClaudeOutput",
    "ClaudeOutputType",
    "ClaudeSubprocess",
    "ClaudeSubprocessConfig",
    "FileStatus",
    "LLMTasksParser",
    "ParsedStage",
    "ParsedTask",
    "ParsedTasksFile",
    "ParsedTasksOutput",
    "PrerequisiteValidation",
    "Stage",
    "StagePhase",
    "StageStatus",
    "Task",
    "TasksParser",
]
