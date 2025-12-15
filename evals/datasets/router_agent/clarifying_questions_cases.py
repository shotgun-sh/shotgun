"""
Router agent test cases for clarifying questions behavior.

Tests that the Router asks clarifying questions when given vague/ambiguous prompts
before taking action or delegating.
"""

from evals.models import (
    AgentType,
    ExpectedAgentOutput,
    ShotgunTestCase,
    TestCaseContext,
    TestCaseInput,
)

VAGUE_PROMPT_CLARIFYING_QUESTIONS = ShotgunTestCase(
    name="vague_prompt_clarifying_questions",
    inputs=TestCaseInput(
        prompt="I want to add a new feature to this project",
        agent_type=AgentType.ROUTER,
        context=TestCaseContext(has_codebase_indexed=False),
    ),
    expected=ExpectedAgentOutput(min_clarifying_questions=1),
)

CLARIFYING_QUESTIONS_CASES: list[ShotgunTestCase] = [
    VAGUE_PROMPT_CLARIFYING_QUESTIONS,
]
