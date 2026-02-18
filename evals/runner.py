"""
Evaluation runner for Router agent test suites.

Orchestrates execution of test cases, evaluation, and report generation.
Supports running by suite name, tag, or single case with configurable concurrency.

Usage:
    python -m evals.runner --suite router_smoke --report json --out evals/reports/router_smoke.json
    python -m evals.runner --suite router_core --report console
    python -m evals.runner --case local_models_clarifying_questions
    python -m evals.runner --tag smoke
    python -m evals.runner --suite router_smoke --model claude-sonnet-4-6
    python -m evals.runner --suite router_smoke --models anthropic
"""

# Load .env file before any other imports so API keys are available
from dotenv import load_dotenv

load_dotenv(override=True)

import argparse  # noqa: E402
import asyncio  # noqa: E402
import logging  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from pathlib import Path  # noqa: E402

import logfire  # noqa: E402

from evals.aggregators.router_aggregator import RouterAggregator  # noqa: E402
from evals.datasets.router_agent import ALL_ROUTER_CASES  # noqa: E402
from evals.evaluators.deterministic.router_evaluators import (  # noqa: E402
    run_all_deterministic_evaluators,
)
from evals.executor import ExecutionResult, RouterExecutor  # noqa: E402
from evals.judges.file_requests_judge import FileRequestsJudge  # noqa: E402
from evals.judges.router_quality_judge import RouterQualityJudge  # noqa: E402
from evals.judges.web_search_efficiency_judge import (  # noqa: E402
    WebSearchEfficiencyJudge,
)  # noqa: E402
from evals.models import (  # noqa: E402
    AgentExecutionOutput,
    AggregatedResult,
    EvaluationReport,
    EvaluationSuite,
    JudgeType,
    ShotgunTestCase,
    TestCaseResult,
    TraceRef,
)
from evals.reporters.console import ConsoleReporter  # noqa: E402
from evals.reporters.json_reporter import JSONReporter  # noqa: E402
from evals.suites.router_suites import ROUTER_SUITES  # noqa: E402
from shotgun.agents.config.models import (  # noqa: E402
    MODEL_SPECS,
    ModelName,
    ProviderType,
)

logger = logging.getLogger(__name__)


def get_model_presets() -> dict[str, list[ModelName]]:
    """Build model presets from MODEL_SPECS registry.

    Returns:
        Dictionary mapping preset names to lists of ModelName enums.
        Presets include 'all', 'anthropic', 'openai', 'google', and 'fast'.
    """
    all_models = list(MODEL_SPECS.keys())

    # Group by provider
    by_provider: dict[ProviderType, list[ModelName]] = {}
    for model_name, spec in MODEL_SPECS.items():
        by_provider.setdefault(spec.provider, []).append(model_name)

    return {
        "all": all_models,
        "anthropic": by_provider.get(ProviderType.ANTHROPIC, []),
        "openai": by_provider.get(ProviderType.OPENAI, []),
        "google": by_provider.get(ProviderType.GOOGLE, []),
        # Fast models - one per provider (cheapest/fastest)
        "fast": [
            ModelName.CLAUDE_HAIKU_4_5,
            ModelName.GPT_5_1,
            ModelName.GEMINI_2_5_FLASH_LITE,
        ],
    }


