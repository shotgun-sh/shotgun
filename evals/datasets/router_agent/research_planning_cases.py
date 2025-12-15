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
        # User's answers to follow-up questions - triggers plan creation
        prompt=(
            "Q1: Should the spec cover only Ollama in v1, or design for other runtimes later?\n"
            "A1: just ollama for now, we can extend later\n\n"
            "Q2: Do you want concrete example configs in the spec?\n"
            "A2: yes, include example configs"
        ),
        agent_type=AgentType.ROUTER,
        context=TestCaseContext(has_codebase_indexed=True, codebase_name="shotgun"),
        message_history=[
            # User's initial request
            ModelRequest(
                parts=[
                    UserPromptPart(
                        content="I want to write a spec for adding local LLM model support"
                    )
                ]
            ),
            # Router asks initial clarifying questions
            ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="final_result",
                        args={
                            "response": "To help you get a useful, focused spec, I need to "
                            "clarify your goals and constraints for local LLM support first.",
                            "clarifying_questions": [
                                "Where will this local LLM run: on developer machines only, "
                                "end-user desktops, servers, or all of the above?",
                                "What environments must we support initially?",
                                "Which runtimes are in scope for v1?",
                                "How should this integrate into the existing system?",
                            ],
                        },
                        tool_call_id="call_clarify_1",
                    )
                ],
                model_name="eval-model",
            ),
            # Tool return
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        tool_name="final_result",
                        content="Final result processed.",
                        tool_call_id="call_clarify_1",
                    )
                ]
            ),
            # User answers initial questions
            ModelRequest(
                parts=[
                    UserPromptPart(
                        content=(
                            "Q1: Where will this local LLM run?\n"
                            "A1: developer machines\n\n"
                            "Q2: What environments must we support initially?\n"
                            "A2: anything that runs ollama\n\n"
                            "Q3: Which runtimes are in scope for v1?\n"
                            "A3: ollama to start with\n\n"
                            "Q4: How should this integrate?\n"
                            "A4: just make it work like it does now but support ollama models too"
                        )
                    )
                ]
            ),
            # Router asks follow-up questions
            ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="final_result",
                        args={
                            "response": "Thanks for the details. A couple more questions to finalize the scope.",
                            "clarifying_questions": [
                                "Should the spec cover only Ollama in v1, or design for other runtimes later?",
                                "Do you want concrete example configs in the spec?",
                            ],
                        },
                        tool_call_id="call_clarify_2",
                    )
                ],
                model_name="eval-model",
            ),
            # Tool return
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        tool_name="final_result",
                        content="Final result processed.",
                        tool_call_id="call_clarify_2",
                    )
                ]
            ),
        ],
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
            "Plan should start with researching/reviewing the existing codebase "
            "to understand current auth patterns and architecture before writing the specification. "
            "The plan should be practical and grounded in understanding the existing code first."
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
