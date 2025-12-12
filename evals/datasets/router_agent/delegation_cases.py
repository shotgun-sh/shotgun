"""
Router agent delegation test cases.

This module contains 12 test cases covering:
- 5 Direct Delegation cases (Router identifies and delegates to single sub-agent)
- 3 Plan Creation cases (Router creates implementation plan when requested)
- 2 Multi-Step Workflow cases (Router coordinates multiple agents)
- 2 Error Handling cases (Router handles invalid/ambiguous requests)

Difficulty distribution:
- EASY: 4 cases
- MEDIUM: 5 cases
- HARD: 3 cases
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
# Direct Delegation Cases (5 cases)
# Router correctly identifies and delegates to a single sub-agent
# ============================================================================

DELEGATE_TO_RESEARCH_BASIC = ShotgunTestCase(
    name="delegate_to_research_basic",
    inputs=TestCaseInput(
        prompt="Research Python async best practices and common patterns",
        agent_type=AgentType.ROUTER,
        context={},
        enable_tools=True,
    ),
    expected_output=ExpectedAgentOutput(
        response_contains=["research"],
        expected_sub_agent="research",
    ),
    metadata=TestCaseMetadata(
        difficulty=TestDifficulty.EASY,
        category=TestCategory.ROUTER_DELEGATION,
        tags=["router", "delegation", "research"],
        expected_sub_agent="research",
        description="Router should delegate research request to Research agent",
    ),
)

DELEGATE_TO_RESEARCH_WEB_SEARCH = ShotgunTestCase(
    name="delegate_to_research_web_search",
    inputs=TestCaseInput(
        prompt="Find information about OAuth2 authentication flows and best practices for secure implementation",
        agent_type=AgentType.ROUTER,
        context={},
        enable_tools=True,
    ),
    expected_output=ExpectedAgentOutput(
        response_contains=["OAuth", "authentication"],
        expected_sub_agent="research",
    ),
    metadata=TestCaseMetadata(
        difficulty=TestDifficulty.EASY,
        category=TestCategory.ROUTER_DELEGATION,
        tags=["router", "delegation", "research", "web-search"],
        expected_sub_agent="research",
        description="Router should delegate web research to Research agent",
    ),
)

DELEGATE_TO_SPECIFY = ShotgunTestCase(
    name="delegate_to_specify",
    inputs=TestCaseInput(
        prompt="Write a specification for a user authentication system with email and social login",
        agent_type=AgentType.ROUTER,
        context={
            "research_available": True,
            "research_content": "OAuth2 research findings...",
        },
        enable_tools=True,
    ),
    expected_output=ExpectedAgentOutput(
        response_contains=["specification", "authentication"],
        expected_sub_agent="specify",
    ),
    metadata=TestCaseMetadata(
        difficulty=TestDifficulty.MEDIUM,
        category=TestCategory.ROUTER_DELEGATION,
        tags=["router", "delegation", "specify"],
        expected_sub_agent="specify",
        description="Router should delegate specification writing to Specify agent",
    ),
)

DELEGATE_TO_TASKS = ShotgunTestCase(
    name="delegate_to_tasks",
    inputs=TestCaseInput(
        prompt="Break down the authentication implementation into specific coding tasks",
        agent_type=AgentType.ROUTER,
        context={
            "plan_available": True,
            "plan_content": "Implementation plan with stages...",
        },
        enable_tools=True,
    ),
    expected_output=ExpectedAgentOutput(
        response_contains=["task"],
        expected_sub_agent="tasks",
    ),
    metadata=TestCaseMetadata(
        difficulty=TestDifficulty.MEDIUM,
        category=TestCategory.ROUTER_DELEGATION,
        tags=["router", "delegation", "tasks"],
        expected_sub_agent="tasks",
        description="Router should delegate task breakdown to Tasks agent",
    ),
)

DELEGATE_TO_EXPORT = ShotgunTestCase(
    name="delegate_to_export",
    inputs=TestCaseInput(
        prompt="Export the current session as markdown documentation",
        agent_type=AgentType.ROUTER,
        context={},
        enable_tools=True,
    ),
    expected_output=ExpectedAgentOutput(
        response_contains=["export"],
        expected_sub_agent="export",
    ),
    metadata=TestCaseMetadata(
        difficulty=TestDifficulty.EASY,
        category=TestCategory.ROUTER_DELEGATION,
        tags=["router", "delegation", "export"],
        expected_sub_agent="export",
        description="Router should delegate export request to Export agent",
    ),
)


# ============================================================================
# Plan Creation Cases (3 cases)
# Router creates implementation plan when requested
# ============================================================================

CREATE_PLAN_BASIC = ShotgunTestCase(
    name="create_plan_basic",
    inputs=TestCaseInput(
        prompt="Create an implementation plan for adding dark mode to the application",
        agent_type=AgentType.ROUTER,
        context={},
        enable_tools=True,
    ),
    expected_output=ExpectedAgentOutput(
        response_contains=["plan", "stage"],
        tools_used=["create_plan"],
    ),
    metadata=TestCaseMetadata(
        difficulty=TestDifficulty.MEDIUM,
        category=TestCategory.ROUTER_DELEGATION,
        tags=["router", "plan", "create"],
        expected_tools=["create_plan"],
        description="Router should create a multi-stage plan for feature implementation",
    ),
)

CREATE_PLAN_COMPLEX = ShotgunTestCase(
    name="create_plan_complex",
    inputs=TestCaseInput(
        prompt="I need a comprehensive implementation plan for building a real-time notification system with WebSocket support, message queuing, and mobile push notifications",
        agent_type=AgentType.ROUTER,
        context={},
        enable_tools=True,
    ),
    expected_output=ExpectedAgentOutput(
        response_contains=["plan", "stage"],
        tools_used=["create_plan"],
    ),
    metadata=TestCaseMetadata(
        difficulty=TestDifficulty.HARD,
        category=TestCategory.ROUTER_DELEGATION,
        tags=["router", "plan", "complex"],
        expected_tools=["create_plan"],
        description="Router should create detailed plan for complex multi-component system",
    ),
)

CREATE_PLAN_WITH_RESEARCH = ShotgunTestCase(
    name="create_plan_with_research",
    inputs=TestCaseInput(
        prompt="Plan the implementation of a caching layer for our API - we need research first to understand options, then a plan",
        agent_type=AgentType.ROUTER,
        context={},
        enable_tools=True,
    ),
    expected_output=ExpectedAgentOutput(
        response_contains=["research", "plan"],
    ),
    metadata=TestCaseMetadata(
        difficulty=TestDifficulty.HARD,
        category=TestCategory.MULTI_STEP,
        tags=["router", "plan", "research", "multi-step"],
        description="Router should identify need for research before planning",
    ),
)


# ============================================================================
# Multi-Step Workflow Cases (2 cases)
# Router coordinates multiple agents in sequence
# ============================================================================

WORKFLOW_RESEARCH_TO_SPECIFY = ShotgunTestCase(
    name="workflow_research_to_specify",
    inputs=TestCaseInput(
        prompt="Research GraphQL best practices and then write a specification for our new GraphQL API",
        agent_type=AgentType.ROUTER,
        context={},
        enable_tools=True,
    ),
    expected_output=ExpectedAgentOutput(
        response_contains=["research", "specification"],
    ),
    metadata=TestCaseMetadata(
        difficulty=TestDifficulty.HARD,
        category=TestCategory.MULTI_STEP,
        tags=["router", "workflow", "research", "specify"],
        description="Router should coordinate Research then Specify agents",
    ),
)

WORKFLOW_FULL_PIPELINE = ShotgunTestCase(
    name="workflow_full_pipeline",
    inputs=TestCaseInput(
        prompt="Help me implement a feature: I need to add rate limiting to our API. Start with research, then spec, then plan.",
        agent_type=AgentType.ROUTER,
        context={},
        enable_tools=True,
    ),
    expected_output=ExpectedAgentOutput(
        response_contains=["research", "specification", "plan"],
    ),
    metadata=TestCaseMetadata(
        difficulty=TestDifficulty.EXPERT,
        category=TestCategory.MULTI_STEP,
        tags=["router", "workflow", "full-pipeline"],
        description="Router should coordinate full Research -> Specify -> Plan workflow",
    ),
)


# ============================================================================
# Error Handling Cases (2 cases)
# Router handles invalid/ambiguous requests appropriately
# ============================================================================

HANDLE_AMBIGUOUS_REQUEST = ShotgunTestCase(
    name="handle_ambiguous_request",
    inputs=TestCaseInput(
        prompt="Make it better",
        agent_type=AgentType.ROUTER,
        context={},
        enable_tools=True,
    ),
    expected_output=ExpectedAgentOutput(
        response_contains=[],  # Should ask for clarification, not delegate blindly
    ),
    metadata=TestCaseMetadata(
        difficulty=TestDifficulty.MEDIUM,
        category=TestCategory.ERROR_HANDLING,
        tags=["router", "error-handling", "ambiguous"],
        description="Router should ask for clarification on ambiguous request",
    ),
)

HANDLE_OUT_OF_SCOPE = ShotgunTestCase(
    name="handle_out_of_scope",
    inputs=TestCaseInput(
        prompt="What's the weather like today in San Francisco?",
        agent_type=AgentType.ROUTER,
        context={},
        enable_tools=True,
    ),
    expected_output=ExpectedAgentOutput(
        response_contains=[],  # Should explain scope limitations
    ),
    metadata=TestCaseMetadata(
        difficulty=TestDifficulty.EASY,
        category=TestCategory.ERROR_HANDLING,
        tags=["router", "error-handling", "out-of-scope"],
        description="Router should handle out-of-scope requests gracefully",
    ),
)


# ============================================================================
# Export All Cases
# ============================================================================

DELEGATION_CASES: list[ShotgunTestCase] = [
    # Direct Delegation (5)
    DELEGATE_TO_RESEARCH_BASIC,
    DELEGATE_TO_RESEARCH_WEB_SEARCH,
    DELEGATE_TO_SPECIFY,
    DELEGATE_TO_TASKS,
    DELEGATE_TO_EXPORT,
    # Plan Creation (3)
    CREATE_PLAN_BASIC,
    CREATE_PLAN_COMPLEX,
    CREATE_PLAN_WITH_RESEARCH,
    # Multi-Step Workflow (2)
    WORKFLOW_RESEARCH_TO_SPECIFY,
    WORKFLOW_FULL_PIPELINE,
    # Error Handling (2)
    HANDLE_AMBIGUOUS_REQUEST,
    HANDLE_OUT_OF_SCOPE,
]
