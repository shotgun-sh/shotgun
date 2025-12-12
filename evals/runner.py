"""
Evaluation runner for Router agent test suites.

Orchestrates execution of test cases, evaluation, and report generation.
Supports running by suite name, tag, or single case with configurable concurrency.

Usage:
    python -m evals.runner --suite router_smoke --report json --out evals/reports/router_smoke.json
    python -m evals.runner --suite router_core --report console
    python -m evals.runner --case delegate_to_research_basic
    python -m evals.runner --tag smoke --report json
"""

import argparse
import asyncio
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import logfire

from evals.aggregators.router_aggregator import AggregatedResult, RouterAggregator
from evals.datasets.router_agent import ALL_ROUTER_CASES
from evals.evaluators.deterministic.router_delegation import (
    run_all_deterministic_evaluators,
)
from evals.executor import ExecutionResult, RouterExecutor
from evals.judges.router_quality_judge import RouterQualityJudge
from evals.logfire_utils import TraceRef
from evals.models import (
    AgentExecutionOutput,
    EvaluationReport,
    EvaluationSuite,
    ShotgunTestCase,
    TestCaseResult,
)
from evals.suites.router_suites import ROUTER_SUITES

logger = logging.getLogger(__name__)


class RunnerConfig:
    """Configuration for the evaluation runner."""

    def __init__(
        self,
        max_concurrency: int = 2,
        enable_judge: bool = True,
        judge_concurrency: int = 1,
        timeout_seconds: float = 300.0,
    ) -> None:
        """Initialize runner configuration.

        Args:
            max_concurrency: Maximum concurrent test case executions
            enable_judge: Whether to run LLM judge evaluation
            judge_concurrency: Concurrency for judge calls (conservative default)
            timeout_seconds: Timeout per test case
        """
        self.max_concurrency = max_concurrency
        self.enable_judge = enable_judge
        self.judge_concurrency = judge_concurrency
        self.timeout_seconds = timeout_seconds


