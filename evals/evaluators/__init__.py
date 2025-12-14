"""
Evaluator implementations for Shotgun agent evaluation.

Organized by evaluator type:
- deterministic/: Rule-based evaluators with deterministic outcomes
- llm_judges/: LLM-as-a-judge evaluators (in evals/judges/)
"""

from evals.evaluators.deterministic.router_delegation import (
    ContentAssertionEvaluator,
    DelegationCorrectnessEvaluator,
    DisallowedToolUsageEvaluator,
    ExecutionFailureEvaluator,
    ExpectedToolPresenceEvaluator,
    RouterDeterministicEvaluator,
    run_all_deterministic_evaluators,
)
from evals.models import EvaluatorResult, EvaluatorSeverity

__all__ = [
    # Base types
    "EvaluatorSeverity",
    "EvaluatorResult",
    "RouterDeterministicEvaluator",
    # Evaluators
    "DisallowedToolUsageEvaluator",
    "ExecutionFailureEvaluator",
    "ExpectedToolPresenceEvaluator",
    "ContentAssertionEvaluator",
    "DelegationCorrectnessEvaluator",
    # Runner
    "run_all_deterministic_evaluators",
]
