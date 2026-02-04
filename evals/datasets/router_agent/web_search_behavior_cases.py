"""
Router agent test cases for web search behavior in drafting mode.

Tests that the Router doesn't perform excessive web searches when asked
to write specs or plans. In drafting mode, the agent should produce
deliverables rather than endlessly researching.

These cases detect pathological behavior like:
- Search loops where agent keeps searching instead of producing output
- Redundant searches for the same topics
- Inability to synthesize search results into output
"""

from evals.models import (
    AgentType,
    ExpectedAgentOutput,
    JudgeType,
    ShotgunTestCase,
    TestCaseContext,
    TestCaseInput,
)
from shotgun.agents.router.models import RouterMode

# Test: Simple spec request should not trigger excessive web searches
# This is the case that triggered the investigation - asking for a spec
# on building a Pydantic AI agent with FastAPI caused endless searches.
# Using exact prompt from user's reproduction + directive to skip questions.
SPEC_REQUEST_REASONABLE_WEB_SEARCHES = ShotgunTestCase(
    name="spec_request_reasonable_web_searches",
    inputs=TestCaseInput(
        prompt="write a spec for building an ai agent with pydantic ai, it will be hosted via fastapi. Don't ask me any questions, just write the spec.",
        agent_type=AgentType.ROUTER,
        context=TestCaseContext(
            has_codebase_indexed=False,
            router_mode=RouterMode.DRAFTING,  # Drafting mode - delegation tools available
        ),
        # Allow more turns for multi-turn behavior - need enough for delegation chain
        request_limit=25,
        tool_calls_limit=100,
    ),
    expected=ExpectedAgentOutput(
        judge_type=JudgeType.WEB_SEARCH_EFFICIENCY,
        # Limit web searches to detect excessive searching
        max_web_searches=10,
        # Should NOT ask clarifying questions (we told it not to)
        max_clarifying_questions=0,
        # Response should contain spec-like content, not questions
        response_not_contains=[
            "few questions",
            "clarify",
            "Before I proceed",
        ],
        # LLM Judge evaluation criteria
        expected_response="""
The Router should produce a specification document for a Pydantic AI agent with FastAPI.

Correct behavior:
- Delegate to research/specification agents to gather info and write spec
- Produce a coherent spec with sections like Overview, Requirements, API Design, etc.
- Limit web searches to 0-10, focusing on Pydantic AI and FastAPI docs if needed

Incorrect behavior:
- Endless web searches without producing output (11+ searches is concerning)
- Repeated searches for the same topics (Pydantic AI, FastAPI)
- Asking clarifying questions when told not to
- Search count exceeding 15-20 indicates pathological loop behavior
""",
    ),
)

# Test: Complex multi-topic spec should allow more searches but still be bounded
# This serves as a control case - even complex requests shouldn't cause search loops.
COMPLEX_SPEC_REQUEST_BOUNDED_SEARCHES = ShotgunTestCase(
    name="complex_spec_request_bounded_searches",
    inputs=TestCaseInput(
        prompt=(
            "Write a specification for implementing OAuth2 authentication "
            "with support for multiple providers (Google, GitHub, Microsoft). Include "
            "token refresh handling, scope management, and secure token storage. "
            "Don't ask questions, just write the spec."
        ),
        agent_type=AgentType.ROUTER,
        context=TestCaseContext(
            has_codebase_indexed=False,
            router_mode=RouterMode.DRAFTING,
        ),
        # More generous limits for complex topic and delegation chain
        request_limit=30,
        tool_calls_limit=150,
    ),
    expected=ExpectedAgentOutput(
        judge_type=JudgeType.WEB_SEARCH_EFFICIENCY,
        # Higher limit for complex topic, but still bounded
        max_web_searches=15,
        max_clarifying_questions=0,
        response_not_contains=[
            "few questions",
            "clarify",
        ],
        expected_response="""
The Router should produce a comprehensive OAuth2 specification.

Correct behavior:
- Some web searches for OAuth2 specifics, provider differences are acceptable
- Should converge to producing output after 10-15 searches
- Final spec should cover: OAuth2 flow, provider configs, token handling, security

Incorrect behavior:
- Searches exceeding 20-25 even for complex topics indicates problems
- Repeated searches for same OAuth2 topics
- No spec produced despite extensive searching
- Endless "let me research more" without synthesis
""",
    ),
)

