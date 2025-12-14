"""
Deterministic evaluators for Router agent evaluation.

These evaluators apply rule-based checks with deterministic outcomes.
Per plan Decision A, these are Router-first evaluators:
- Hard failures: Disallowed tool usage, Execution failure
- Soft failures: Expected tool presence, Content assertions, Delegation correctness

NOTE: Performance bounds checks (duration/tokens thresholds) are EXCLUDED per scope.
Duration and tokens are recorded for debugging only, not for pass/fail evaluation.
"""

from abc import ABC, abstractmethod
from typing import Protocol

from evals.models import (
    AgentExecutionOutput,
    EvaluationResult,
    EvaluatorResult,
    EvaluatorSeverity,
    ExpectedAgentOutput,
    ShotgunTestCase,
)


class RouterDeterministicEvaluator(Protocol):
    """Protocol for deterministic Router evaluators."""

    name: str
    severity: EvaluatorSeverity

    def evaluate(
        self,
        actual_output: AgentExecutionOutput,
        expected_output: ExpectedAgentOutput | None,
        test_case: ShotgunTestCase,
    ) -> EvaluatorResult:
        """Evaluate the agent output against expectations.

        Args:
            actual_output: The agent's actual output
            expected_output: Expected output specification (if any)
            test_case: The full test case for metadata access

        Returns:
            EvaluatorResult with pass/fail, reasoning, and details
        """
        ...


class BaseEvaluator(ABC):
    """Base class for deterministic evaluators."""

    name: str
    severity: EvaluatorSeverity

    @abstractmethod
    def evaluate(
        self,
        actual_output: AgentExecutionOutput,
        expected_output: ExpectedAgentOutput | None,
        test_case: ShotgunTestCase,
    ) -> EvaluatorResult:
        """Evaluate the agent output."""
        ...


class DisallowedToolUsageEvaluator(BaseEvaluator):
    """
    [HARD] Checks that no disallowed tools were used.

    This is a hard failure because using disallowed tools indicates
    a security or correctness violation.

    Disallowed tools for Router agent:
    - File manipulation tools (Router should delegate, not act directly)
    - Code execution tools
    - Any tools not in the Router's allowed set
    """

    name = "disallowed_tool_usage"
    severity = EvaluatorSeverity.HARD

    # Tools that Router agent should NEVER use directly
    DISALLOWED_TOOLS = {
        # File operations - Router should delegate to sub-agents
        "file_write",
        "file_delete",
        "file_create",
        "write_file",
        "delete_file",
        "create_file",
        # Code execution
        "execute_code",
        "run_command",
        "shell",
        "bash",
        # Direct code modification
        "edit_code",
        "modify_file",
    }

    def evaluate(
        self,
        actual_output: AgentExecutionOutput,
        expected_output: ExpectedAgentOutput | None,
        test_case: ShotgunTestCase,
    ) -> EvaluatorResult:
        """Check for disallowed tool usage."""
        tools_used = set(actual_output.tools_used)
        violations = tools_used.intersection(self.DISALLOWED_TOOLS)

        if violations:
            return EvaluatorResult(
                evaluator_name=self.name,
                passed=False,
                severity=self.severity,
                reasoning=f"Router used disallowed tools: {', '.join(sorted(violations))}",
                details={"violations": sorted(violations)},
            )

        return EvaluatorResult(
            evaluator_name=self.name,
            passed=True,
            severity=self.severity,
            reasoning="No disallowed tools used",
            details={},
        )


