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
# Delegation Routing Suite
# Tests Router correctly routes updates to appropriate sub-agents
# ============================================================================

router_delegation_routing = EvaluationSuite(
    name="router_delegation_routing",
    description="Tests Router correctly delegates to each agent for their files",
    test_case_names=[
        "multi_file_update_delegates_separately",
    ],
    evaluator_names=["router_delegation", "router_correctness_judge"],
    tags=["delegation", "router", "routing"],
)

# ============================================================================
# File Write Suite
# Tests Router delegates to sub-agents which write files
# ============================================================================

router_file_write = EvaluationSuite(
    name="router_file_write",
    description="Tests Router creates plans that include writing core deliverable files",
    test_case_names=[
        "feature_request_creates_plan_with_files",
        "spec_request_creates_plan",
    ],
    evaluator_names=["router_delegation", "router_correctness_judge"],
    tags=["file_write", "router", "planning"],
)

# ============================================================================
# File Request Suite
# Tests Router uses file_requests for binary files instead of asking questions
# ============================================================================

router_file_request = EvaluationSuite(
    name="router_file_request",
    description="Tests Router uses file_requests for PDFs/images instead of asking questions or reading .shotgun files",
    test_case_names=[
        "pdf_file_request_no_questions",
        "image_file_request_no_questions",
        "pdf_direct_access_no_excuses",
        "pdf_no_research_file_read",
    ],
    evaluator_names=["router_delegation"],
    tags=["file_request", "router", "drafting"],
)

# ============================================================================
# Document Files Suite
# Tests Router handles document files (PDFs, images) via file_requests in both modes
# ============================================================================

router_document_files = EvaluationSuite(
    name="router_document_files",
    description="Tests Router handles document files (PDFs, images) via file_requests in both Planning and Drafting modes",
    test_case_names=[
        # Planning mode cases
        "prd_file_planning_mode",
        "user_stories_file_planning_mode",
        "qa_guidelines_file_planning_mode",
        "spec_doc_file_planning_mode",
        # Drafting mode cases
        "prd_file_drafting_mode",
        "user_stories_file_drafting_mode",
        "wireframe_image_drafting_mode",
        "screenshot_for_bug_report",
    ],
    evaluator_names=["router_delegation", "file_requests_judge"],
    tags=["file_request", "router", "documents"],
)

# ============================================================================
# All Router Tests Suite
# Runs all Router agent test cases
# ============================================================================

router_all = EvaluationSuite(
    name="router_all",
    description="All Router agent test cases",
    test_case_names=[
        # Clarifying questions cases
        "vague_prompt_clarifying_questions",
        "performance_request_asks_questions",
        "cache_request_asks_questions",
        "open_source_models_asks_questions",
        # Planning cases
        "feature_request_asks_questions",
        "complex_feature_asks_questions",
        "specific_feature_creates_plan",
        # Research planning cases
        "ollama_feature_plans_research_first",
        "auth_feature_plans_research_first",
        "cache_feature_plans_research_first",
        # Delegation routing cases
        "multi_file_update_delegates_separately",
        # File write cases
        "feature_request_creates_plan_with_files",
        "spec_request_creates_plan",
        # File request cases
        "pdf_file_request_no_questions",
        "image_file_request_no_questions",
        "pdf_direct_access_no_excuses",
        "pdf_no_research_file_read",
        # Document file cases (planning and drafting modes)
        "prd_file_planning_mode",
        "user_stories_file_planning_mode",
        "qa_guidelines_file_planning_mode",
        "spec_doc_file_planning_mode",
        "prd_file_drafting_mode",
        "user_stories_file_drafting_mode",
        "wireframe_image_drafting_mode",
        "screenshot_for_bug_report",
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
    "router_delegation_routing": router_delegation_routing,
    "router_file_write": router_file_write,
    "router_file_request": router_file_request,
    "router_document_files": router_document_files,
    "router_all": router_all,
}

__all__ = [
    "router_smoke",
    "router_core",
    "router_planning",
    "router_delegation_routing",
    "router_file_write",
    "router_file_request",
    "router_document_files",
    "router_all",
    "ROUTER_SUITES",
]
