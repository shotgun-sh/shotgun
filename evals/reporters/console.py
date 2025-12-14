"""
Console reporter for evaluation results.

Provides formatted console output with:
- Per-case score summary
- Trace links/IDs for quick debugging
- Overall statistics and pass/fail status
"""

import sys
from io import StringIO

from evals.models import EvaluationReport, TestCaseResult, build_logfire_url


class ConsoleReporter:
    """
    Formats evaluation reports for console output.

    Emphasizes scores and trace references for quick debugging.
    """

    # ANSI color codes
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

    def __init__(self, use_color: bool = True) -> None:
        """Initialize the console reporter.

        Args:
            use_color: Whether to use ANSI color codes
        """
        self.use_color = use_color and sys.stdout.isatty()

    def _color(self, text: str, color: str) -> str:
        """Apply color to text if colors are enabled."""
        if self.use_color:
            return f"{color}{text}{self.RESET}"
        return text

    def _status_icon(self, passed: bool) -> str:
        """Get status icon for pass/fail."""
        if passed:
            return self._color("[PASS]", self.GREEN)
        return self._color("[FAIL]", self.RED)

    def _score_color(self, score: float) -> str:
        """Get color for a score value."""
        if score >= 4.0:
            return self.GREEN
        elif score >= 3.0:
            return self.YELLOW
        return self.RED

    def format_report(self, report: EvaluationReport) -> str:
        """Format the evaluation report as a string.

        Args:
            report: The evaluation report to format

        Returns:
            Formatted string for console output
        """
        output = StringIO()

        # Header
        output.write("\n")
        output.write(self._color("=" * 80, self.BOLD))
        output.write("\n")
        output.write(
            self._color(f"  EVALUATION REPORT: {report.suite_name}", self.BOLD)
        )
        output.write("\n")
        output.write(self._color("=" * 80, self.BOLD))
        output.write("\n\n")

        # Summary stats
        pass_rate_pct = report.pass_rate * 100
        pass_rate_color = self.GREEN if report.pass_rate >= 0.8 else self.RED

        output.write(f"  Timestamp: {report.timestamp}\n")
        output.write(f"  Duration:  {report.total_duration_seconds:.2f}s\n")
        output.write(f"  Tokens:    {report.total_tokens_used:,}\n")
        output.write("\n")

        output.write(
            f"  Total:  {report.total_test_cases} | "
            f"Passed: {self._color(str(report.passed_test_cases), self.GREEN)} | "
            f"Failed: {self._color(str(report.failed_test_cases), self.RED)} | "
            f"Rate: {self._color(f'{pass_rate_pct:.1f}%', pass_rate_color)}\n"
        )

        if report.average_score is not None:
            score_color = self._score_color(report.average_score)
            output.write(
                f"  Average Score: {self._color(f'{report.average_score:.2f}/5', score_color)}\n"
            )

        output.write("\n")

        # Dimension averages
        if report.dimension_averages:
            output.write(self._color("  Dimension Averages:", self.BOLD))
            output.write("\n")
            for dim, avg in sorted(report.dimension_averages.items()):
                score_color = self._score_color(avg)
                output.write(f"    {dim}: {self._color(f'{avg:.2f}', score_color)}\n")
            output.write("\n")

        # Per-case results
        output.write(self._color("-" * 80, self.BOLD))
        output.write("\n")
        output.write(self._color("  TEST CASE RESULTS", self.BOLD))
        output.write("\n")
        output.write(self._color("-" * 80, self.BOLD))
        output.write("\n\n")

        for result in report.test_results:
            output.write(self._format_test_case_result(result))
            output.write("\n")

        # Footer
        output.write(self._color("=" * 80, self.BOLD))
        output.write("\n")

        overall_status = (
            self._color("PASSED", self.GREEN)
            if report.pass_rate >= 1.0
            else self._color("FAILED", self.RED)
        )
        output.write(f"  Overall: {overall_status}\n")
        output.write(self._color("=" * 80, self.BOLD))
        output.write("\n")

        return output.getvalue()

    def _format_test_case_result(self, result: TestCaseResult) -> str:
        """Format a single test case result.

        Args:
            result: The test case result to format

        Returns:
            Formatted string
        """
        output = StringIO()

        # Status and name
        status = self._status_icon(result.passed)
        output.write(f"  {status} {result.test_case_name}\n")

        # Score
        if result.average_score is not None:
            score_color = self._score_color(result.average_score)
            output.write(
                f"        Score: {self._color(f'{result.average_score:.2f}/5', score_color)}\n"
            )

        # Trace reference - extract from evaluation results if available
        trace_id = self._extract_trace_id(result)
        if trace_id:
            trace_url = build_logfire_url(trace_id)
            short_trace = trace_id[:16] + "..."
            output.write(f"        Trace: {self._color(short_trace, self.BLUE)}\n")
            if trace_url:
                output.write(f"        URL:   {trace_url}\n")

        # Error if present
        if result.error:
            output.write(f"        Error: {self._color(result.error, self.RED)}\n")

        # Evaluator summary (compact)
        failed_evaluators = [
            e.evaluator_name for e in result.evaluation_results if not e.passed
        ]
        if failed_evaluators:
            output.write(
                f"        Failed: {', '.join(failed_evaluators[:3])}"
                f"{'...' if len(failed_evaluators) > 3 else ''}\n"
            )

        return output.getvalue()

    def _extract_trace_id(self, result: TestCaseResult) -> str | None:
        """Extract trace ID from test case result.

        The trace ID is stored in the execution output metadata or
        can be inferred from evaluator context.
        """
        # Look for trace info in evaluation results
        for eval_result in result.evaluation_results:
            if eval_result.dimension and "trace" in eval_result.dimension.lower():
                return eval_result.reasoning

        # Check execution output for trace metadata
        if hasattr(result.execution_output, "token_usage"):
            # The trace ID might be in metadata - for now return None
            # as the actual trace is captured at runner level
            pass

        return None

    def print_report(self, report: EvaluationReport) -> None:
        """Print the evaluation report to stdout.

        Args:
            report: The evaluation report to print
        """
        print(self.format_report(report))