class ExecutionFailureEvaluator(BaseEvaluator):
    """
    [HARD] Checks that execution completed without errors.

    This is a hard failure because execution errors indicate
    fundamental problems with the agent.
    """

    name = "execution_failure"
    severity = EvaluatorSeverity.HARD

    def evaluate(
        self,
        actual_output: AgentExecutionOutput,
        expected_output: ExpectedAgentOutput | None,
        test_case: ShotgunTestCase,
    ) -> EvaluatorResult:
        """Check for execution failures."""
        # Check if response is empty (indicating failure)
        if not actual_output.response or actual_output.response.strip() == "":
            return EvaluatorResult(
                evaluator_name=self.name,
                passed=False,
                severity=self.severity,
                reasoning="Agent produced empty response",
                details={},
            )

        # Check if response indicates an error
        error_indicators = [
            "error occurred",
            "failed to",
            "unable to complete",
            "exception:",
            "traceback:",
        ]
        response_lower = actual_output.response.lower()

        for indicator in error_indicators:
            if indicator in response_lower:
                # Only fail if the error is about the agent itself, not discussing errors
                if (
                    "i encountered" in response_lower
                    or "an error occurred" in response_lower
                ):
                    return EvaluatorResult(
                        evaluator_name=self.name,
                        passed=False,
                        severity=self.severity,
                        reasoning=f"Agent response indicates execution error: contains '{indicator}'",
                        details={"error_indicator": [indicator]},
                    )

        return EvaluatorResult(
            evaluator_name=self.name,
            passed=True,
            severity=self.severity,
            reasoning="Execution completed successfully",
            details={},
        )


class ExpectedToolPresenceEvaluator(BaseEvaluator):
    """
    [SOFT] Checks that expected tools were used.

    This is a soft failure because the agent might accomplish
    the task through alternative (valid) means.
    """

    name = "expected_tool_presence"
    severity = EvaluatorSeverity.SOFT

    def evaluate(
        self,
        actual_output: AgentExecutionOutput,
        expected_output: ExpectedAgentOutput | None,
        test_case: ShotgunTestCase,
    ) -> EvaluatorResult:
        """Check that expected tools were used."""
        # Get expected tools from test case metadata
        expected_tools = set(test_case.metadata.expected_tools)

        if not expected_tools:
            return EvaluatorResult(
                evaluator_name=self.name,
                passed=True,
                severity=self.severity,
                reasoning="No expected tools specified",
                details={},
            )

        tools_used = set(actual_output.tools_used)
        missing_tools = expected_tools - tools_used

        if missing_tools:
            return EvaluatorResult(
                evaluator_name=self.name,
                passed=False,
                severity=self.severity,
                reasoning=f"Missing expected tools: {', '.join(sorted(missing_tools))}",
                details={
                    "missing_tools": sorted(missing_tools),
                    "tools_used": sorted(tools_used),
                },
            )

        return EvaluatorResult(
            evaluator_name=self.name,
            passed=True,
            severity=self.severity,
            reasoning=f"All expected tools used: {', '.join(sorted(expected_tools))}",
            details={"tools_used": sorted(tools_used)},
        )


class ContentAssertionEvaluator(BaseEvaluator):
    """
    [SOFT] Checks content assertions (contains/not contains).

    This is a soft failure because content checks are heuristic
    and the agent might express the same information differently.
    """

    name = "content_assertion"
    severity = EvaluatorSeverity.SOFT

    def evaluate(
        self,
        actual_output: AgentExecutionOutput,
        expected_output: ExpectedAgentOutput | None,
        test_case: ShotgunTestCase,
    ) -> EvaluatorResult:
        """Check content assertions."""
        if expected_output is None:
            return EvaluatorResult(
                evaluator_name=self.name,
                passed=True,
                severity=self.severity,
                reasoning="No expected output specified",
                details={},
            )

        response_lower = actual_output.response.lower()
        violations: list[str] = []

        # Check response_contains
        missing_content = [
            content
            for content in expected_output.response_contains
            if content.lower() not in response_lower
        ]
        if missing_content:
            violations.extend([f"missing: '{c}'" for c in missing_content])

        # Check response_not_contains
        forbidden_content = [
            content
            for content in expected_output.response_not_contains
            if content.lower() in response_lower
        ]
        if forbidden_content:
            violations.extend([f"forbidden: '{c}'" for c in forbidden_content])

        if violations:
            return EvaluatorResult(
                evaluator_name=self.name,
                passed=False,
                severity=self.severity,
                reasoning=f"Content assertions failed: {', '.join(violations[:3])}{'...' if len(violations) > 3 else ''}",
                details={
                    "missing_content": missing_content,
                    "forbidden_content": forbidden_content,
                },
            )

        return EvaluatorResult(
            evaluator_name=self.name,
            passed=True,
            severity=self.severity,
            reasoning="All content assertions passed",
            details={},
        )


