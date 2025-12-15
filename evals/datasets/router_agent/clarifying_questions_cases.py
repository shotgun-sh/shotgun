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

# Plan tools that should NOT be called when asking clarifying questions
PLAN_TOOLS = ["create_plan", "edit_plan", "update_plan", "append_plan"]

VAGUE_PROMPT_CLARIFYING_QUESTIONS = ShotgunTestCase(
    name="vague_prompt_clarifying_questions",
    inputs=TestCaseInput(
        prompt="I want to add a new feature to this project",
        agent_type=AgentType.ROUTER,
        context=TestCaseContext(has_codebase_indexed=False),
    ),
    expected=ExpectedAgentOutput(
        min_clarifying_questions=1,
        disallowed_tools=PLAN_TOOLS,
        expected_response="Questions should be high-level and help understand what feature the user wants to build",
    ),
)

PERFORMANCE_REQUEST_ASKS_QUESTIONS = ShotgunTestCase(
    name="performance_request_asks_questions",
    inputs=TestCaseInput(
        prompt="This app is slow, make it faster",
        agent_type=AgentType.ROUTER,
        context=TestCaseContext(has_codebase_indexed=True, codebase_name="shotgun"),
    ),
    expected=ExpectedAgentOutput(
        min_clarifying_questions=1,
        disallowed_tools=PLAN_TOOLS,
        expected_response="Questions should ask about where the slowness is observed, what operations are slow, and what performance targets are expected",
    ),
)

CACHE_REQUEST_ASKS_QUESTIONS = ShotgunTestCase(
    name="cache_request_asks_questions",
    inputs=TestCaseInput(
        prompt="Add a cache",
        agent_type=AgentType.ROUTER,
        context=TestCaseContext(has_codebase_indexed=True, codebase_name="shotgun"),
    ),
    expected=ExpectedAgentOutput(
        min_clarifying_questions=1,
        disallowed_tools=PLAN_TOOLS,
        expected_response="Questions should ask about what to cache, cache backend preferences, TTL requirements, and invalidation strategy",
    ),
)

OPEN_SOURCE_MODELS_ASKS_QUESTIONS = ShotgunTestCase(
    name="open_source_models_asks_questions",
    inputs=TestCaseInput(
        prompt="I want to write a spec to add support for open source models for this project",
        agent_type=AgentType.ROUTER,
        context=TestCaseContext(has_codebase_indexed=True, codebase_name="shotgun"),
    ),
    expected=ExpectedAgentOutput(
        min_clarifying_questions=1,
        disallowed_tools=PLAN_TOOLS,
        expected_response="Questions should ask about which open source models, what inference backend (Ollama, vLLM, etc), and integration requirements",
    ),
)

CLARIFYING_QUESTIONS_CASES: list[ShotgunTestCase] = [
    VAGUE_PROMPT_CLARIFYING_QUESTIONS,
    PERFORMANCE_REQUEST_ASKS_QUESTIONS,
    CACHE_REQUEST_ASKS_QUESTIONS,
    OPEN_SOURCE_MODELS_ASKS_QUESTIONS,
]
