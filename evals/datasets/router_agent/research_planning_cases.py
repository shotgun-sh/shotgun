"""
Router agent test cases for research-first planning behavior.

Tests that when a user provides specific requirements for a feature,
the Router creates a plan that:
1. First researches the codebase to understand current architecture
2. Then writes the specification based on that understanding

Note: These tests are single-turn only. The prompts contain enough context
for the Router to understand the user's requirements without multi-turn conversation.
"""

from evals.models import (
    AgentType,
    ExpectedAgentOutput,
    ShotgunTestCase,
    TestCaseContext,
    TestCaseInput,
)

# Test case: Specific Ollama feature request should create plan with research first
OLLAMA_FEATURE_PLANS_RESEARCH_FIRST = ShotgunTestCase(
    name="ollama_feature_plans_research_first",
    inputs=TestCaseInput(
        prompt=(
            "I want to add Ollama support for local LLM inference to this project. "
            "The scope is: developer machines only, Ollama runtime for v1 (we can extend later), "
            "and I want example configs in the spec. Please research the codebase first "
            "to understand the current architecture, then write a spec."
        ),
        agent_type=AgentType.ROUTER,
        context=TestCaseContext(has_codebase_indexed=True, codebase_name="shotgun"),
    ),
    expected=ExpectedAgentOutput(
        expected_tools=["create_plan"],
        expected_response=(
            "Plan should start with researching/reviewing the existing codebase architecture "
            "to understand current patterns before writing the specification. "
            "The plan should be practical and grounded in understanding the existing code first."
        ),
    ),
)

# Test case: Specific auth feature request should create plan with research first
AUTH_FEATURE_PLANS_RESEARCH_FIRST = ShotgunTestCase(
    name="auth_feature_plans_research_first",
    inputs=TestCaseInput(
        prompt=(
            "I want to add OAuth2 authentication with Google and GitHub providers to this project. "
            "Sessions should use JWT tokens stored in HTTP-only cookies. "
            "Please check the codebase for any existing auth code to build on, "
            "then write a specification for the implementation."
        ),
        agent_type=AgentType.ROUTER,
        context=TestCaseContext(has_codebase_indexed=True, codebase_name="shotgun"),
    ),
    expected=ExpectedAgentOutput(
        expected_tools=["create_plan"],
        expected_response=(
            "Plan should start with researching/reviewing the existing codebase "
            "to understand current auth patterns and architecture before writing the specification. "
            "The plan should be practical and grounded in understanding the existing code first."
        ),
    ),
)

# Test case: Specific caching feature request should create plan with research first
CACHE_FEATURE_PLANS_RESEARCH_FIRST = ShotgunTestCase(
    name="cache_feature_plans_research_first",
    inputs=TestCaseInput(
        prompt=(
            "I want to add Redis caching for LLM provider API responses to improve performance. "
            "TTL should be about 1 hour for most cached items. "
            "Please research the current architecture to understand how caching would integrate, "
            "then write a specification."
        ),
        agent_type=AgentType.ROUTER,
        context=TestCaseContext(has_codebase_indexed=True, codebase_name="shotgun"),
    ),
    expected=ExpectedAgentOutput(
        expected_tools=["create_plan"],
        expected_response=(
            "Plan should start with researching/reviewing the existing codebase "
            "to understand the current architecture and how caching would integrate. "
            "The plan should be practical and grounded in understanding the existing code first."
        ),
    ),
)

RESEARCH_PLANNING_CASES: list[ShotgunTestCase] = [
    OLLAMA_FEATURE_PLANS_RESEARCH_FIRST,
    AUTH_FEATURE_PLANS_RESEARCH_FIRST,
    CACHE_FEATURE_PLANS_RESEARCH_FIRST,
]