class DelegationCorrectnessEvaluator(BaseEvaluator):
    """
    [SOFT] Checks that Router delegated to the expected sub-agent.

    Design decision: This is marked as SOFT because:
    1. The "correct" sub-agent can be subjective for ambiguous requests
    2. Multiple sub-agents might reasonably handle certain tasks
    3. The LLM judge provides a more nuanced assessment of delegation quality

    If strict enforcement is needed, change severity to HARD.
    """

    name = "delegation_correctness"
    severity = EvaluatorSeverity.SOFT

    def evaluate(
        self,
        actual_output: AgentExecutionOutput,
        expected_output: ExpectedAgentOutput | None,
        test_case: ShotgunTestCase,
    ) -> EvaluatorResult:
        """Check delegation correctness."""
        # Get expected sub-agent from test case metadata
        expected_sub_agent = test_case.metadata.expected_sub_agent

        if expected_sub_agent is None:
            return EvaluatorResult(
                evaluator_name=self.name,
                passed=True,
                severity=self.severity,
                reasoning="No expected sub-agent specified",
                details={},
            )

        actual_sub_agent = actual_output.delegated_sub_agent

        if actual_sub_agent is None:
            return EvaluatorResult(
                evaluator_name=self.name,
                passed=False,
                severity=self.severity,
                reasoning="Router did not delegate to any sub-agent",
                details={
                    "expected_sub_agent": [expected_sub_agent],
                    "actual_sub_agent": ["None"],
                },
            )

        # Normalize for comparison (case-insensitive)
        if actual_sub_agent.lower() == expected_sub_agent.lower():
            return EvaluatorResult(
                evaluator_name=self.name,
                passed=True,
                severity=self.severity,
                reasoning=f"Correctly delegated to {actual_sub_agent}",
                details={"delegated_to": [actual_sub_agent]},
            )

        return EvaluatorResult(
            evaluator_name=self.name,
            passed=False,
            severity=self.severity,
            reasoning=f"Delegated to {actual_sub_agent}, expected {expected_sub_agent}",
            details={
                "expected_sub_agent": [expected_sub_agent],
                "actual_sub_agent": [actual_sub_agent],
            },
        )


# Registry of all deterministic evaluators
DETERMINISTIC_EVALUATORS: list[type[BaseEvaluator]] = [
    DisallowedToolUsageEvaluator,
    ExecutionFailureEvaluator,
    ExpectedToolPresenceEvaluator,
    ContentAssertionEvaluator,
    DelegationCorrectnessEvaluator,
]


def run_all_deterministic_evaluators(
    actual_output: AgentExecutionOutput,
    expected_output: ExpectedAgentOutput | None,
    test_case: ShotgunTestCase,
) -> list[EvaluatorResult]:
    """
    Run all deterministic evaluators on the given output.

    Args:
        actual_output: The agent's actual output
        expected_output: Expected output specification (if any)
        test_case: The full test case for metadata access

    Returns:
        List of EvaluatorResult from all evaluators
    """
    results: list[EvaluatorResult] = []

    for evaluator_class in DETERMINISTIC_EVALUATORS:
        evaluator = evaluator_class()
        result = evaluator.evaluate(actual_output, expected_output, test_case)
        results.append(result)

    return results


def convert_to_evaluation_result(
    evaluator_result: EvaluatorResult,
) -> EvaluationResult:
    """
    Convert EvaluatorResult to the standard EvaluationResult model.

    Args:
        evaluator_result: Result from a deterministic evaluator

    Returns:
        Standard EvaluationResult model
    """
    return EvaluationResult(
        evaluator_name=evaluator_result.evaluator_name,
        passed=evaluator_result.passed,
        score=1.0 if evaluator_result.passed else 0.0,
        reasoning=evaluator_result.reasoning,
        dimension=f"deterministic.{evaluator_result.evaluator_name}",
    )