# Available model presets for CLI
MODEL_PRESETS = get_model_presets()


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
        # Initialize judges lazily based on evaluator_names
        self._router_judge: RouterQualityJudge | None = None
        self._file_requests_judge: FileRequestsJudge | None = None
        self._web_search_efficiency_judge: WebSearchEfficiencyJudge | None = None
        self.aggregator = RouterAggregator()

    def _get_router_judge(self) -> RouterQualityJudge:
        """Get or create the RouterQualityJudge instance."""
        if self._router_judge is None:
            self._router_judge = RouterQualityJudge()
        return self._router_judge

    def _get_file_requests_judge(self) -> FileRequestsJudge:
        """Get or create the FileRequestsJudge instance."""
        if self._file_requests_judge is None:
            self._file_requests_judge = FileRequestsJudge()
        return self._file_requests_judge

    def _get_web_search_efficiency_judge(self) -> WebSearchEfficiencyJudge:
        """Get or create the WebSearchEfficiencyJudge instance."""
        if self._web_search_efficiency_judge is None:
            self._web_search_efficiency_judge = WebSearchEfficiencyJudge()
        return self._web_search_efficiency_judge

    async def run_suite(
        self,
        suite_name: str,
        model_override: ModelName | None = None,
    ) -> EvaluationReport:
        """Run a named evaluation suite.

        Args:
            suite_name: Name of the suite to run
            model_override: Optional model to use instead of the default

        Returns:
            EvaluationReport with all results
        """
        if suite_name not in ROUTER_SUITES:
            raise ValueError(
                f"Unknown suite: {suite_name}. Available: {list(ROUTER_SUITES.keys())}"
            )

        suite = ROUTER_SUITES[suite_name]
        return await self._run_suite(suite, model_override)

    async def run_by_tag(
        self,
        tag: str,
        model_override: ModelName | None = None,
    ) -> EvaluationReport:
        """Run all suites matching a tag.

        Args:
            tag: Tag to filter suites by
            model_override: Optional model to use instead of the default

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

        return await self._run_suite(combined_suite, model_override)

    async def run_single_case(
        self,
        case_name: str,
        model_override: ModelName | None = None,
    ) -> EvaluationReport:
        """Run a single test case.

        Args:
            case_name: Name of the test case to run
            model_override: Optional model to use instead of the default

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

        return await self._run_suite(single_suite, model_override)

    async def _run_suite(
        self,
        suite: EvaluationSuite,
        model_override: ModelName | None = None,
    ) -> EvaluationReport:
        """Internal method to run an evaluation suite.

        Args:
            suite: Suite to run
            model_override: Optional model to use instead of the default

        Returns:
            EvaluationReport with all results
        """
        start_time = time.time()
        timestamp = datetime.now(timezone.utc).isoformat()

        with logfire.span(
            "eval.run_suite",
            suite_name=suite.name,
            test_case_count=len(suite.test_case_names),
            model_override=model_override.value if model_override else None,
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
            results = await self._run_test_cases(
                test_cases, suite.name, suite.evaluator_names, model_override
            )

            # Build report
            total_duration = time.time() - start_time
            return self._build_report(
                suite.name, results, total_duration, timestamp, model_override
            )

    async def _run_test_cases(
        self,
        test_cases: list[ShotgunTestCase],
        suite_name: str,
        evaluator_names: list[str],
        model_override: ModelName | None = None,
    ) -> list[tuple[AggregatedResult, AgentExecutionOutput]]:
        """Run test cases with concurrency control.

        Args:
            test_cases: Test cases to run
            suite_name: Name of the suite for logging
            evaluator_names: Names of evaluators to apply (determines which judge to use)
            model_override: Optional model to use instead of the default

        Returns:
            List of (AggregatedResult, AgentExecutionOutput) tuples
        """
        semaphore = asyncio.Semaphore(self.config.max_concurrency)
        judge_semaphore = asyncio.Semaphore(self.config.judge_concurrency)

        async def run_single(
            test_case: ShotgunTestCase,
        ) -> tuple[AggregatedResult, AgentExecutionOutput]:
            async with semaphore:
                return await self._evaluate_case(
                    test_case,
                    suite_name,
                    evaluator_names,
                    judge_semaphore,
                    model_override,
                )

        tasks = [run_single(tc) for tc in test_cases]
        return await asyncio.gather(*tasks)

    async def _evaluate_case(
        self,
        test_case: ShotgunTestCase,
        suite_name: str,
        evaluator_names: list[str],
        judge_semaphore: asyncio.Semaphore,
        model_override: ModelName | None = None,
    ) -> tuple[AggregatedResult, AgentExecutionOutput]:
        """Execute and evaluate a single test case.

        Args:
            test_case: Test case to run
            suite_name: Suite name for context
            evaluator_names: Names of evaluators to apply (determines which judge to use)
            judge_semaphore: Semaphore for judge concurrency
            model_override: Optional model to use instead of the default

        Returns:
            Tuple of (AggregatedResult, AgentExecutionOutput)
        """
        with logfire.span(
            "eval.evaluate_case",
            test_case_name=test_case.name,
            suite_name=suite_name,
            model_override=model_override.value if model_override else None,
        ):
            # Execute the test case
            execution_result: ExecutionResult = await self.executor.execute_case(
                test_case, suite_name, model_override
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
                test_case.expected,
                test_case,
            )

            # Run LLM judge (with concurrency control)
            # Select judge based on test_case.expected.judge_type (per-test-case selection)
            from evals.judges.file_requests_judge import FileRequestsJudgeResult
            from evals.judges.web_search_efficiency_judge import (
                WebSearchEfficiencyJudgeResult,
            )
            from evals.models import RouterJudgeResult

            judge_result: (
                RouterJudgeResult
                | FileRequestsJudgeResult
                | WebSearchEfficiencyJudgeResult
                | None
            ) = None
            if self.config.enable_judge:
                async with judge_semaphore:
                    try:
                        judge_type = test_case.expected.judge_type
                        if judge_type == JudgeType.FILE_REQUESTS:
                            # Use FileRequestsJudge for file handling scenarios
                            file_judge = self._get_file_requests_judge()
                            judge_result = await file_judge.evaluate(
                                test_case, execution_result.output
                            )
                        elif judge_type == JudgeType.WEB_SEARCH_EFFICIENCY:
                            # Use WebSearchEfficiencyJudge for web search behavior
                            ws_judge = self._get_web_search_efficiency_judge()
                            judge_result = await ws_judge.evaluate(
                                test_case, execution_result.output
                            )
                        else:
                            # Default: JudgeType.ROUTER_CORRECTNESS
                            # Use RouterQualityJudge for clarifying questions/planning scenarios
                            router_judge = self._get_router_judge()
                            judge_result = await router_judge.evaluate(
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
        model_override: ModelName | None = None,
    ) -> EvaluationReport:
        """Build the final evaluation report.

        Args:
            suite_name: Name of the suite
            results: List of (AggregatedResult, AgentExecutionOutput) tuples
            total_duration: Total evaluation time
            timestamp: When evaluation started
            model_override: Optional model that was used instead of the default

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
            model_name=model_override.value if model_override else None,
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
    # Build available model choices from MODEL_SPECS
    available_models = [m.value for m in ModelName]

    parser = argparse.ArgumentParser(
        description="Run Router agent evaluation suites",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
    python -m evals.runner --suite router_smoke --report json --out evals/reports/router_smoke.json
    python -m evals.runner --suite router_core --report console
    python -m evals.runner --case local_models_clarifying_questions
    python -m evals.runner --tag smoke

Model comparison examples:
    python -m evals.runner --suite router_smoke --model claude-sonnet-4-6
    python -m evals.runner --suite router_smoke --model claude-sonnet-4-6 --model gpt-5.1
    python -m evals.runner --suite router_smoke --models anthropic
    python -m evals.runner --suite router_smoke --models fast

Available models: {", ".join(available_models)}
Available presets: {", ".join(MODEL_PRESETS.keys())}
        """,
    )

    # Selection options (mutually exclusive)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--suite", help="Run a named suite")
    selection.add_argument("--tag", help="Run all suites matching a tag")
    selection.add_argument("--case", help="Run a single test case")

    # Model selection options
    model_group = parser.add_mutually_exclusive_group()
    model_group.add_argument(
        "--model",
        action="append",
        dest="model_list",
        choices=available_models,
        help="Model to evaluate (can be repeated for multiple models)",
    )
    model_group.add_argument(
        "--models",
        choices=list(MODEL_PRESETS.keys()),
        help="Model preset to evaluate (e.g., 'anthropic', 'fast', 'all')",
    )

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


