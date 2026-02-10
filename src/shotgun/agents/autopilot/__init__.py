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
from shotgun.agents.autopilot.lightweight_parser import LightweightTasksParser
from shotgun.agents.autopilot.llm_parser import LLMTasksParser
from shotgun.agents.autopilot.models import (
    AutopilotMode,
    AutopilotState,
    ClaudeModel,
    ClaudeOutput,
    ClaudeOutputType,
    FileStatus,
    MonitorAction,
    MonitorDecision,
    ParsedStage,
    ParsedTask,
    ParsedTasksOutput,
    PrerequisiteValidation,
    Stage,
    StagePhase,
    StageStatus,
    Task,
)
from shotgun.agents.autopilot.tasks_parser import (
    ParsedTasksFile,
    TasksParser,
    merge_stages_with_parsed_tasks,
)

__all__ = [
    "AutopilotConfig",
    "AutopilotMode",
    "AutopilotOrchestrator",
    "AutopilotState",
    "ClaudeModel",
    "ClaudeOutput",
    "ClaudeOutputType",
    "ClaudeSubprocess",
    "ClaudeSubprocessConfig",
    "FileStatus",
    "LightweightTasksParser",
    "LLMTasksParser",
    "MonitorAction",
    "MonitorDecision",
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
    "merge_stages_with_parsed_tasks",
]
