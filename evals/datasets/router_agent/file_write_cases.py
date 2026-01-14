"""
Router agent test cases for verifying plan creation includes file writes.

Tests that the Router creates plans that include writing specification.md,
plan.md, and tasks.md files. These tests run in planning mode (no delegation)
so they execute quickly.

Bug scenario (2026-01-14):
- User asked to "make a plan to build an ai agent"
- Router created execution plan but the plan didn't clearly include
  writing the core deliverable files (specification.md, plan.md, tasks.md)
- When executing, content was dumped to chat instead of files
"""

from evals.models import (
    AgentType,
    ExpectedAgentOutput,
    ShotgunTestCase,
    TestCaseContext,
    TestCaseInput,
)

# =============================================================================
# Test Case: Feature request should create plan with file write steps
# =============================================================================

FEATURE_REQUEST_CREATES_PLAN_WITH_FILES = ShotgunTestCase(
    name="feature_request_creates_plan_with_files",
    inputs=TestCaseInput(
        prompt="I want to build a REST API with JWT authentication and PostgreSQL database",
        agent_type=AgentType.ROUTER,
        context=TestCaseContext(
            has_codebase_indexed=False,
            router_mode="planning",  # Planning mode - no delegation, just create plan
        ),
    ),
    expected=ExpectedAgentOutput(
        # Router should ask clarifying questions for this vague request
        min_clarifying_questions=1,
        # Router should NOT dump full spec content directly
        response_not_contains=[
            "## 1. Overview",  # Full spec section
            "## 2. Functional Requirements",  # Full spec section
            "```python",  # Code blocks (router shouldn't write code)
        ],
    ),
)

# =============================================================================
# Test Case: Spec request should create plan mentioning specification.md
# =============================================================================

SPEC_REQUEST_CREATES_PLAN = ShotgunTestCase(
    name="spec_request_creates_plan",
    inputs=TestCaseInput(
        prompt="Write a specification for a user authentication system",
        agent_type=AgentType.ROUTER,
        context=TestCaseContext(
            has_codebase_indexed=False,
            router_mode="planning",  # Planning mode
        ),
    ),
    expected=ExpectedAgentOutput(
        # Router should ask clarifying questions for this request
        min_clarifying_questions=1,
        # Should NOT output the actual spec content
        response_not_contains=[
            "## Overview",
            "## Requirements",
            "### Authentication Flow",
        ],
    ),
)

# =============================================================================
# Export all test cases
# =============================================================================

FILE_WRITE_CASES: list[ShotgunTestCase] = [
    FEATURE_REQUEST_CREATES_PLAN_WITH_FILES,
    SPEC_REQUEST_CREATES_PLAN,
]

__all__ = [
    "FEATURE_REQUEST_CREATES_PLAN_WITH_FILES",
    "SPEC_REQUEST_CREATES_PLAN",
    "FILE_WRITE_CASES",
]