def get_models_to_run(args: argparse.Namespace) -> list[ModelName]:
    """Determine which models to run based on CLI arguments.

    Args:
        args: Parsed CLI arguments

    Returns:
        List of ModelName enums to evaluate. Empty list means use default model.
    """
    if args.model_list:
        # Individual models specified
        return [ModelName(m) for m in args.model_list]
    elif args.models:
        # Model preset specified
        return MODEL_PRESETS[args.models]
    else:
        # No model specified - use default (empty list = no override)
        return []


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

    # Determine which models to run
    models_to_run = get_models_to_run(args)

    try:
        reports: list[EvaluationReport] = []

        # If no models specified, run with default
        if not models_to_run:
            models_to_run_iter: list[ModelName | None] = [None]
        else:
            models_to_run_iter = models_to_run  # type: ignore[assignment]

        # Run evaluation for each model
        for model_override in models_to_run_iter:
            if model_override:
                print(f"\n{'=' * 60}")
                print(f"Running evaluation with model: {model_override.value}")
                print(f"{'=' * 60}\n")

            # Run based on selection
            if args.suite:
                report = await runner.run_suite(args.suite, model_override)
            elif args.tag:
                report = await runner.run_by_tag(args.tag, model_override)
            elif args.case:
                report = await runner.run_single_case(args.case, model_override)
            else:
                print("Error: Must specify --suite, --tag, or --case", file=sys.stderr)
                return 1

            reports.append(report)

            # Output individual report
            if args.report in ("console", "both"):
                console_reporter = ConsoleReporter()
                console_reporter.print_report(report)

        # If multiple models were run, print comparison report
        if len(reports) > 1:
            console_reporter = ConsoleReporter()
            console_reporter.print_comparison_report(reports)

        # Output JSON reports
        if args.report in ("json", "both"):
            json_reporter = JSONReporter()

            if len(reports) == 1:
                # Single report
                if args.out:
                    json_reporter.write_report(reports[0], args.out)
                    print(f"\nJSON report written to: {args.out}")
                else:
                    print(json_reporter.format_report(reports[0]))
            else:
                # Multiple reports - write comparison
                if args.out:
                    json_reporter.write_comparison_report(reports, args.out)
                    print(f"\nJSON comparison report written to: {args.out}")
                else:
                    print(json_reporter.format_comparison_report(reports))

        # Return exit code based on worst pass rate across all models
        min_pass_rate = min(r.pass_rate for r in reports)
        return 0 if min_pass_rate >= 1.0 else 1

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        logger.exception("Evaluation failed")
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
