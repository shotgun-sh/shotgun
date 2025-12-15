"""
Router agent test cases for planning behavior.

Tests that the Router asks clarifying questions or creates plans
based on request specificity.
"""

from evals.models import (
    AgentType,
    ExpectedAgentOutput,
    ShotgunTestCase,
    TestCaseContext,
    TestCaseInput,
)

FEATURE_REQUEST_ASKS_QUESTIONS = ShotgunTestCase(
    name="feature_request_asks_questions",
    inputs=TestCaseInput(
        prompt="I want to write a spec for adding support for local models to this project",
        agent_type=AgentType.ROUTER,
        context=TestCaseContext(has_codebase_indexed=True, codebase_name="shotgun"),
    ),
    expected=ExpectedAgentOutput(min_clarifying_questions=1),
)

COMPLEX_FEATURE_ASKS_QUESTIONS = ShotgunTestCase(
    name="complex_feature_asks_questions",
    inputs=TestCaseInput(
        prompt="Add authentication to this project",
        agent_type=AgentType.ROUTER,
        context=TestCaseContext(has_codebase_indexed=True, codebase_name="shotgun"),
    ),
    expected=ExpectedAgentOutput(min_clarifying_questions=1),
)

SPECIFIC_FEATURE_CREATES_PLAN = ShotgunTestCase(
    name="specific_feature_creates_plan",
    inputs=TestCaseInput(
        prompt="I want to add Ollama support for local model inference. Research what's needed and write a spec for it.",
        agent_type=AgentType.ROUTER,
        context=TestCaseContext(has_codebase_indexed=True, codebase_name="shotgun"),
    ),
    expected=ExpectedAgentOutput(
        expected_tools=["create_plan"],
        expected_plan_description="Plan should have research as the first step and writing a specification as the second step",
    ),
)

PLANNING_CASES: list[ShotgunTestCase] = [
    FEATURE_REQUEST_ASKS_QUESTIONS,
    COMPLEX_FEATURE_ASKS_QUESTIONS,
    SPECIFIC_FEATURE_CREATES_PLAN,
]
