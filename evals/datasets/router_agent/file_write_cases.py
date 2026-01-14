"""
Router agent test cases for verifying file write behavior.

Tests that the Router correctly delegates to sub-agents which write files.
This catches bugs where:
- Router outputs content directly via final_result instead of delegating
- Sub-agents output content to chat instead of calling write_file()

Bug scenario (2026-01-14):
- User asked to "make a plan to build an ai agent"
- Router created execution plan but just marked steps done without delegating
- When user said "lets turn it into a full spec", Router dumped 2600-token spec
  directly in response instead of delegating to specification agent
- specification.md was never created
"""

from datetime import UTC, datetime

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from evals.models import (
    AgentType,
    ExpectedAgentOutput,
    ShotgunTestCase,
    TestCaseContext,
    TestCaseInput,
)

# Fixed timestamp for deterministic test data
_TEST_TIMESTAMP = datetime(2026, 1, 14, 10, 0, 0, tzinfo=UTC)

# =============================================================================
# Helper to build message history for spec request after clarification
# =============================================================================


def _build_post_clarification_history() -> list[ModelMessage]:
    """Build message history where user answered clarifying questions.

    This simulates:
    1. User asked to write a spec
    2. Router asked clarifying questions
    3. User answered the questions
    4. Now Router should delegate to specification agent
    """
    return [
        # Initial user request
        ModelRequest(
            parts=[
                SystemPromptPart(content="You are the Router agent..."),
                UserPromptPart(
                    content="Write a spec for a REST API",
                    timestamp=_TEST_TIMESTAMP,
                ),
            ]
        ),
        # Router asked clarifying questions
        ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="final_result",
                    args={
                        "response": "I'll help with the spec. A few questions first:",
                        "clarifying_questions": [
                            "What authentication method?",
                            "What database?",
                        ],
                    },
                    tool_call_id="call_1",
                )
            ],
            model_name="test",
            timestamp=_TEST_TIMESTAMP,
        ),
        # Tool return
        ModelRequest(
            parts=[
                ToolReturnPart(
                    tool_name="final_result",
                    content="Final result processed.",
                    tool_call_id="call_1",
                    timestamp=_TEST_TIMESTAMP,
                ),
                SystemPromptPart(
                    content="""<EXECUTION_PLAN>
**Goal:** Write REST API specification

**Steps:**
1. ⬜ Write specification ◀
</EXECUTION_PLAN>"""
                ),
                UserPromptPart(
                    content="""Q1: What authentication method?
A1: JWT tokens

Q2: What database?
A2: PostgreSQL""",
                    timestamp=_TEST_TIMESTAMP,
                ),
            ]
        ),
    ]


# =============================================================================
# Test Case: Spec request should delegate to specification agent
# =============================================================================

SPEC_REQUEST_DELEGATES_TO_SPECIFICATION = ShotgunTestCase(
    name="spec_request_delegates_to_specification",
    inputs=TestCaseInput(
        prompt="""Q1: What authentication method?
A1: JWT tokens

Q2: What database?
A2: PostgreSQL""",
        agent_type=AgentType.ROUTER,
        context=TestCaseContext(
            has_codebase_indexed=True,
            codebase_name="shotgun",
            router_mode="drafting",  # Delegation tools enabled
        ),
        message_history=_build_post_clarification_history(),
    ),
    expected=ExpectedAgentOutput(
        # Router MUST delegate to specification agent
        expected_delegations=["specify"],
        # Router should NOT output the spec content directly
        response_not_contains=[
            "## 1. Overview",  # Spec section heading dumped in response
            "## 2. Functional Requirements",  # Spec section heading
            "### Authentication",  # Spec subsection
        ],
    ),
)

# =============================================================================
# Test Case: Clear spec request in drafting mode delegates immediately
# =============================================================================

CLEAR_SPEC_REQUEST_DELEGATES = ShotgunTestCase(
    name="clear_spec_request_delegates",
    inputs=TestCaseInput(
        prompt="Write a specification for a REST API with JWT authentication and PostgreSQL database",
        agent_type=AgentType.ROUTER,
        context=TestCaseContext(
            has_codebase_indexed=True,
            codebase_name="shotgun",
            router_mode="drafting",  # Delegation tools enabled
        ),
    ),
    expected=ExpectedAgentOutput(
        # With clear requirements in drafting mode, should delegate directly
        expected_delegations=["specify"],
        # Should not dump spec content in response
        response_not_contains=[
            "## Overview",
            "## Requirements",
        ],
    ),
)

# =============================================================================
# Export all test cases
# =============================================================================

FILE_WRITE_CASES: list[ShotgunTestCase] = [
    SPEC_REQUEST_DELEGATES_TO_SPECIFICATION,
    CLEAR_SPEC_REQUEST_DELEGATES,
]

__all__ = [
    "SPEC_REQUEST_DELEGATES_TO_SPECIFICATION",
    "CLEAR_SPEC_REQUEST_DELEGATES",
    "FILE_WRITE_CASES",
]
