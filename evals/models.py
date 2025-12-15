"""
Core Pydantic models for the Shotgun evaluation system.

This module defines all data structures for test cases, evaluation results,
and judge configurations. It draws from the contracts defined in .shotgun/contracts/
but is self-contained for the evaluation system.

Note: This is evaluation-specific code, not part of the main Shotgun codebase.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# ============================================================================
# Constants
# ============================================================================

LOGFIRE_TRACE_URL_BASE = "https://logfire.pydantic.dev/trace"
"""Base URL for Logfire trace links."""

# ============================================================================
# Utility Functions
# ============================================================================


def build_logfire_url(trace_id: str) -> str | None:
    """Build a Logfire trace URL from a trace ID.

    Args:
        trace_id: The OpenTelemetry trace ID (32 hex chars)

    Returns:
        Full Logfire URL or None if trace ID is invalid/empty
    """
    if not trace_id or trace_id == "0" * 32:
        return None
    return f"{LOGFIRE_TRACE_URL_BASE}/{trace_id}"


# ============================================================================
# Agent Types
# ============================================================================


class AgentType(str, Enum):
    """Supported Shotgun agent types for evaluation."""

    RESEARCH = "research"
    SPECIFY = "specify"
    PLAN = "plan"
    TASKS = "tasks"
    EXPORT = "export"
    ROUTER = "router"


# ============================================================================
# File Operation Types
# ============================================================================


class FileOperationType(str, Enum):
    """Type of file operation performed by an agent."""

    CREATED = "CREATED"
    UPDATED = "UPDATED"
    DELETED = "DELETED"


# ============================================================================
# LLM Provider Types
# ============================================================================


class JudgeProviderType(str, Enum):
    """Supported LLM providers for judge models."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    GROQ = "groq"


# ============================================================================
# Evaluator Types
# ============================================================================


class EvaluatorSeverity(str, Enum):
    """Severity level for evaluator results.

    - HARD: Failure results in overall test failure (critical errors)
    - SOFT: Failure is recorded but doesn't cause overall test failure (warnings)
    """

    HARD = "hard"
    SOFT = "soft"


class EvaluatorName(str, Enum):
    """Names of deterministic evaluators."""

    DISALLOWED_TOOL_USAGE = "disallowed_tool_usage"
    EXECUTION_FAILURE = "execution_failure"
    EXPECTED_TOOL_PRESENCE = "expected_tool_presence"
    CONTENT_ASSERTION = "content_assertion"
    DELEGATION_CORRECTNESS = "delegation_correctness"


class DimensionSource(str, Enum):
    """Source of an evaluation dimension score."""

    DETERMINISTIC = "deterministic"
    JUDGE = "judge"


# ============================================================================
# Router Evaluation Dimensions
# ============================================================================


class RouterDimension(str, Enum):
    """Evaluation dimensions for Router agent."""

    # Router-specific dimensions
    DELEGATION_RATIONALE = "delegation_rationale"
    CONTEXT_HANDLING = "context_handling"
    # Core writing quality dimensions
    CLARITY = "clarity"
    RELEVANCE = "relevance"


# ============================================================================
# Test Difficulty and Category
# ============================================================================


