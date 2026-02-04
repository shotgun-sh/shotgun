"""
Router agent test cases for file_requests behavior.

Tests that the Router uses file_requests to load binary files (PDFs, images)
when a user asks about a specific file path, instead of:
1. Asking clarifying questions
2. Reading existing .shotgun/ research files about the file
3. Claiming it cannot access the file

The Router should IMMEDIATELY use file_requests for any binary file path.
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

# Test: Router should use file_requests for PDFs, not ask clarifying questions
PDF_FILE_REQUEST_NO_QUESTIONS = ShotgunTestCase(
    name="pdf_file_request_no_questions",
    inputs=TestCaseInput(
        prompt="what's in tmp/example_pdf.pdf",
        agent_type=AgentType.ROUTER,
        context=TestCaseContext(
            has_codebase_indexed=False,
            router_mode=RouterMode.DRAFTING,  # Drafting mode - delegation tools available
        ),
    ),
    expected=ExpectedAgentOutput(
        judge_type=JudgeType.FILE_REQUESTS,
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
            router_mode=RouterMode.DRAFTING,
        ),
    ),
    expected=ExpectedAgentOutput(
        judge_type=JudgeType.FILE_REQUESTS,
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

# Test: Router should NOT claim inability to access files
# This captures the failure where Router says "I can't tell you what's in the PDF"
# instead of just using file_requests to load it
PDF_DIRECT_ACCESS_NO_EXCUSES = ShotgunTestCase(
    name="pdf_direct_access_no_excuses",
    inputs=TestCaseInput(
        prompt="Tell me exactly whats in tmp/example_pdf.pdf",
        agent_type=AgentType.ROUTER,
        context=TestCaseContext(
            has_codebase_indexed=False,
            router_mode=RouterMode.DRAFTING,
        ),
    ),
    expected=ExpectedAgentOutput(
        judge_type=JudgeType.FILE_REQUESTS,
        max_clarifying_questions=0,
        disallowed_delegations=["research", "specification", "plan", "tasks", "export"],
        # Response should NOT contain inability claims
        response_not_contains=[
            "can't tell you",
            "cannot tell you",
            "can't access",
            "cannot access",
            "don't have access",
            "no tool",
            "unable to",
            "I need access",
            "need the file",
            "cannot extract",
            "can't extract",
            "I would need",
        ],
        # Disallow using read_file tool (Router should use file_requests, not read research files)
        disallowed_tools=["read_file"],
        expected_response="Router should immediately use file_requests without excuses or reading .shotgun files",
    ),
)

# Test: Router should NOT read .shotgun research files when asked about a specific binary file
# This captures the bug where Router reads research/pdf-inspection-request-*.md instead of file_requests
PDF_NO_RESEARCH_FILE_READ = ShotgunTestCase(
    name="pdf_no_research_file_read",
    inputs=TestCaseInput(
        prompt="what's in tmp/example_pdf.pdf",
        agent_type=AgentType.ROUTER,
        context=TestCaseContext(
            has_codebase_indexed=False,
            router_mode=RouterMode.DRAFTING,
        ),
    ),
    expected=ExpectedAgentOutput(
        judge_type=JudgeType.FILE_REQUESTS,
        max_clarifying_questions=0,
        disallowed_delegations=["research", "specification", "plan", "tasks", "export"],
        # Disallow read_file - for binary files, use file_requests directly
        disallowed_tools=["read_file"],
        response_not_contains=[
            "prior",
            "previous",
            "existing research",
            "inspection notes",
            "metadata-only",
        ],
        expected_response="Router should use file_requests directly, not read existing .shotgun/ research files",
    ),
)


# Test: Router should use file_requests for multiple PDFs in .shotgun directory
# This captures the bug where Router tries to read .shotgun/user_stories/*.pdf files
# using read_file (text tool) instead of file_requests (binary files)
SHOTGUN_MULTIPLE_PDFS_FILE_REQUEST = ShotgunTestCase(
    name="shotgun_multiple_pdfs_file_request",
    inputs=TestCaseInput(
        prompt="take a look at the user stories in .shotgun/user_stories/ - there are two PDFs there",
        agent_type=AgentType.ROUTER,
        context=TestCaseContext(
            has_codebase_indexed=False,
            router_mode=RouterMode.DRAFTING,
        ),
    ),
    expected=ExpectedAgentOutput(
        judge_type=JudgeType.FILE_REQUESTS,
        max_clarifying_questions=0,
        disallowed_delegations=["research", "specification", "plan", "tasks", "export"],
        # Should NOT use read_file on PDF files (will fail with UTF-8 error)
        # Router should use file_requests instead
        disallowed_tools=["read_file"],
        response_not_contains=[
            "can't read",
            "cannot read",
            "binary file",  # Should not expose internal error to user
            "UTF-8",
            "codec",
            "decode",
        ],
        # LLM Judge evaluation criteria:
        expected_response=(
            "The Router should immediately use file_requests to load the PDF files. "
            "The response should indicate it will check/load the files and the file_requests "
            "field should contain paths to both PDF files (e.g., '.shotgun/user_stories/story1.pdf'). "
            "The Router should NOT ask clarifying questions, should NOT claim inability to access files, "
            "and should NOT use the read_file tool which only works for text files."
        ),
    ),
)


# Export all test cases
FILE_REQUEST_CASES: list[ShotgunTestCase] = [
    PDF_FILE_REQUEST_NO_QUESTIONS,
    IMAGE_FILE_REQUEST_NO_QUESTIONS,
    PDF_DIRECT_ACCESS_NO_EXCUSES,
    PDF_NO_RESEARCH_FILE_READ,
    SHOTGUN_MULTIPLE_PDFS_FILE_REQUEST,
]
