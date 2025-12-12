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
