"""
Router agent test cases for clarifying questions behavior.

Tests that the Router asks clarifying questions when given vague/ambiguous prompts
before taking action or delegating.
"""

from evals.models import (
    AgentType,
    ExpectedAgentOutput,
    ShotgunTestCase,
    TestCaseInput,
    TestCaseMetadata,
    TestCategory,
    TestDifficulty,
)

# ============================================================================
# Test Case: Vague prompts should trigger clarifying questions
# ============================================================================

VAGUE_PROMPT_CLARIFYING_QUESTIONS = ShotgunTestCase(
    name="vague_prompt_clarifying_questions",
    inputs=TestCaseInput(
        prompt="I want to add a new feature to this project",
        agent_type=AgentType.ROUTER,
        context={},
        enable_tools=True,
    ),
    expected_output=ExpectedAgentOutput(
        expect_clarifying_questions=True,
        min_clarifying_questions=1,
    ),
    metadata=TestCaseMetadata(
        difficulty=TestDifficulty.EASY,
        category=TestCategory.ROUTER_DELEGATION,
        tags=["router", "clarifying-questions", "vague-prompt"],
        description="Router should ask clarifying questions for vague feature request",
    ),
)

# ============================================================================
# Export all cases
# ============================================================================

CLARIFYING_QUESTIONS_CASES: list[ShotgunTestCase] = [
    VAGUE_PROMPT_CLARIFYING_QUESTIONS,
]
