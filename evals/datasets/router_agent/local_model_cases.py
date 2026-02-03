"""
Router agent test cases for local model evaluation (Ollama).

These test cases are designed to be simpler and more suitable for local LLMs
which may have less capability than cloud models. They focus on:
- Basic clarifying questions behavior
- Simple tool usage patterns
- Straightforward routing decisions

Test cases avoid complex multi-step reasoning or nuanced judgments that
local models may struggle with.
"""

from evals.models import (
    AgentType,
    ExpectedAgentOutput,
    ShotgunTestCase,
    TestCaseContext,
    TestCaseInput,
)

# =============================================================================
# Simple Clarifying Questions Cases
# =============================================================================

SIMPLE_GREETING = ShotgunTestCase(
    name="simple_greeting",
    inputs=TestCaseInput(
        prompt="Hello, I need help with my project",
        agent_type=AgentType.ROUTER,
        context=TestCaseContext(has_codebase_indexed=False),
    ),
    expected=ExpectedAgentOutput(
        min_clarifying_questions=1,
        max_clarifying_questions=4,
        expected_response="""The Router should ask basic clarifying questions about what the user needs help with.
        Correct behavior: Ask 1-3 simple questions about the project or what kind of help is needed.
        Incorrect behavior: Immediately delegating without asking questions, or providing a generic response without engagement.""",
    ),
)

LOCAL_MODELS_CLARIFYING_QUESTIONS = ShotgunTestCase(
    name="local_models_clarifying_questions",
    inputs=TestCaseInput(
        prompt="I want to add a new feature",
        agent_type=AgentType.ROUTER,
        context=TestCaseContext(has_codebase_indexed=False),
    ),
    expected=ExpectedAgentOutput(
        min_clarifying_questions=1,
        max_clarifying_questions=4,
        expected_response="""The Router should ask what feature the user wants to add.
        Correct behavior: Ask clarifying questions about the feature - what it does, scope, requirements.
        Incorrect behavior: Assuming what the feature is, or delegating without gathering requirements.""",
    ),
)

BUG_FIX_CLARIFYING_QUESTIONS = ShotgunTestCase(
    name="bug_fix_clarifying_questions",
    inputs=TestCaseInput(
        prompt="There's a bug in my code",
        agent_type=AgentType.ROUTER,
        context=TestCaseContext(has_codebase_indexed=False),
    ),
    expected=ExpectedAgentOutput(
        min_clarifying_questions=1,
        max_clarifying_questions=4,
        expected_response="""The Router should ask about the bug - what behavior is observed, expected behavior, etc.
        Correct behavior: Ask clarifying questions to understand the bug.
        Incorrect behavior: Claiming to fix the bug without understanding it, or delegating without information.""",
    ),
)

# =============================================================================
# Simple Response Cases (no clarifying questions expected)
# =============================================================================

EXPLAIN_WHAT_YOU_DO = ShotgunTestCase(
    name="explain_what_you_do",
    inputs=TestCaseInput(
        prompt="What can you help me with?",
        agent_type=AgentType.ROUTER,
        context=TestCaseContext(has_codebase_indexed=False),
    ),
    expected=ExpectedAgentOutput(
        max_clarifying_questions=2,  # May ask follow-up questions
        expected_response="""The Router should explain its capabilities or ask what the user needs help with.
        Correct behavior: Provide helpful information about capabilities OR ask clarifying questions.
        Incorrect behavior: Ignoring the question, delegating without reason.""",
    ),
)

# =============================================================================
# Context-Aware Cases
# =============================================================================

SIMPLE_CODEBASE_QUESTION = ShotgunTestCase(
    name="simple_codebase_question",
    inputs=TestCaseInput(
        prompt="What does this project do?",
        agent_type=AgentType.ROUTER,
        context=TestCaseContext(has_codebase_indexed=True, codebase_name="shotgun"),
    ),
    expected=ExpectedAgentOutput(
        # May ask questions or delegate to research
        expected_response="""The Router should either ask about specific aspects of the project or indicate it can help research.
        Correct behavior: Engage with the question - either ask for more specifics or offer to explore the codebase.
        Incorrect behavior: Refusing to help, or making up information about the project.""",
    ),
)

# =============================================================================
# Drafting Mode Cases
# =============================================================================

SIMPLE_FILE_REQUEST_DRAFTING = ShotgunTestCase(
    name="simple_file_request_drafting",
    inputs=TestCaseInput(
        prompt="Please read the README.md file",
        agent_type=AgentType.ROUTER,
        context=TestCaseContext(has_codebase_indexed=False, router_mode="drafting"),
    ),
    expected=ExpectedAgentOutput(
        expected_response="""The Router should acknowledge the file request.
        Correct behavior: Acknowledge the request to read the file.
        Incorrect behavior: Refusing to read the file, asking unnecessary questions about a clear request.""",
    ),
)

# =============================================================================
# Test Case Collections
# =============================================================================

LOCAL_MODEL_CASES: list[ShotgunTestCase] = [
    SIMPLE_GREETING,
    LOCAL_MODELS_CLARIFYING_QUESTIONS,
    BUG_FIX_CLARIFYING_QUESTIONS,
    EXPLAIN_WHAT_YOU_DO,
    SIMPLE_CODEBASE_QUESTION,
    SIMPLE_FILE_REQUEST_DRAFTING,
]

__all__ = [
    "LOCAL_MODEL_CASES",
    "SIMPLE_GREETING",
    "LOCAL_MODELS_CLARIFYING_QUESTIONS",
    "BUG_FIX_CLARIFYING_QUESTIONS",
    "EXPLAIN_WHAT_YOU_DO",
    "SIMPLE_CODEBASE_QUESTION",
    "SIMPLE_FILE_REQUEST_DRAFTING",
]
