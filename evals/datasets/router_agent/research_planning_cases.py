"""
Router agent test cases for research-first planning behavior.

Tests that after a user answers clarifying questions about adding a feature
to the codebase, the Router creates a plan that:
1. First researches the codebase
2. Asks more informed clarifying questions
3. Then writes the specification
"""

from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
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

# Test case: After user answers questions about adding Ollama support,
# the plan should include research first
OLLAMA_FEATURE_PLANS_RESEARCH_FIRST = ShotgunTestCase(
    name="ollama_feature_plans_research_first",
    inputs=TestCaseInput(
        # The final user message (answers to clarifying questions)
        prompt=(
            "Q1: What environment are you targeting?\n"
            "A1: desktop\n\n"
            "Q2: Which runtimes/libraries?\n"
            "A2: Ollama\n\n"
            "Q3: What use cases?\n"
            "A3: using it with agents\n\n"
            "Q4: Backend only or UX/API?\n"
            "A4: backend integration"
        ),
        agent_type=AgentType.ROUTER,
        context=TestCaseContext(has_codebase_indexed=True, codebase_name="shotgun"),
        message_history=[
            # Turn 1: User's initial prompt
            ModelRequest(
                parts=[
                    UserPromptPart(
                        content="I want to write a spec for adding local LLM model support"
                    )
                ]
            ),
            # Turn 2: Router asks clarifying questions via final_result tool
            ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="final_result",
                        args={
                            "response": "To write a useful spec, I need to narrow down a few aspects.",
                            "clarifying_questions": [
                                "What environment are you targeting (desktop, CLI, web)?",
                                "Which runtimes/libraries (Ollama, llama.cpp, vLLM)?",
                                "What use cases (chat, embeddings, agents)?",
                                "Backend only or also UX/API surfaces?",
                            ],
                        },
                        tool_call_id="call_clarify",
                    )
                ],
                model_name="eval-model",
            ),
            # Turn 3: Tool return (system acknowledgment)
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        tool_name="final_result",
                        content="Final result processed.",
                        tool_call_id="call_clarify",
                    )
                ]
            ),
        ],
    ),
    expected=ExpectedAgentOutput(
        expected_tools=["create_plan"],
        expected_response=(
            "Plan should have codebase research (delegate_to_research) as the first step, "
            "followed by asking more informed clarifying questions based on research, "
            "and then writing the specification"
        ),
    ),
)

# Test case: After user answers questions about adding authentication,
# the plan should research existing auth patterns first
AUTH_FEATURE_PLANS_RESEARCH_FIRST = ShotgunTestCase(
    name="auth_feature_plans_research_first",
    inputs=TestCaseInput(
        prompt=(
            "Q1: What type of authentication?\n"
            "A1: OAuth2 with Google and GitHub\n\n"
            "Q2: Session management?\n"
            "A2: JWT tokens stored in HTTP-only cookies\n\n"
            "Q3: Any existing auth code to build on?\n"
            "A3: Not sure, you should check the codebase"
        ),
        agent_type=AgentType.ROUTER,
        context=TestCaseContext(has_codebase_indexed=True, codebase_name="shotgun"),
        message_history=[
            ModelRequest(
                parts=[
                    UserPromptPart(
                        content="I want to add authentication to this project"
                    )
                ]
            ),
            ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="final_result",
                        args={
                            "response": "I need some details to write a good auth spec.",
                            "clarifying_questions": [
                                "What type of authentication (OAuth, username/password, SSO)?",
                                "How should sessions be managed (JWT, server sessions)?",
                                "Any existing auth code to build on?",
                            ],
                        },
                        tool_call_id="call_auth_clarify",
                    )
                ],
                model_name="eval-model",
            ),
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        tool_name="final_result",
                        content="Final result processed.",
                        tool_call_id="call_auth_clarify",
                    )
                ]
            ),
        ],
    ),
    expected=ExpectedAgentOutput(
        expected_tools=["create_plan"],
        expected_response=(
            "Plan should research the codebase first to understand existing patterns "
            "and architecture before writing the authentication specification"
        ),
    ),
)

# Test case: After user answers questions about adding caching,
# the plan should research current architecture first
CACHE_FEATURE_PLANS_RESEARCH_FIRST = ShotgunTestCase(
    name="cache_feature_plans_research_first",
    inputs=TestCaseInput(
        prompt=(
            "Q1: What do you want to cache?\n"
            "A1: API responses from the LLM providers\n\n"
            "Q2: What cache backend?\n"
            "A2: Redis would be nice\n\n"
            "Q3: TTL requirements?\n"
            "A3: About 1 hour for most things"
        ),
        agent_type=AgentType.ROUTER,
        context=TestCaseContext(has_codebase_indexed=True, codebase_name="shotgun"),
        message_history=[
            ModelRequest(
                parts=[UserPromptPart(content="Add caching to improve performance")]
            ),
            ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="final_result",
                        args={
                            "response": "I need to understand what you want to cache.",
                            "clarifying_questions": [
                                "What do you want to cache?",
                                "What cache backend (Redis, in-memory, file)?",
                                "TTL requirements?",
                            ],
                        },
                        tool_call_id="call_cache_clarify",
                    )
                ],
                model_name="eval-model",
            ),
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        tool_name="final_result",
                        content="Final result processed.",
                        tool_call_id="call_cache_clarify",
                    )
                ]
            ),
        ],
    ),
    expected=ExpectedAgentOutput(
        expected_tools=["create_plan"],
        expected_response=(
            "Plan should research the codebase first to understand the current "
            "architecture and how caching would integrate, then ask more informed "
            "questions, then write the specification"
        ),
    ),
)

RESEARCH_PLANNING_CASES: list[ShotgunTestCase] = [
    OLLAMA_FEATURE_PLANS_RESEARCH_FIRST,
    AUTH_FEATURE_PLANS_RESEARCH_FIRST,
    CACHE_FEATURE_PLANS_RESEARCH_FIRST,
]