class EvaluationRunner:
    """
    Runs evaluation suites and produces reports.

    Orchestrates:
    1. Test case execution via RouterExecutor
    2. Deterministic evaluation
    3. LLM judge evaluation (optional, with conservative concurrency)
    4. Result aggregation
    5. Report generation
    """

    def __init__(
        self,
        config: RunnerConfig | None = None,
        working_directory: Path | None = None,
    ) -> None:
        """Initialize the evaluation runner.

        Args:
            config: Runner configuration
            working_directory: Working directory for agent execution
        """
        self.config = config or RunnerConfig()
        self.executor = RouterExecutor(working_directory=working_directory)
        self.judge = RouterQualityJudge() if self.config.enable_judge else None
        self.aggregator = RouterAggregator()

    async def run_suite(self, suite_name: str) -> EvaluationReport:
        """Run a named evaluation suite.

        Args:
            suite_name: Name of the suite to run

        Returns:
            EvaluationReport with all results
        """
        if suite_name not in ROUTER_SUITES:
            raise ValueError(
                f"Unknown suite: {suite_name}. Available: {list(ROUTER_SUITES.keys())}"
            )

        suite = ROUTER_SUITES[suite_name]
        return await self._run_suite(suite)

    async def run_by_tag(self, tag: str) -> EvaluationReport:
        """Run all suites matching a tag.

        Args:
            tag: Tag to filter suites by

        Returns:
            Combined EvaluationReport from all matching suites
        """
        matching_suites = [s for s in ROUTER_SUITES.values() if tag in s.tags]

        if not matching_suites:
            available_tags = {t for s in ROUTER_SUITES.values() for t in s.tags}
            raise ValueError(
                f"No suites found with tag: {tag}. Available tags: {available_tags}"
            )

        # Combine all test cases from matching suites
        all_case_names: list[str] = []
        for suite in matching_suites:
            for name in suite.test_case_names:
                if name not in all_case_names:
                    all_case_names.append(name)

        combined_suite = EvaluationSuite(
            name=f"tag:{tag}",
            description=f"Combined suite for tag '{tag}'",
            test_case_names=all_case_names,
            tags=[tag],
        )

        return await self._run_suite(combined_suite)

    async def run_single_case(self, case_name: str) -> EvaluationReport:
        """Run a single test case.

        Args:
            case_name: Name of the test case to run

        Returns:
            EvaluationReport with single result
        """
        if case_name not in ALL_ROUTER_CASES:
            raise ValueError(
                f"Unknown test case: {case_name}. "
                f"Available: {list(ALL_ROUTER_CASES.keys())}"
            )

        single_suite = EvaluationSuite(
            name=f"single:{case_name}",
            description=f"Single case run: {case_name}",
            test_case_names=[case_name],
            tags=["single"],
        )

        return await self._run_suite(single_suite)

    async def _run_suite(self, suite: EvaluationSuite) -> EvaluationReport:
        """Internal method to run an evaluation suite.

        Args:
            suite: Suite to run

        Returns:
            EvaluationReport with all results
        """
        start_time = time.time()
        timestamp = datetime.now(timezone.utc).isoformat()

        with logfire.span(
            "eval.run_suite",
            suite_name=suite.name,
            test_case_count=len(suite.test_case_names),
        ):
            # Get test cases
            test_cases = [
                ALL_ROUTER_CASES[name]
                for name in suite.test_case_names
                if name in ALL_ROUTER_CASES
            ]

            if not test_cases:
                raise ValueError(f"No valid test cases found in suite {suite.name}")

            # Run test cases with concurrency control
            results = await self._run_test_cases(test_cases, suite.name)

            # Build report
            total_duration = time.time() - start_time
            return self._build_report(suite.name, results, total_duration, timestamp)

    async def _run_test_cases(
        self,
        test_cases: list[ShotgunTestCase],
        suite_name: str,
    ) -> list[tuple[AggregatedResult, AgentExecutionOutput]]:
        """Run test cases with concurrency control.

        Args:
            test_cases: Test cases to run
            suite_name: Name of the suite for logging

        Returns:
            List of (AggregatedResult, AgentExecutionOutput) tuples
        """
        semaphore = asyncio.Semaphore(self.config.max_concurrency)
        judge_semaphore = asyncio.Semaphore(self.config.judge_concurrency)

        async def run_single(
            test_case: ShotgunTestCase,
        ) -> tuple[AggregatedResult, AgentExecutionOutput]:
            async with semaphore:
                return await self._evaluate_case(test_case, suite_name, judge_semaphore)

        tasks = [run_single(tc) for tc in test_cases]
        return await asyncio.gather(*tasks)

    async def _evaluate_case(
        self,
        test_case: ShotgunTestCase,
        suite_name: str,
        judge_semaphore: asyncio.Semaphore,
    ) -> tuple[AggregatedResult, AgentExecutionOutput]:
        """Execute and evaluate a single test case.

        Args:
            test_case: Test case to run
            suite_name: Suite name for context
            judge_semaphore: Semaphore for judge concurrency

        Returns:
            Tuple of (AggregatedResult, AgentExecutionOutput)
        """
        with logfire.span(
            "eval.evaluate_case",
            test_case_name=test_case.name,
            suite_name=suite_name,
        ):
            # Execute the test case
            execution_result: ExecutionResult = await self.executor.execute_case(
                test_case, suite_name
            )

            # Handle execution errors
            if execution_result.error:
                logger.error(
                    f"Execution failed for {test_case.name}: {execution_result.error}"
                )
                # Create a minimal aggregated result for failed execution
                return self._create_failed_result(
                    test_case.name,
                    execution_result.trace_ref,
                    execution_result.error,
                ), execution_result.output

            # Run deterministic evaluators
            deterministic_results = run_all_deterministic_evaluators(
                execution_result.output,
                test_case.expected_output,
                test_case,
            )

            # Run LLM judge (with concurrency control)
            judge_result = None
            if self.judge:
                async with judge_semaphore:
                    try:
                        judge_result = await self.judge.evaluate(
                            test_case, execution_result.output
                        )
                    except Exception:
                        logger.exception(
                            f"Judge evaluation failed for {test_case.name}"
                        )
                        # Continue without judge result

            # Aggregate results
            aggregated = self.aggregator.aggregate(
                test_case_name=test_case.name,
                deterministic_results=deterministic_results,
                judge_result=judge_result,
                trace_ref=execution_result.trace_ref,
            )

            return aggregated, execution_result.output

    def _create_failed_result(
        self,
        test_case_name: str,
        trace_ref: TraceRef,
        error: str,
    ) -> AggregatedResult:
        """Create an aggregated result for a failed execution.

        Args:
            test_case_name: Name of the test case
            trace_ref: Trace reference
            error: Error message

        Returns:
            AggregatedResult indicating failure
        """
        return AggregatedResult(
            test_case_name=test_case_name,
            passed=False,
            overall_score=1.0,
            deterministic_results=[],
            judge_result=None,
            dimension_scores=[],
            trace_ref=trace_ref,
            summary=f"FAILED: Execution error - {error}",
            hard_failures=[f"Execution error: {error}"],
            soft_failures=[],
        )

    def _build_report(
        self,
        suite_name: str,
        results: list[tuple[AggregatedResult, AgentExecutionOutput]],
        total_duration: float,
        timestamp: str,
    ) -> EvaluationReport:
        """Build the final evaluation report.

        Args:
            suite_name: Name of the suite
            results: List of (AggregatedResult, AgentExecutionOutput) tuples
            total_duration: Total evaluation time
            timestamp: When evaluation started

        Returns:
            EvaluationReport
        """
        test_results: list[TestCaseResult] = []
        total_tokens = 0
        dimension_scores: dict[str, list[float]] = {}

        for aggregated, execution_output in results:
            # Convert to TestCaseResult
            test_result = self.aggregator.convert_to_test_case_result(
                aggregated, execution_output
            )
            test_results.append(test_result)

            # Accumulate tokens
            total_tokens += sum(execution_output.token_usage.values())

            # Collect dimension scores for averaging
            for dim_score in aggregated.dimension_scores:
                if dim_score.dimension not in dimension_scores:
                    dimension_scores[dim_score.dimension] = []
                dimension_scores[dim_score.dimension].append(dim_score.score)

        # Calculate stats
        passed_count = sum(1 for r in test_results if r.passed)
        failed_count = len(test_results) - passed_count
        pass_rate = passed_count / len(test_results) if test_results else 0.0

        # Calculate average scores
        scores = [r.average_score for r in test_results if r.average_score is not None]
        average_score = sum(scores) / len(scores) if scores else None

        # Calculate dimension averages
        dimension_averages = {
            dim: sum(vals) / len(vals) for dim, vals in dimension_scores.items() if vals
        }

        return EvaluationReport(
            suite_name=suite_name,
            total_test_cases=len(test_results),
            passed_test_cases=passed_count,
            failed_test_cases=failed_count,
            pass_rate=pass_rate,
            test_results=test_results,
            average_score=average_score,
            total_duration_seconds=total_duration,
            total_tokens_used=total_tokens,
            timestamp=timestamp,
            dimension_averages=dimension_averages,
        )


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run Router agent evaluation suites",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python -m evals.runner --suite router_smoke --report json --out evals/reports/router_smoke.json
    python -m evals.runner --suite router_core --report console
    python -m evals.runner --case delegate_to_research_basic
    python -m evals.runner --tag smoke
        """,
    )

    # Selection options (mutually exclusive)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--suite", help="Run a named suite")
    selection.add_argument("--tag", help="Run all suites matching a tag")
    selection.add_argument("--case", help="Run a single test case")

    # Output options
    parser.add_argument(
        "--report",
        choices=["json", "console", "both"],
        default="console",
        help="Report format (default: console)",
    )
    parser.add_argument(
        "--out",
        type=str,
        help="Output file path for JSON report",
    )

    # Runner options
    parser.add_argument(
        "--concurrency",
        type=int,
        default=2,
        help="Maximum concurrent test case executions (default: 2)",
    )
    parser.add_argument(
        "--no-judge",
        action="store_true",
        help="Skip LLM judge evaluation (faster, deterministic only)",
    )
    parser.add_argument(
        "--judge-concurrency",
        type=int,
        default=1,
        help="Concurrency for judge calls (default: 1, conservative)",
    )

    return parser.parse_args()


async def main() -> int:
    """Main entry point for the evaluation runner."""
    args = parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Create runner config
    config = RunnerConfig(
        max_concurrency=args.concurrency,
        enable_judge=not args.no_judge,
        judge_concurrency=args.judge_concurrency,
    )

    # Create runner
    runner = EvaluationRunner(config=config)

    try:
        # Run based on selection
        if args.suite:
            report = await runner.run_suite(args.suite)
        elif args.tag:
            report = await runner.run_by_tag(args.tag)
        elif args.case:
            report = await runner.run_single_case(args.case)
        else:
            print("Error: Must specify --suite, --tag, or --case", file=sys.stderr)
            return 1

        # Output report
        if args.report in ("console", "both"):
            from evals.reporters.console import ConsoleReporter

            console_reporter = ConsoleReporter()
            console_reporter.print_report(report)

        if args.report in ("json", "both"):
            from evals.reporters.json_reporter import JSONReporter

            json_reporter = JSONReporter()

            if args.out:
                json_reporter.write_report(report, args.out)
                print(f"\nJSON report written to: {args.out}")
            else:
                # Print to stdout if no output file specified
                print(json_reporter.format_report(report))

        # Return exit code based on pass rate
        return 0 if report.pass_rate >= 1.0 else 1

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        logger.exception("Evaluation failed")
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
