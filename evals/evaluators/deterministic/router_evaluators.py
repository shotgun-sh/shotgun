"""
Deterministic evaluators for Router agent evaluation.

These evaluators apply rule-based checks with deterministic outcomes.
Per plan Decision A, these are Router-first evaluators:
- Hard failures: Disallowed tool usage, Execution failure
- Soft failures: Expected tool presence, Content assertions, Delegation correctness

NOTE: Performance bounds checks (duration/tokens thresholds) are EXCLUDED per scope.
Duration and tokens are recorded for debugging only, not for pass/fail evaluation.
"""

import logging
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

logger = logging.getLogger(__name__)


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

        # Check global disallowed tools
        global_violations = tools_used.intersection(self.DISALLOWED_TOOLS)

        # Check test case specific disallowed tools
        test_case_disallowed = set(test_case.expected.disallowed_tools)
        test_case_violations = tools_used.intersection(test_case_disallowed)

        all_violations = global_violations | test_case_violations

        if all_violations:
            return EvaluatorResult(
                evaluator_name=self.name,
                passed=False,
                severity=self.severity,
                reasoning=f"Router used disallowed tools: {', '.join(sorted(all_violations))}",
                details={"violations": sorted(all_violations)},
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
        # Check if agent produced any meaningful output
        has_response = actual_output.response and actual_output.response.strip() != ""
        has_clarifying_questions = bool(actual_output.clarifying_questions)
        has_file_requests = bool(actual_output.file_requests)
        has_delegation = bool(actual_output.delegated_sub_agent)

        logger.debug(
            f"ExecutionFailureEvaluator: response={has_response}, "
            f"questions={has_clarifying_questions}, "
            f"file_requests={has_file_requests}, "
            f"delegation={has_delegation}"
        )

        # Agent succeeded if it produced ANY meaningful output
        if not (has_response or has_clarifying_questions or has_file_requests or has_delegation):
            logger.warning(f"ExecutionFailureEvaluator: no output for {test_case.name}")
            return EvaluatorResult(
                evaluator_name=self.name,
                passed=False,
                severity=self.severity,
                reasoning="Agent produced empty response",
                details={},
            )

        # Check if response indicates an error (only if there is a response)
        if not has_response:
            return EvaluatorResult(
                evaluator_name=self.name,
                passed=True,
                severity=self.severity,
                reasoning="Execution completed successfully (clarifying questions or other structured output)",
                details={},
            )

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
                    logger.warning(
                        f"ExecutionFailureEvaluator failed: found '{indicator}' in response. "
                        f"Response preview: {actual_output.response[:500]}"
                    )
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
        # Get expected tools from test case expected output
        expected_tools = set(test_case.expected.expected_tools)

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
        # Get expected sub-agent from test case expected output
        expected_sub_agent = test_case.expected.expected_sub_agent

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


class ClarifyingQuestionsEvaluator(BaseEvaluator):
    """
    [HARD when expected] Checks that clarifying questions match expectations.

    When a test case specifies min_clarifying_questions, this becomes a HARD failure
    because the test is specifically designed to verify that behavior.

    When a test case specifies max_clarifying_questions, exceeding it is a HARD failure
    because the test expects the agent NOT to ask questions (e.g., for specific file paths).

    Used for test cases where we expect the agent to gather requirements
    before proceeding (e.g., ambiguous feature requests) OR where we expect
    the agent to act directly without questions (e.g., specific file requests).
    """

    name = "clarifying_questions"
    # Default severity - will be overridden to HARD when questions are expected
    severity = EvaluatorSeverity.SOFT

    def evaluate(
        self,
        actual_output: AgentExecutionOutput,
        expected_output: ExpectedAgentOutput | None,
        test_case: ShotgunTestCase,
    ) -> EvaluatorResult:
        """Check if clarifying questions match expectations."""
        # Get question count constraints from expected output
        min_questions = (
            expected_output.min_clarifying_questions if expected_output else None
        )
        max_questions = (
            expected_output.max_clarifying_questions if expected_output else None
        )

        # If no constraints specified, questions are not required/restricted
        if min_questions is None and max_questions is None:
            return EvaluatorResult(
                evaluator_name=self.name,
                passed=True,
                severity=self.severity,
                reasoning="Clarifying questions not constrained for this test",
                details={},
            )

        # When questions are explicitly constrained, use HARD severity
        # This ensures the test fails when its core assertion is violated
        failure_severity = EvaluatorSeverity.HARD

        # Check if agent asked clarifying questions
        questions = actual_output.clarifying_questions or []
        question_count = len(questions)

        # Check max_clarifying_questions constraint (should NOT ask questions)
        if max_questions is not None and question_count > max_questions:
            return EvaluatorResult(
                evaluator_name=self.name,
                passed=False,
                severity=failure_severity,
                reasoning=f"Agent asked {question_count} question(s) but max allowed is {max_questions}",
                details={
                    "questions_asked": questions,
                    "max_allowed": [str(max_questions)],
                },
            )

        # Check min_clarifying_questions constraint (should ask questions)
        if min_questions is not None:
            if question_count >= min_questions:
                return EvaluatorResult(
                    evaluator_name=self.name,
                    passed=True,
                    severity=failure_severity,
                    reasoning=f"Agent asked {question_count} clarifying question(s) (required: {min_questions}+)",
                    details={
                        "questions_asked": questions,
                        "min_required": [str(min_questions)],
                    },
                )

            if question_count > 0:
                return EvaluatorResult(
                    evaluator_name=self.name,
                    passed=False,
                    severity=failure_severity,
                    reasoning=f"Agent asked {question_count} question(s) but {min_questions}+ required",
                    details={
                        "questions_asked": questions,
                        "min_required": [str(min_questions)],
                    },
                )

            return EvaluatorResult(
                evaluator_name=self.name,
                passed=False,
                severity=failure_severity,
                reasoning=f"Agent did not ask clarifying questions (required: {min_questions}+)",
                details={"questions_asked": [], "min_required": [str(min_questions)]},
            )

        # Only max constraint specified and it passed
        return EvaluatorResult(
            evaluator_name=self.name,
            passed=True,
            severity=failure_severity,
            reasoning=f"Agent asked {question_count} question(s) (max allowed: {max_questions})",
            details={
                "questions_asked": questions,
                "max_allowed": [str(max_questions)],
            },
        )


class MultiDelegationCorrectnessEvaluator(BaseEvaluator):
    """
    [HARD] Checks that Router delegated to ALL expected sub-agents separately.

    This catches the bug where Router tries to batch multi-file updates to a
    single agent instead of delegating to each appropriate agent.

    Example bug scenario:
    - User answers questions requiring updates to spec, plan, and tasks
    - Router should delegate to: specify, plan, tasks (3 separate delegations)
    - Bug: Router delegates "Update spec/plan/tasks" to specify only (1 delegation)

    This is HARD because delegating to the wrong agent means the work won't
    actually be completed correctly.
    """

    name = "multi_delegation_correctness"
    severity = EvaluatorSeverity.HARD

    def evaluate(
        self,
        actual_output: AgentExecutionOutput,
        expected_output: ExpectedAgentOutput | None,
        test_case: ShotgunTestCase,
    ) -> EvaluatorResult:
        """Check that all expected delegations occurred and no disallowed ones did."""
        expected_delegations = set(test_case.expected.expected_delegations)
        disallowed_delegations = set(test_case.expected.disallowed_delegations)

        # If no expected delegations specified, skip this evaluator
        if not expected_delegations and not disallowed_delegations:
            return EvaluatorResult(
                evaluator_name=self.name,
                passed=True,
                severity=self.severity,
                reasoning="No multi-delegation requirements specified",
                details={},
            )

        actual_delegations = set(actual_output.delegated_sub_agents)

        # Check for missing expected delegations
        missing_delegations = expected_delegations - actual_delegations
        # Check for disallowed delegations that occurred
        forbidden_delegations = actual_delegations & disallowed_delegations

        violations: list[str] = []

        if missing_delegations:
            violations.append(
                f"Missing delegations: {', '.join(sorted(missing_delegations))}"
            )

        if forbidden_delegations:
            violations.append(
                f"Disallowed delegations occurred: {', '.join(sorted(forbidden_delegations))}"
            )

        if violations:
            return EvaluatorResult(
                evaluator_name=self.name,
                passed=False,
                severity=self.severity,
                reasoning=f"Delegation routing incorrect: {'; '.join(violations)}",
                details={
                    "expected_delegations": sorted(expected_delegations),
                    "disallowed_delegations": sorted(disallowed_delegations),
                    "actual_delegations": sorted(actual_delegations),
                    "missing": sorted(missing_delegations),
                    "forbidden": sorted(forbidden_delegations),
                },
            )

        return EvaluatorResult(
            evaluator_name=self.name,
            passed=True,
            severity=self.severity,
            reasoning=f"Correctly delegated to: {', '.join(sorted(actual_delegations))}",
            details={
                "expected_delegations": sorted(expected_delegations),
                "actual_delegations": sorted(actual_delegations),
            },
        )


# Registry of all deterministic evaluators
DETERMINISTIC_EVALUATORS: list[type[BaseEvaluator]] = [
    DisallowedToolUsageEvaluator,
    ExecutionFailureEvaluator,
    ExpectedToolPresenceEvaluator,
    ContentAssertionEvaluator,
    DelegationCorrectnessEvaluator,
    MultiDelegationCorrectnessEvaluator,
    ClarifyingQuestionsEvaluator,
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
