"""
Aggregator for Router agent evaluation results.

Combines results from:
- Deterministic evaluators (hard/soft failures)
- LLM judge (dimension scores)

Into a final score with:
- Per-evaluator results preserved
- Per-dimension scores
- Overall score
- Trace reference for each case
"""

from evals.models import (
    AgentExecutionOutput,
    AggregatedResult,
    DimensionAggregate,
    EvaluationResult,
    EvaluatorResult,
    EvaluatorSeverity,
    RouterJudgeResult,
    TestCaseResult,
    TraceRef,
)


class RouterAggregator:
    """
    Aggregates evaluation results from deterministic evaluators and LLM judge.

    Aggregation rules:
    1. Any HARD failure from deterministic evaluators -> overall failure
    2. SOFT failures are recorded but don't cause overall failure
    3. LLM judge scores contribute to dimension averages
    4. Overall score is weighted average of all dimensions
    5. Trace reference is attached for debugging
    """

    def __init__(
        self,
        hard_failure_causes_fail: bool = True,
        soft_failure_weight: float = 0.5,
        pass_threshold: float = 3.0,
    ) -> None:
        """Initialize the aggregator.

        Args:
            hard_failure_causes_fail: Whether hard failures cause overall fail
            soft_failure_weight: Weight for soft failure penalty (0-1)
            pass_threshold: Minimum score to pass (1-5 scale, default 3.0)
        """
        self.hard_failure_causes_fail = hard_failure_causes_fail
        self.soft_failure_weight = soft_failure_weight
        self.pass_threshold = pass_threshold

    def aggregate(
        self,
        test_case_name: str,
        deterministic_results: list[EvaluatorResult],
        judge_result: RouterJudgeResult | None,
        trace_ref: TraceRef,
    ) -> AggregatedResult:
        """Aggregate all evaluation results for a test case.

        Args:
            test_case_name: Name of the test case
            deterministic_results: Results from deterministic evaluators
            judge_result: Result from LLM judge (may be None)
            trace_ref: Trace reference for debugging

        Returns:
            AggregatedResult with combined scores and pass/fail
        """
        # Collect failures
        hard_failures: list[str] = []
        soft_failures: list[str] = []

        for result in deterministic_results:
            if not result.passed:
                if result.severity == EvaluatorSeverity.HARD:
                    hard_failures.append(f"{result.evaluator_name}: {result.reasoning}")
                else:
                    soft_failures.append(f"{result.evaluator_name}: {result.reasoning}")

        # Build dimension scores
        dimension_scores: list[DimensionAggregate] = []

        # Add deterministic dimensions
        for result in deterministic_results:
            dimension_scores.append(
                DimensionAggregate(
                    dimension=f"deterministic.{result.evaluator_name}",
                    score=5.0 if result.passed else 1.0,
                    passed=result.passed,
                    source="deterministic",
                )
            )

        # Add judge dimensions
        if judge_result:
            for dim_name, dim_score in judge_result.dimension_scores.items():
                dimension_scores.append(
                    DimensionAggregate(
                        dimension=f"judge.{dim_name}",
                        score=float(dim_score.score),
                        passed=dim_score.passed,
                        source="judge",
                    )
                )

        # Calculate overall score
        overall_score = self._calculate_overall_score(
            deterministic_results, judge_result, hard_failures, soft_failures
        )

        # Determine overall pass/fail
        passed = self._determine_passed(overall_score, hard_failures)

        # Build summary
        summary = self._build_summary(
            passed, overall_score, hard_failures, soft_failures, judge_result
        )

        return AggregatedResult(
            test_case_name=test_case_name,
            passed=passed,
            overall_score=overall_score,
            deterministic_results=deterministic_results,
            judge_result=judge_result,
            dimension_scores=dimension_scores,
            trace_ref=trace_ref,
            summary=summary,
            hard_failures=hard_failures,
            soft_failures=soft_failures,
        )

    def _calculate_overall_score(
        self,
        deterministic_results: list[EvaluatorResult],
        judge_result: RouterJudgeResult | None,
        hard_failures: list[str],
        soft_failures: list[str],
    ) -> float:
        """Calculate the overall score from all sources.

        Scoring approach:
        - Start with judge overall score (if available) or 5.0
        - Hard failures set score to 1.0
        - Soft failures apply penalty based on weight
        """
        # Start with judge score if available
        if judge_result:
            base_score = judge_result.overall_score
        else:
            # If no judge, calculate from deterministic results
            passed_count = sum(1 for r in deterministic_results if r.passed)
            total_count = len(deterministic_results)
            if total_count > 0:
                # Scale to 1-5 range
                base_score = 1.0 + 4.0 * (passed_count / total_count)
            else:
                base_score = 3.0  # Neutral score if no evaluators

        # Hard failures set score to 1.0 (minimum)
        if hard_failures:
            return 1.0

        # Soft failures apply penalty
        if soft_failures:
            penalty = len(soft_failures) * self.soft_failure_weight
            base_score = max(1.0, base_score - penalty)

        return base_score

    def _determine_passed(
        self,
        overall_score: float,
        hard_failures: list[str],
    ) -> bool:
        """Determine if the test case passed overall."""
        if self.hard_failure_causes_fail and hard_failures:
            return False

        return overall_score >= self.pass_threshold

    def _build_summary(
        self,
        passed: bool,
        overall_score: float,
        hard_failures: list[str],
        soft_failures: list[str],
        judge_result: RouterJudgeResult | None,
    ) -> str:
        """Build a human-readable summary of the evaluation."""
        parts: list[str] = []

        status = "PASSED" if passed else "FAILED"
        parts.append(f"{status} (score: {overall_score:.2f}/5)")

        if hard_failures:
            parts.append(f"Hard failures: {len(hard_failures)}")

        if soft_failures:
            parts.append(f"Soft failures: {len(soft_failures)}")

        if judge_result:
            parts.append(f"Judge: {judge_result.summary}")

        return " | ".join(parts)

    def convert_to_test_case_result(
        self,
        aggregated: AggregatedResult,
        execution_output: "AgentExecutionOutput",
    ) -> TestCaseResult:
        """Convert AggregatedResult to standard TestCaseResult model.

        Args:
            aggregated: The aggregated result
            execution_output: The agent's execution output

        Returns:
            Standard TestCaseResult model
        """

        # Convert all results to standard EvaluationResult
        evaluation_results: list[EvaluationResult] = []

        # Add deterministic results
        for det_result in aggregated.deterministic_results:
            evaluation_results.append(
                EvaluationResult(
                    evaluator_name=det_result.evaluator_name,
                    passed=det_result.passed,
                    score=5.0 if det_result.passed else 1.0,
                    reasoning=det_result.reasoning,
                    dimension=f"deterministic.{det_result.evaluator_name}",
                )
            )

        # Add judge results
        if aggregated.judge_result:
            for dim_name, dim_score in aggregated.judge_result.dimension_scores.items():
                evaluation_results.append(
                    EvaluationResult(
                        evaluator_name=f"judge.{dim_name}",
                        passed=dim_score.passed,
                        score=float(dim_score.score),
                        reasoning=dim_score.reasoning,
                        dimension=dim_name,
                    )
                )

        return TestCaseResult(
            test_case_name=aggregated.test_case_name,
            passed=aggregated.passed,
            execution_output=execution_output,
            evaluation_results=evaluation_results,
            average_score=aggregated.overall_score,
            error=None,
        )
