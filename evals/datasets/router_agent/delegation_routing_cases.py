"""
Router agent test cases for delegation routing correctness.

Tests that the Router correctly identifies when a request should involve
multiple files or requires careful planning before taking action.

Note: These tests are single-turn only. Multi-turn delegation scenarios
are tested through integration tests instead.
"""

from evals.models import (
    AgentType,
    ExpectedAgentOutput,
    ShotgunTestCase,
    TestCaseContext,
    TestCaseInput,
)
from shotgun.agents.router.models import RouterMode

# =============================================================================
# Test Case: Request affecting multiple areas should create a plan first
# =============================================================================

MULTI_AREA_REQUEST_CREATES_PLAN = ShotgunTestCase(
    name="multi_area_request_creates_plan",
    inputs=TestCaseInput(
        prompt="I want to add .env and .tox to the default ignore patterns, and also mark cache invalidation as out of scope in the documentation",
        agent_type=AgentType.ROUTER,
        context=TestCaseContext(
            has_codebase_indexed=True,
            codebase_name="shotgun",
            router_mode=RouterMode.PLANNING,  # Planning mode - Router should create plan
        ),
    ),
    expected=ExpectedAgentOutput(
        # The router should recognize this touches multiple areas and ask questions or create a plan
        min_clarifying_questions=1,
        # Should NOT try to immediately execute without understanding scope
        disallowed_tools=[
            "delegate_to_specify",
            "delegate_to_plan",
            "delegate_to_tasks",
        ],
        expected_response="""The Router should ask clarifying questions about this multi-area request.
Correct behavior: Ask questions to understand where ignore patterns are configured, what documentation needs updating, and scope of changes.
Incorrect behavior: Immediately delegating without understanding the request, or trying to make changes without a plan.""",
    ),
)

# =============================================================================
# Export all test cases
# =============================================================================

DELEGATION_ROUTING_CASES: list[ShotgunTestCase] = [
    MULTI_AREA_REQUEST_CREATES_PLAN,
]

__all__ = [
    "MULTI_AREA_REQUEST_CREATES_PLAN",
    "DELEGATION_ROUTING_CASES",
]
