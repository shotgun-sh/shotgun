"""
Router agent test cases for delegation routing correctness.

Tests that the Router correctly routes updates to the appropriate sub-agents
based on file ownership. This catches bugs where the Router tries to delegate
multi-file updates to a single agent.

Bug scenario (2025-12-17):
- User answered clarifying questions that required updating spec, plan, and tasks
- Router incorrectly delegated "Update spec/plan/tasks" to specification agent only
- Specification agent can only modify specification.md, not plan.md or tasks.md
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
_TEST_TIMESTAMP = datetime(2025, 12, 17, 10, 0, 0, tzinfo=UTC)

# =============================================================================
# Helper to build message history simulating completed plan execution
# =============================================================================


def _build_post_plan_execution_history() -> list[ModelMessage]:
    """Build message history simulating a state where spec/plan/tasks exist.

    This simulates:
    1. User asked to write a spec for a feature
    2. Router created a plan
    3. Plan was approved and executed (research -> spec -> plan -> tasks)
    4. Sub-agents asked clarifying questions
    5. Now user is answering those questions
    """
    return [
        # Initial user request
        ModelRequest(
            parts=[
                SystemPromptPart(content="You are the Router agent..."),
                UserPromptPart(
                    content="I want to write a spec for adding pathspec-based ignore rules",
                    timestamp=_TEST_TIMESTAMP,
                ),
            ]
        ),
        # Router created plan
        ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="create_plan",
                    args={
                        "goal": "Write spec for pathspec ignore rules",
                        "steps": [
                            {"id": "research", "title": "Research current behavior"},
                            {"id": "spec", "title": "Write specification"},
                            {"id": "plan", "title": "Create implementation plan"},
                            {"id": "tasks", "title": "Generate tasks"},
                        ],
                    },
                    tool_call_id="call_1",
                )
            ],
            model_name="test",
            timestamp=_TEST_TIMESTAMP,
        ),
        # Plan tool return
        ModelRequest(
            parts=[
                ToolReturnPart(
                    tool_name="create_plan",
                    content={"success": True, "message": "Plan created"},
                    tool_call_id="call_1",
                    timestamp=_TEST_TIMESTAMP,
                )
            ]
        ),
        # Router presented plan and asked for approval
        ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="final_result",
                    args={"response": "Here's my plan. Ready to proceed?"},
                    tool_call_id="call_2",
                )
            ],
            model_name="test",
            timestamp=_TEST_TIMESTAMP,
        ),
        # User approved (simulated by "Execute step" message)
        ModelRequest(
            parts=[
                ToolReturnPart(
                    tool_name="final_result",
                    content="Final result processed.",
                    tool_call_id="call_2",
                    timestamp=_TEST_TIMESTAMP,
                ),
                SystemPromptPart(
                    content="""<EXECUTION_PLAN>
**Goal:** Write spec for pathspec ignore rules

**Steps:**
1. ✅ Research current behavior
2. ✅ Write specification
3. ✅ Create implementation plan
4. ✅ Generate tasks
</EXECUTION_PLAN>

<AVAILABLE_FILES>
- specification.md
- plan.md
- tasks.md
- research.md
</AVAILABLE_FILES>"""
                ),
                UserPromptPart(
                    content="""Q1: Should built-in defaults include .env and .tox?
A1: yes

Q2: On .gitignore modification, should cache invalidation be global reset or targeted subtree invalidation?
A2: lets mark that as out of scope for now""",
                    timestamp=_TEST_TIMESTAMP,
                ),
            ]
        ),
    ]


# =============================================================================
# Test Case: Multi-file update should delegate to each agent
# =============================================================================

MULTI_FILE_UPDATE_DELEGATES_SEPARATELY = ShotgunTestCase(
    name="multi_file_update_delegates_separately",
    inputs=TestCaseInput(
        prompt="""Q1: Should built-in defaults include .env and .tox?
A1: yes include them

Q2: On .gitignore modification, should cache invalidation be global reset or targeted subtree invalidation?
A2: lets mark that as out of scope for now and handle it later""",
        agent_type=AgentType.ROUTER,
        context=TestCaseContext(
            has_codebase_indexed=True,
            codebase_name="shotgun",
            router_mode="drafting",  # Delegation tools enabled
        ),
        message_history=_build_post_plan_execution_history(),
    ),
    expected=ExpectedAgentOutput(
        # The router should call multiple delegation tools, NOT just one
        # This is the key assertion - we expect ALL THREE agents to be called
        expected_delegations=["specify", "plan", "tasks"],
        # The router should NOT try to batch updates to a single agent
        response_not_contains=[
            "Update spec/plan/tasks",  # Bad: batched delegation
            "update specification.md, plan.md, and tasks.md",  # Bad: single agent multi-file
        ],
    ),
)

# =============================================================================
# Export all test cases
# =============================================================================

DELEGATION_ROUTING_CASES: list[ShotgunTestCase] = [
    MULTI_FILE_UPDATE_DELEGATES_SEPARATELY,
]

__all__ = [
    "MULTI_FILE_UPDATE_DELEGATES_SEPARATELY",
    "DELEGATION_ROUTING_CASES",
]