class TestDifficulty(str, Enum):
    """Test case difficulty classification."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"


class TestCategory(str, Enum):
    """Test case category classification."""

    BASIC_FUNCTIONALITY = "basic_functionality"
    TOOL_USAGE = "tool_usage"
    FILE_OPERATIONS = "file_operations"
    ERROR_HANDLING = "error_handling"
    MULTI_STEP = "multi_step"
    EDGE_CASE = "edge_case"
    REGRESSION = "regression"
    INTEGRATION = "integration"
    ROUTER_DELEGATION = "router_delegation"


# ============================================================================
# Test Case Input/Output Models
# ============================================================================


class TestCaseInput(BaseModel):
    """Input structure for agent test cases."""

    prompt: str = Field(..., description="The user prompt/request to the agent")
    agent_type: AgentType = Field(..., description="Which agent to invoke")
    context: dict[str, Any] | None = Field(
        default=None,
        description="Additional context (codebase state, prior outputs, etc.)",
    )
    enable_tools: bool = Field(default=True, description="Whether to enable tool usage")


class FileOperation(BaseModel):
    """Represents a file operation performed by an agent."""

    file_path: str = Field(..., description="Path to the file")
    operation: FileOperationType = Field(..., description="Type of file operation")
    content_snippet: str | None = Field(
        default=None, description="Optional snippet of file content for validation"
    )


class AgentExecutionOutput(BaseModel):
    """Complete output from an agent execution."""

    response: str = Field(..., description="Agent's text response")
    clarifying_questions: list[str] | None = Field(
        default=None, description="Questions posed to user"
    )
    file_operations: list[FileOperation] = Field(
        default_factory=list, description="Files created/modified/deleted"
    )
    tools_used: list[str] = Field(
        default_factory=list, description="Names of tools invoked"
    )
    duration_seconds: float = Field(..., description="Execution time")
    token_usage: dict[str, int] = Field(
        default_factory=dict, description="Token counts (prompt, completion, total)"
    )

    # Router-specific fields
    delegated_sub_agent: str | None = Field(
        default=None, description="Sub-agent Router delegated to (Router agent only)"
    )
    delegation_reasoning: str | None = Field(
        default=None,
        description="Router's reasoning for delegation (Router agent only)",
    )


class ExpectedAgentOutput(BaseModel):
    """Expected output specification for reference-based evaluation."""

    response_contains: list[str] = Field(
        default_factory=list,
        description="Keywords/phrases that must appear in response",
    )
    response_not_contains: list[str] = Field(
        default_factory=list, description="Keywords/phrases that must NOT appear"
    )
    file_operations: list[FileOperation] = Field(
        default_factory=list, description="Expected file operations"
    )
    tools_used: list[str] = Field(
        default_factory=list, description="Expected tools to be invoked"
    )
    min_response_length: int | None = Field(
        default=None, description="Minimum response length in characters"
    )
    max_response_length: int | None = Field(
        default=None, description="Maximum response length in characters"
    )
    max_duration_seconds: float | None = Field(
        default=None, description="Maximum acceptable execution time"
    )
    max_tokens: int | None = Field(
        default=None, description="Maximum acceptable token usage"
    )

    # Router-specific expected outputs
    expected_sub_agent: str | None = Field(
        default=None, description="Expected sub-agent for Router delegation"
    )
    expect_clarifying_questions: bool = Field(
        default=False,
        description="Whether the agent should ask clarifying questions",
    )
    min_clarifying_questions: int = Field(
        default=1,
        description="Minimum number of clarifying questions expected (when expect_clarifying_questions=True)",
    )


# ============================================================================
# Test Case Metadata
# ============================================================================


class TestCaseMetadata(BaseModel):
    """Metadata for organizing and filtering test cases."""

    difficulty: TestDifficulty = Field(..., description="Test difficulty level")
    category: TestCategory = Field(..., description="Test category")
    tags: list[str] = Field(
        default_factory=list, description="Custom tags for filtering"
    )
    expected_files: list[str] = Field(
        default_factory=list, description="Files expected to be created/modified"
    )
    expected_tools: list[str] = Field(
        default_factory=list, description="Tools expected to be used"
    )
    description: str | None = Field(
        default=None, description="Human-readable description of what's being tested"
    )

    # Router-specific metadata
    expected_sub_agent: str | None = Field(
        default=None, description="Expected sub-agent for Router delegation tests"
    )


# ============================================================================
# Complete Test Case
# ============================================================================


class ShotgunTestCase(BaseModel):
    """Complete test case definition for agent evaluation."""

    name: str = Field(..., description="Unique test case identifier")
    inputs: TestCaseInput = Field(..., description="Test case inputs")
    expected_output: ExpectedAgentOutput | None = Field(
        default=None,
        description="Expected output specification (for reference-based eval)",
    )
    metadata: TestCaseMetadata = Field(..., description="Test case metadata")


# ============================================================================
# Evaluation Context and Results
# ============================================================================


class EvaluationContext(BaseModel):
    """Context provided to evaluators during evaluation."""

    test_case_name: str = Field(..., description="Test case identifier")
    inputs: TestCaseInput = Field(..., description="Test case inputs")
    actual_output: AgentExecutionOutput = Field(
        ..., description="Agent's actual output"
    )
    expected_output: ExpectedAgentOutput | None = Field(
        default=None, description="Expected output (if reference-based)"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Test case metadata as dict"
    )


class EvaluationResult(BaseModel):
    """Result from a single evaluator."""

    evaluator_name: str = Field(..., description="Name of the evaluator")
    passed: bool = Field(..., description="Whether evaluation passed")
    score: float | None = Field(
        default=None, ge=0.0, le=5.0, description="Score (1-5 Likert scale)"
    )
    reasoning: str | None = Field(
        default=None, description="Explanation for the result"
    )
    dimension: str | None = Field(
        default=None,
        description="Evaluation dimension (e.g., 'correctness', 'clarity')",
    )


class TestCaseResult(BaseModel):
    """Result from executing a single test case."""

    test_case_name: str = Field(..., description="Test case identifier")
    passed: bool = Field(..., description="Overall pass/fail")
    execution_output: AgentExecutionOutput = Field(
        ..., description="Agent's execution output"
    )
    evaluation_results: list[EvaluationResult] = Field(
        ..., description="Results from all evaluators"
    )
    average_score: float | None = Field(
        default=None, description="Average score across evaluators"
    )
    error: str | None = Field(
        default=None, description="Error message if execution failed"
    )


class EvaluationReport(BaseModel):
    """Comprehensive report from evaluation run."""

    suite_name: str = Field(..., description="Evaluation suite name")
    model_name: str | None = Field(
        default=None, description="Model used for evaluation (if overridden)"
    )
    total_test_cases: int = Field(..., description="Total test cases run")
    passed_test_cases: int = Field(..., description="Number of passed tests")
    failed_test_cases: int = Field(..., description="Number of failed tests")
    pass_rate: float = Field(..., ge=0.0, le=1.0, description="Pass rate (0.0-1.0)")
    test_results: list[TestCaseResult] = Field(
        ..., description="Individual test case results"
    )
    average_score: float | None = Field(
        default=None, description="Average score across all tests (if scoring)"
    )
    total_duration_seconds: float = Field(..., description="Total evaluation time")
    total_tokens_used: int = Field(
        default=0, description="Total tokens used across all tests"
    )
    timestamp: str = Field(..., description="When evaluation was run")

    # Dimension-level aggregates
    dimension_averages: dict[str, float] = Field(
        default_factory=dict, description="Average scores per evaluation dimension"
    )


# ============================================================================
# LLM Judge Configuration
# ============================================================================


class JudgeModelConfig(BaseModel):
    """Configuration for LLM judge model."""

    provider: JudgeProviderType = Field(..., description="LLM provider")
    model_name: str = Field(..., description="Model identifier")
    temperature: float = Field(
        default=0.2,
        ge=0.0,
        le=2.0,
        description="Sampling temperature (lower = more deterministic)",
    )
    max_tokens: int | None = Field(
        default=2000, description="Maximum tokens for judge response"
    )

    def to_model_string(self) -> str:
        """Convert to provider:model format."""
        return f"{self.provider.value}:{self.model_name}"


class LLMJudgeConfig(BaseModel):
    """Configuration for LLM-as-a-judge evaluation."""

    rubric: str = Field(..., description="Evaluation rubric/prompt for the judge")
    model: JudgeModelConfig = Field(..., description="Judge model configuration")
    include_input: bool = Field(
        default=True, description="Include original input in judge context"
    )
    include_expected_output: bool = Field(
        default=False,
        description="Include expected output for reference-based evaluation",
    )
    enable_chain_of_thought: bool = Field(
        default=True, description="Request step-by-step reasoning from judge"
    )


# ============================================================================
# Evaluation Suite
# ============================================================================


class EvaluationSuite(BaseModel):
    """
    Collection of test cases organized into a suite.

    Suites reference test cases by name for modular organization.
    Suite definitions go in: evals/suites/<suite_name>.py
    """

    name: str = Field(..., description="Suite identifier")
    description: str | None = Field(default=None, description="Suite description")
    test_case_names: list[str] = Field(
        ..., description="Names of test cases in this suite"
    )
    evaluator_names: list[str] = Field(
        default_factory=list, description="Names of evaluators to apply to all cases"
    )
    tags: list[str] = Field(
        default_factory=list, description="Tags for filtering suites"
    )


# ============================================================================
# Tracing Models
# ============================================================================


class TraceRef(BaseModel):
    """Reference to a Logfire trace for debugging."""

    trace_id: str = Field(..., description="OpenTelemetry trace ID (32 hex chars)")
    span_id: str = Field(..., description="OpenTelemetry span ID (16 hex chars)")
    url: str | None = Field(default=None, description="Logfire UI URL for this trace")


# ============================================================================
# Deterministic Evaluator Models
# ============================================================================


class EvaluatorResult(BaseModel):
    """Result from a deterministic evaluator."""

    evaluator_name: str = Field(..., description="Name of the evaluator")
    passed: bool = Field(..., description="Whether the check passed")
    severity: EvaluatorSeverity = Field(
        ..., description="Severity of failure if failed"
    )
    reasoning: str = Field(..., description="Explanation of the result")
    details: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Additional details (e.g., lists of violations)",
    )


# ============================================================================
# LLM Judge Models
# ============================================================================


class RouterDimensionRubric(BaseModel):
    """Rubric definition for a single Router evaluation dimension."""

    dimension: RouterDimension = Field(..., description="The dimension being evaluated")
    description: str = Field(..., description="What this dimension measures")
    rubric_text: str = Field(..., description="Full rubric text for the LLM judge")
    weight: float = Field(default=1.0, ge=0.0, le=2.0, description="Weight for scoring")


class DimensionScoreOutput(BaseModel):
    """Structured output from LLM judge for a single dimension."""

    score: int = Field(..., ge=1, le=5, description="Score on 1-5 Likert scale")
    reasoning: str = Field(..., description="Explanation for the score")
    passed: bool = Field(
        ..., description="Whether the minimum threshold was met (score >= 3)"
    )


class RouterJudgeResult(BaseModel):
    """Complete result from Router quality judge evaluation."""

    dimension_scores: dict[str, DimensionScoreOutput] = Field(
        ..., description="Scores for each evaluated dimension"
    )
    overall_score: float = Field(
        ..., ge=0.0, le=5.0, description="Weighted average score (1-5 scale)"
    )
    overall_passed: bool = Field(..., description="Whether overall evaluation passed")
    summary: str = Field(..., description="Summary of the evaluation")


# ============================================================================
# Aggregation Models
# ============================================================================


class DimensionAggregate(BaseModel):
    """Aggregated score for a single evaluation dimension."""

    dimension: str = Field(..., description="Dimension name")
    score: float = Field(..., ge=0.0, le=5.0, description="Average score (1-5 scale)")
    passed: bool = Field(..., description="Whether dimension passed")
    source: DimensionSource = Field(..., description="Source of this dimension")


class AggregatedResult(BaseModel):
    """Aggregated result from all evaluators for a single test case."""

    test_case_name: str = Field(..., description="Test case identifier")
    passed: bool = Field(..., description="Overall pass/fail")
    overall_score: float = Field(
        ..., ge=0.0, le=5.0, description="Overall score (1-5 scale)"
    )

    # Preserved per-evaluator results
    deterministic_results: list[EvaluatorResult] = Field(
        ..., description="Results from deterministic evaluators"
    )
    judge_result: RouterJudgeResult | None = Field(
        default=None, description="Result from LLM judge (if run)"
    )

    # Per-dimension aggregates
    dimension_scores: list[DimensionAggregate] = Field(
        default_factory=list, description="Scores by evaluation dimension"
    )

    # Trace reference
    trace_ref: TraceRef = Field(
        ..., description="Logfire trace reference for debugging"
    )

    # Summary
    summary: str = Field(..., description="Human-readable summary")
    hard_failures: list[str] = Field(
        default_factory=list, description="List of hard failures (if any)"
    )
    soft_failures: list[str] = Field(
        default_factory=list, description="List of soft failures (if any)"
    )
