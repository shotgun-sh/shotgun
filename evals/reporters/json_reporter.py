"""
JSON reporter for evaluation results.

Provides machine-readable JSON output as the primary artifact format.
Supports writing to file or returning as string.
"""

import json
from pathlib import Path

from evals.models import EvaluationReport


class JSONReporter:
    """
    Formats evaluation reports as JSON.

    The JSON output is the primary machine-readable artifact for:
    - CI/CD integration
    - Historical tracking
    - Analysis tooling
    """

    def __init__(self, indent: int = 2, sort_keys: bool = True) -> None:
        """Initialize the JSON reporter.

        Args:
            indent: JSON indentation level (default: 2)
            sort_keys: Whether to sort keys alphabetically (default: True)
        """
        self.indent = indent
        self.sort_keys = sort_keys

    def format_report(self, report: EvaluationReport) -> str:
        """Format the evaluation report as a JSON string.

        Args:
            report: The evaluation report to format

        Returns:
            JSON-formatted string
        """
        # Use Pydantic's model_dump for proper serialization
        data = report.model_dump(mode="json")

        return json.dumps(
            data,
            indent=self.indent,
            sort_keys=self.sort_keys,
            ensure_ascii=False,
        )

    def write_report(self, report: EvaluationReport, path: str | Path) -> None:
        """Write the evaluation report to a JSON file.

        Args:
            report: The evaluation report to write
            path: File path to write to
        """
        path = Path(path)

        # Create parent directories if needed
        path.parent.mkdir(parents=True, exist_ok=True)

        # Write the report
        json_content = self.format_report(report)
        path.write_text(json_content, encoding="utf-8")

    def to_dict(self, report: EvaluationReport) -> dict[str, object]:
        """Convert the evaluation report to a dictionary.

        Args:
            report: The evaluation report to convert

        Returns:
            Dictionary representation of the report
        """
        return report.model_dump(mode="json")

    def format_comparison_report(self, reports: list[EvaluationReport]) -> str:
        """Format multiple evaluation reports as a comparison JSON.

        Args:
            reports: List of evaluation reports (one per model)

        Returns:
            JSON-formatted string with comparison data
        """
        if not reports:
            return json.dumps({"error": "No reports provided"})

        # Build comparison structure
        comparison = {
            "suite_name": reports[0].suite_name,
            "timestamp": reports[0].timestamp,
            "models_evaluated": len(reports),
            "model_results": [
                {
                    "model_name": r.model_name or "default",
                    "pass_rate": r.pass_rate,
                    "average_score": r.average_score,
                    "passed_test_cases": r.passed_test_cases,
                    "failed_test_cases": r.failed_test_cases,
                    "total_test_cases": r.total_test_cases,
                    "total_duration_seconds": r.total_duration_seconds,
                    "total_tokens_used": r.total_tokens_used,
                    "dimension_averages": r.dimension_averages,
                }
                for r in reports
            ],
            "rankings": self._compute_rankings(reports),
            "detailed_reports": [self.to_dict(r) for r in reports],
        }

        return json.dumps(
            comparison,
            indent=self.indent,
            sort_keys=self.sort_keys,
            ensure_ascii=False,
        )

    def _compute_rankings(
        self, reports: list[EvaluationReport]
    ) -> dict[str, list[dict[str, object]]]:
        """Compute model rankings by different metrics.

        Args:
            reports: List of evaluation reports

        Returns:
            Dictionary with rankings by different metrics
        """
        # Rank by pass rate
        by_pass_rate = sorted(reports, key=lambda r: r.pass_rate, reverse=True)

        # Rank by score (filter out None scores)
        reports_with_scores = [r for r in reports if r.average_score is not None]
        by_score = sorted(
            reports_with_scores,
            key=lambda r: r.average_score or 0,
            reverse=True,
        )

        # Rank by speed (lower is better)
        by_speed = sorted(reports, key=lambda r: r.total_duration_seconds)

        # Rank by efficiency (tokens per test case, lower is better)
        by_efficiency = sorted(
            reports,
            key=lambda r: (
                r.total_tokens_used / r.total_test_cases
                if r.total_test_cases > 0
                else float("inf")
            ),
        )

        return {
            "by_pass_rate": [
                {
                    "rank": i + 1,
                    "model": r.model_name or "default",
                    "value": r.pass_rate,
                }
                for i, r in enumerate(by_pass_rate)
            ],
            "by_score": [
                {
                    "rank": i + 1,
                    "model": r.model_name or "default",
                    "value": r.average_score,
                }
                for i, r in enumerate(by_score)
            ],
            "by_speed": [
                {
                    "rank": i + 1,
                    "model": r.model_name or "default",
                    "value": r.total_duration_seconds,
                }
                for i, r in enumerate(by_speed)
            ],
            "by_efficiency": [
                {
                    "rank": i + 1,
                    "model": r.model_name or "default",
                    "value": (
                        r.total_tokens_used / r.total_test_cases
                        if r.total_test_cases > 0
                        else None
                    ),
                }
                for i, r in enumerate(by_efficiency)
            ],
        }

    def write_comparison_report(
        self, reports: list[EvaluationReport], path: str | Path
    ) -> None:
        """Write a comparison report to a JSON file.

        Args:
            reports: List of evaluation reports
            path: File path to write to
        """
        path = Path(path)

        # Create parent directories if needed
        path.parent.mkdir(parents=True, exist_ok=True)

        # Write the report
        json_content = self.format_comparison_report(reports)
        path.write_text(json_content, encoding="utf-8")
