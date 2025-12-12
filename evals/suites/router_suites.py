"""
Router agent evaluation suites.

This module defines evaluation suites for the Router agent:
- router_smoke: Quick validation with 4 easy cases
- router_core: Comprehensive testing with all 12 cases

Suites reference test cases by name from evals/datasets/router_agent/.
"""

from evals.models import EvaluationSuite

# ============================================================================
# Smoke Suite (4 EASY cases)
# Quick validation for basic Router delegation functionality
# ============================================================================

router_smoke = EvaluationSuite(
    name="router_smoke",
    description="Quick smoke test with 4 easy Router delegation cases",
    test_case_names=[
        "delegate_to_research_basic",
        "delegate_to_research_web_search",
        "delegate_to_export",
        "handle_out_of_scope",
    ],
    evaluator_names=["router_delegation"],
    tags=["smoke", "router", "quick"],
)

# ============================================================================
# Core Suite (All 12 cases)
# Comprehensive Router evaluation covering all scenarios
# ============================================================================

router_core = EvaluationSuite(
    name="router_core",
    description="Comprehensive Router evaluation with all 12 test cases",
    test_case_names=[
        # Direct Delegation (5)
        "delegate_to_research_basic",
        "delegate_to_research_web_search",
        "delegate_to_specify",
        "delegate_to_tasks",
        "delegate_to_export",
        # Plan Creation (3)
        "create_plan_basic",
        "create_plan_complex",
        "create_plan_with_research",
        # Multi-Step Workflow (2)
        "workflow_research_to_specify",
        "workflow_full_pipeline",
        # Error Handling (2)
        "handle_ambiguous_request",
        "handle_out_of_scope",
    ],
    evaluator_names=["router_delegation", "router_correctness_judge"],
    tags=["core", "router", "comprehensive"],
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
