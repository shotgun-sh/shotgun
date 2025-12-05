"""Re-exports all evaluation models from .shotgun/contracts/.

This module provides a clean import path for all eval-related Pydantic models:
    from evals.models import QACase, AgentToolCase, MetricName, CaseEvalResult
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add .shotgun/contracts to the Python path so we can import from it
_contracts_path = Path(__file__).parent.parent.parent / ".shotgun" / "contracts"
if str(_contracts_path) not in sys.path:
    sys.path.insert(0, str(_contracts_path))

# ruff: noqa: E402
# Imports must come after sys.path manipulation
from eval_cases import (  # noqa: E402
    AgentToolCase,
    AgentToolCaseMetadata,
    ClarifyingQuestionPolicy,
    Difficulty,
    FileChangeExpectation,
    QACase,
    QACaseMetadata,
    QADomain,
    QAExpectation,
    ScenarioType,
    SourceType,
    ToolUsageExpectation,
)
from eval_judge_outputs import (  # noqa: E402
    FileChangeJudgeOutput,
    FileChangeJudgeScores,
    QAJudgeOutput,
    QAJudgeScores,
    ScoreScale,
    ToolUseJudgeOutput,
    ToolUseJudgeScores,
)
from eval_metrics import (  # noqa: E402
    CaseEvalResult,
    MetricName,
    MetricValue,
)

__all__ = [
    # Enums from eval_cases
    "Difficulty",
    "QADomain",
    "ScenarioType",
    "SourceType",
    "ClarifyingQuestionPolicy",
    # Q&A case models
    "QAExpectation",
    "QACaseMetadata",
    "QACase",
    # Agent/tool case models
    "FileChangeExpectation",
    "ToolUsageExpectation",
    "AgentToolCaseMetadata",
    "AgentToolCase",
    # Metrics
    "MetricName",
    "MetricValue",
    "CaseEvalResult",
    # Judge outputs
    "ScoreScale",
    "QAJudgeScores",
    "QAJudgeOutput",
    "ToolUseJudgeScores",
    "ToolUseJudgeOutput",
    "FileChangeJudgeScores",
    "FileChangeJudgeOutput",
]