# Test: Plan request should be efficient with searches
# Planning requests should delegate quickly with minimal research.
PLAN_REQUEST_MINIMAL_SEARCHES = ShotgunTestCase(
    name="plan_request_minimal_searches",
    inputs=TestCaseInput(
        prompt="Create a plan for adding caching to our API endpoints using Redis. Don't ask questions, just create the plan.",
        agent_type=AgentType.ROUTER,
        context=TestCaseContext(
            has_codebase_indexed=False,
            router_mode=RouterMode.DRAFTING,
        ),
        request_limit=20,
        tool_calls_limit=75,
    ),
    expected=ExpectedAgentOutput(
        judge_type=JudgeType.WEB_SEARCH_EFFICIENCY,
        # Planning should be quick - few searches needed
        max_web_searches=5,
        max_clarifying_questions=0,
        response_not_contains=[
            "few questions",
            "clarify",
            "Before I can plan",
        ],
        expected_response="""
The Router should quickly delegate to planning agent.

Correct behavior:
- Minimal web searches (0-5) - Redis caching is well-known pattern
- Delegate to plan agent to produce implementation plan
- Plan should include: cache strategy, key design, invalidation, etc.

Incorrect behavior:
- More than 5-7 searches for straightforward caching task
- Searching for basic Redis concepts repeatedly
- Not producing a plan despite searching
""",
    ),
)


# Test: Spec request without directive - matches user's exact repro
# This is the EXACT prompt from the user that caused the web search loop
SPEC_REQUEST_NATURAL = ShotgunTestCase(
    name="spec_request_natural",
    inputs=TestCaseInput(
        prompt="write a spec for building an ai agent with pydantic ai, it will be hosted via fastapi",
        agent_type=AgentType.ROUTER,
        context=TestCaseContext(
            has_codebase_indexed=False,
            router_mode=RouterMode.DRAFTING,
        ),
        # Allow enough turns for full delegation chain
        request_limit=30,
        tool_calls_limit=150,
    ),
    expected=ExpectedAgentOutput(
        judge_type=JudgeType.WEB_SEARCH_EFFICIENCY,
        # This is the key test - should not exceed 10 web searches
        max_web_searches=10,
        expected_response="""
This tests the exact scenario that caused excessive web searches.

Correct behavior:
- Router creates a plan and delegates to Research and/or Specification agents
- Research agent does reasonable web searches (5-10 max)
- Produces a coherent spec

Incorrect behavior (the bug):
- Research agent loops doing 11+ web searches
- Searches are repetitive (same topics over and over)
- No convergence to output
""",
    ),
)


# Test: Research-focused prompt that should trigger Research agent delegation
# This prompt is designed to make the Router delegate to Research first
SPEC_RESEARCH_FIRST = ShotgunTestCase(
    name="spec_research_first",
    inputs=TestCaseInput(
        prompt=(
            "I need you to research and then write a spec for building an AI agent. "
            "First, research the Pydantic AI framework - I want to understand its architecture, "
            "how it handles tool calling, and how to integrate it with FastAPI. "
            "Then create a specification based on your research findings."
        ),
        agent_type=AgentType.ROUTER,
        context=TestCaseContext(
            has_codebase_indexed=False,
            router_mode=RouterMode.DRAFTING,
            use_isolated_directory=True,
        ),
        request_limit=30,
        tool_calls_limit=150,
    ),
    expected=ExpectedAgentOutput(
        judge_type=JudgeType.WEB_SEARCH_EFFICIENCY,
        max_web_searches=10,
        expected_response="""
This prompt explicitly asks for research first, which should trigger Research agent.

Correct behavior:
- Router delegates to Research agent first
- Research agent does targeted web searches (3-8 searches)
- Research findings are used to inform spec
- Total web searches stay under 10

Incorrect behavior (the bug):
- Research agent loops doing 11+ web searches
- Same queries repeated
- No convergence despite searching
""",
    ),
)


