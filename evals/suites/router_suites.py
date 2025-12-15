"""
Router agent evaluation suites.

This module defines evaluation suites for the Router agent:
- router_smoke: Quick validation for clarifying questions behavior
- router_core: Full evaluation including LLM judge

Suites reference test cases by name from evals/datasets/router_agent/.
"""

from evals.models import EvaluationSuite

# ============================================================================
# Smoke Suite
# Quick validation for basic Router functionality
# ============================================================================

router_smoke = EvaluationSuite(
    name="router_smoke",
    description="Quick smoke test for Router clarifying questions",
    test_case_names=[
        "vague_prompt_clarifying_questions",
    ],
    evaluator_names=["router_delegation"],
    tags=["smoke", "router", "quick"],
)

# ============================================================================
# Core Suite
# Comprehensive Router evaluation with LLM judge
# ============================================================================

router_core = EvaluationSuite(
    name="router_core",
    description="Comprehensive Router evaluation with clarifying questions",
    test_case_names=[
        "vague_prompt_clarifying_questions",
    ],
    evaluator_names=["router_delegation", "router_correctness_judge"],
    tags=["core", "router"],
)

# ============================================================================
# Suite Registry
# ============================================================================

ROUTER_SUITES: dict[str, EvaluationSuite] = {
    "router_smoke": router_smoke,
    "router_core": router_core,
}

__all__ = [
    "router_smoke",
    "router_core",
    "ROUTER_SUITES",
]
