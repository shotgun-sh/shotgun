"""
Aggregators for combining evaluation results from multiple sources.

Aggregators combine:
- Deterministic evaluator results
- LLM judge results
- Per-dimension scores

Into a final score and pass/fail determination.
"""

from evals.aggregators.router_aggregator import RouterAggregator
from evals.models import AggregatedResult, DimensionAggregate, DimensionSource

__all__ = [
    "RouterAggregator",
    "AggregatedResult",
    "DimensionAggregate",
    "DimensionSource",
]
