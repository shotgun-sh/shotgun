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
    configure_logfire_or_fail,
    get_current_trace_ref,
    start_case_trace,
)
from evals.models import (
    AgentExecutionOutput,
    # Agent types
    AgentType,
    # Aggregation models
    AggregatedResult,
    DimensionAggregate,
    # Judge output models
    DimensionScoreOutput,
    # Evaluation models
    EvaluationContext,
    EvaluationReport,
    EvaluationResult,
    EvaluationSuite,
    # Evaluator models
    EvaluatorName,
    EvaluatorResult,
    EvaluatorSeverity,
    ExpectedAgentOutput,
    FileOperation,
    FileOperationType,
    # Judge config
    JudgeModelConfig,
    JudgeProviderType,
    LLMJudgeConfig,
    RouterDimension,
    RouterDimensionRubric,
    RouterJudgeResult,
    ShotgunTestCase,
    # Test case models
    TestCaseInput,
    TestCaseMetadata,
    TestCaseResult,
    TestCategory,
    TestDifficulty,
    # Tracing
    TraceRef,
    # Utilities
    build_logfire_url,
)

__all__ = [
    # Agent types
    "AgentType",
    # Test case models
    "TestCaseInput",
    "FileOperation",
    "FileOperationType",
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
    # Evaluator models
    "EvaluatorName",
    "EvaluatorResult",
    "EvaluatorSeverity",
    # Judge config
    "JudgeModelConfig",
    "JudgeProviderType",
    "LLMJudgeConfig",
    # Judge output models
    "RouterDimension",
    "RouterDimensionRubric",
    "DimensionScoreOutput",
    "RouterJudgeResult",
    # Aggregation models
    "DimensionAggregate",
    "AggregatedResult",
    # Tracing
    "TraceRef",
    # Logfire utilities
    "LogfireConfigurationError",
    "configure_logfire_or_fail",
    "start_case_trace",
    "get_current_trace_ref",
    "build_logfire_url",
    # Executor
    "ExecutionError",
    "ExecutionResult",
    "RouterExecutor",
    "get_environment_metadata",
]
