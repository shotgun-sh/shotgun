"""
Router agent test cases for file_requests behavior.

Tests that the Router uses file_requests to load binary files (PDFs, images)
when a user asks about a specific file path, instead of asking clarifying questions.
"""

from evals.models import (
    AgentType,
    ExpectedAgentOutput,
    ShotgunTestCase,
    TestCaseContext,
    TestCaseInput,
)

# Test: Router should use file_requests for PDFs, not ask clarifying questions
PDF_FILE_REQUEST_NO_QUESTIONS = ShotgunTestCase(
    name="pdf_file_request_no_questions",
    inputs=TestCaseInput(
        prompt="what's in tmp/example_pdf.pdf",
        agent_type=AgentType.ROUTER,
        context=TestCaseContext(
            has_codebase_indexed=False,
            router_mode="drafting",  # Drafting mode - delegation tools available
        ),
    ),
    expected=ExpectedAgentOutput(
        # Should NOT ask clarifying questions
        max_clarifying_questions=0,
        # Should NOT delegate to any sub-agent (first turn: just use file_requests)
        disallowed_delegations=["research", "specification", "plan", "tasks", "export"],
        # Response should NOT contain question patterns
        response_not_contains=[
            "Before I",
            "few questions",
            "clarify",
            "Could you",
            "Would you",
            "Is this file",
            "What specifically",
        ],
        # Expected response describes the action being taken
        expected_response="Router should use file_requests to load the PDF, not ask questions about it",
    ),
)

# Test: Router should use file_requests for images
IMAGE_FILE_REQUEST_NO_QUESTIONS = ShotgunTestCase(
    name="image_file_request_no_questions",
    inputs=TestCaseInput(
        prompt="describe the wireframe in designs/mockup.png",
        agent_type=AgentType.ROUTER,
        context=TestCaseContext(
            has_codebase_indexed=False,
            router_mode="drafting",
        ),
    ),
    expected=ExpectedAgentOutput(
        max_clarifying_questions=0,
        disallowed_delegations=["research", "specification", "plan", "tasks", "export"],
        response_not_contains=[
            "Before I",
            "few questions",
            "clarify",
            "Could you tell me",
            "What kind of",
        ],
        expected_response="Router should use file_requests to load the image, not ask questions",
    ),
)

# Export all test cases
FILE_REQUEST_CASES: list[ShotgunTestCase] = [
    PDF_FILE_REQUEST_NO_QUESTIONS,
    IMAGE_FILE_REQUEST_NO_QUESTIONS,
]
