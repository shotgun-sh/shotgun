"""
Router agent evaluation suites.

This module defines evaluation suites for the Router agent:
- router_smoke: Quick validation for clarifying questions behavior
- router_core: Full evaluation including LLM judge
- router_planning: Tests for planning behavior with feature requests

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
# Planning Suite
# Tests Router planning behavior for feature requests
# ============================================================================

router_planning = EvaluationSuite(
    name="router_planning",
    description="Router planning behavior for feature requests",
    test_case_names=[
        "feature_request_asks_questions",
        "complex_feature_asks_questions",
        "specific_feature_creates_plan",
    ],
    evaluator_names=["router_delegation", "router_correctness_judge"],
    tags=["planning", "router"],
)

# ============================================================================
# All Router Tests Suite
# Runs all Router agent test cases
# ============================================================================

router_all = EvaluationSuite(
    name="router_all",
    description="All Router agent test cases",
    test_case_names=[
        "vague_prompt_clarifying_questions",
        "performance_request_asks_questions",
        "cache_request_asks_questions",
        "feature_request_asks_questions",
        "complex_feature_asks_questions",
        "specific_feature_creates_plan",
    ],
    evaluator_names=["router_delegation", "router_correctness_judge"],
    tags=["all", "router"],
)

# ============================================================================
# Suite Registry
# ============================================================================

ROUTER_SUITES: dict[str, EvaluationSuite] = {
    "router_smoke": router_smoke,
    "router_core": router_core,
    "router_planning": router_planning,
    "router_all": router_all,
}

__all__ = [
    "router_smoke",
    "router_core",
    "router_planning",
    "router_all",
    "ROUTER_SUITES",
]
