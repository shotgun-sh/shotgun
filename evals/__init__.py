"""
Shotgun Agent Evaluation System.

A development-only evaluation framework for testing and tuning Shotgun's agents.
This module provides LLM-as-a-judge evaluation for Router agent delegation
correctness, plan quality, and user interaction.

Directory structure:
    evals/
    ├── datasets/           # Test case definitions
    │   └── router_agent/   # Router-specific test cases
    ├── judges/             # LLM judge implementations
    ├── rubrics/            # Scoring rubrics
    ├── reporters/          # Report formatting
    ├── config/             # Judge configurations
    └── reports/            # Generated evaluation reports

Usage:
    python evals/run_eval.py

This is NOT production code - it runs only during development and CI/CD.
"""

from evals.executor import (
    ExecutionError,
    ExecutionResult,
    RouterExecutor,
    get_environment_metadata,
)
from evals.logfire_utils import (
    LogfireConfigurationError,
    TraceRef,
    configure_logfire_or_fail,
    get_current_trace_ref,
    start_case_trace,
)
from evals.models import (
    AgentExecutionOutput,
    # Agent types
    AgentType,
    # Evaluation models
    EvaluationContext,
    EvaluationReport,
    EvaluationResult,
    EvaluationSuite,
    ExpectedAgentOutput,
    FileOperation,
    # Judge config
    JudgeModelConfig,
    LLMJudgeConfig,
    ShotgunTestCase,
    # Test case models
    TestCaseInput,
    TestCaseMetadata,
    TestCaseResult,
    TestCategory,
    TestDifficulty,
)

__all__ = [
    # Agent types
    "AgentType",
    # Test case models
    "TestCaseInput",
    "FileOperation",
    "AgentExecutionOutput",
    "ExpectedAgentOutput",
    "TestDifficulty",
    "TestCategory",
    "TestCaseMetadata",
    "ShotgunTestCase",
    # Evaluation models
    "EvaluationContext",
    "EvaluationResult",
    "TestCaseResult",
    "EvaluationReport",
    "EvaluationSuite",
    # Judge config
    "JudgeModelConfig",
    "LLMJudgeConfig",
    # Logfire utilities
    "LogfireConfigurationError",
    "TraceRef",
    "configure_logfire_or_fail",
    "start_case_trace",
    "get_current_trace_ref",
    # Executor
    "ExecutionError",
    "ExecutionResult",
    "RouterExecutor",
    "get_environment_metadata",
]
