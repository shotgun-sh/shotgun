"""Benchmark system for codebase indexing performance analysis.

This package provides tools for running benchmarks and reporting metrics
for the codebase indexing pipeline.
"""

from shotgun.codebase.benchmarks.benchmark_runner import BenchmarkRunner
from shotgun.codebase.benchmarks.exporters import MetricsExporter
from shotgun.codebase.benchmarks.formatters import (
    CsvFormatter,
    JsonFormatter,
    MarkdownFormatter,
    TextFormatter,
    get_formatter,
)

__all__ = [
    "BenchmarkRunner",
    "CsvFormatter",
    "JsonFormatter",
    "MarkdownFormatter",
    "MetricsExporter",
    "TextFormatter",
    "get_formatter",
]