# ============================================================================
# RESEARCH AGENT DIRECT TESTS
# These test the Research agent directly, bypassing the Router to avoid
# the Router reading existing files and short-circuiting delegation.
# ============================================================================

# Test: Research agent should converge on Pydantic AI research
# This directly tests the agent that was observed looping on web searches
RESEARCH_AGENT_PYDANTIC_AI = ShotgunTestCase(
    name="research_agent_pydantic_ai",
    inputs=TestCaseInput(
        prompt=(
            "Research how to build an AI agent using Pydantic AI framework. "
            "Focus on: the framework architecture, key features, and FastAPI integration. "
            "Provide a summary of your findings."
        ),
        agent_type=AgentType.RESEARCH,  # Direct Research agent test
        context=TestCaseContext(
            has_codebase_indexed=False,
            use_isolated_directory=True,  # Run in temp directory
        ),
        # Generous limits to allow for web searches
        request_limit=20,
        tool_calls_limit=50,
    ),
    expected=ExpectedAgentOutput(
        judge_type=JudgeType.WEB_SEARCH_EFFICIENCY,
        # Research agent should converge within reasonable searches
        max_web_searches=10,
        expected_response="""
The Research agent should perform targeted web searches and synthesize findings.

Correct behavior:
- 3-8 web searches focused on Pydantic AI docs, examples, and FastAPI integration
- Diverse queries (not repeating the same search)
- Produces a coherent summary after gathering information
- Converges to output rather than continuing to search

Incorrect behavior (the bug):
- 11+ web searches indicates a loop
- Repeated/redundant searches for same topics
- No synthesis despite extensive searching
- Agent keeps searching without producing output
""",
    ),
)

# Test: Research agent with simpler task should need fewer searches
RESEARCH_AGENT_SIMPLE_TOPIC = ShotgunTestCase(
    name="research_agent_simple_topic",
    inputs=TestCaseInput(
        prompt=(
            "Research what Python web frameworks support async/await. "
            "List the top 3 options with brief descriptions."
        ),
        agent_type=AgentType.RESEARCH,
        context=TestCaseContext(
            has_codebase_indexed=False,
            use_isolated_directory=True,
        ),
        request_limit=15,
        tool_calls_limit=30,
    ),
    expected=ExpectedAgentOutput(
        judge_type=JudgeType.WEB_SEARCH_EFFICIENCY,
        # Simple topic needs few searches
        max_web_searches=5,
        expected_response="""
Research agent should quickly find well-known frameworks.

Correct behavior:
- 1-3 web searches for async Python frameworks
- Quick convergence to answer (FastAPI, Starlette, AIOHTTP are well-known)
- Brief, focused response

Incorrect behavior:
- More than 5 searches for this simple topic
- Searching for the same "async python frameworks" repeatedly
- Not producing output despite finding information
""",
    ),
)


# Export all test cases
WEB_SEARCH_BEHAVIOR_CASES: list[ShotgunTestCase] = [
    SPEC_REQUEST_REASONABLE_WEB_SEARCHES,
    COMPLEX_SPEC_REQUEST_BOUNDED_SEARCHES,
    PLAN_REQUEST_MINIMAL_SEARCHES,
    SPEC_REQUEST_NATURAL,
    SPEC_RESEARCH_FIRST,
    # Research agent direct tests (bypass Router)
    RESEARCH_AGENT_PYDANTIC_AI,
    RESEARCH_AGENT_SIMPLE_TOPIC,
]
