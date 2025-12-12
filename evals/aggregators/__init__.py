"""
Aggregators for combining evaluation results from multiple sources.

Aggregators combine:
- Deterministic evaluator results
- LLM judge results
- Per-dimension scores

Into a final score and pass/fail determination.
"""

from evals.aggregators.router_aggregator import (
    AggregatedResult,
    RouterAggregator,
)

__all__ = [
    "RouterAggregator",
    "AggregatedResult",
]
