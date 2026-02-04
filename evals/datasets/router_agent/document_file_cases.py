"""
Router agent test cases for document file handling in both Planning and Drafting modes.

Tests that the Router uses file_requests to load binary document files (PDFs, images)
when a user asks about specific file paths containing:
- PRDs (Product Requirement Documents)
- User stories
- QA guidelines
- Specification documents
- Wireframes and design mockups
- Screenshots for bug reports

The Router should IMMEDIATELY use file_requests for any binary file path,
regardless of whether it's in Planning or Drafting mode.

These test cases rely primarily on the LLM judge (FileRequestsJudge) to evaluate
the quality of the Router's response, rather than deterministic text matching.
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

# All sub-agents that Router should NOT delegate to for direct file access
ALL_DELEGATIONS = ["research", "specification", "plan", "tasks", "export"]


# ============================================================================
# Planning Mode Cases
# Tests Router uses file_requests for documents even when in planning mode
# ============================================================================

PRD_FILE_PLANNING_MODE = ShotgunTestCase(
    name="prd_file_planning_mode",
    inputs=TestCaseInput(
        prompt="I need to understand the requirements in docs/prd.pdf before we start planning",
        agent_type=AgentType.ROUTER,
        context=TestCaseContext(
            has_codebase_indexed=True,
            router_mode=RouterMode.PLANNING,
        ),
    ),
    expected=ExpectedAgentOutput(
        judge_type=JudgeType.FILE_REQUESTS,
        max_clarifying_questions=0,
        disallowed_delegations=ALL_DELEGATIONS,
        disallowed_tools=["read_file"],
        expected_response="""The Router should immediately use file_requests to load the PRD PDF file.
Correct behavior: Set file_requests with the PDF path, provide a brief acknowledgment that it will load and analyze the document.
Incorrect behavior: Asking clarifying questions about the file, claiming inability to access PDFs, or delegating to Research agent.""",
    ),
)

USER_STORIES_FILE_PLANNING_MODE = ShotgunTestCase(
    name="user_stories_file_planning_mode",
    inputs=TestCaseInput(
        prompt="Check the user stories document at requirements/user-stories.pdf",
        agent_type=AgentType.ROUTER,
        context=TestCaseContext(
            has_codebase_indexed=True,
            router_mode=RouterMode.PLANNING,
        ),
    ),
    expected=ExpectedAgentOutput(
        judge_type=JudgeType.FILE_REQUESTS,
        max_clarifying_questions=0,
        disallowed_delegations=ALL_DELEGATIONS,
        disallowed_tools=["read_file"],
        expected_response="""The Router should immediately use file_requests to load the user stories PDF.
Correct behavior: Set file_requests with the PDF path, acknowledge it will review the document.
Incorrect behavior: Asking clarifying questions, claiming inability to access the file, or delegating to Research agent.""",
    ),
)

QA_GUIDELINES_FILE_PLANNING_MODE = ShotgunTestCase(
    name="qa_guidelines_file_planning_mode",
    inputs=TestCaseInput(
        prompt="Review the QA guidelines in docs/qa-checklist.pdf before we plan testing",
        agent_type=AgentType.ROUTER,
        context=TestCaseContext(
            has_codebase_indexed=True,
            router_mode=RouterMode.PLANNING,
        ),
    ),
    expected=ExpectedAgentOutput(
        judge_type=JudgeType.FILE_REQUESTS,
        max_clarifying_questions=0,
        disallowed_delegations=ALL_DELEGATIONS,
        disallowed_tools=["read_file"],
        expected_response="""The Router should immediately use file_requests to load the QA guidelines PDF.
Correct behavior: Set file_requests with the PDF path, acknowledge it will review the QA checklist.
Incorrect behavior: Asking clarifying questions, claiming inability to access the file, or delegating to Research agent.""",
    ),
)

SPEC_DOC_FILE_PLANNING_MODE = ShotgunTestCase(
    name="spec_doc_file_planning_mode",
    inputs=TestCaseInput(
        prompt="I uploaded the technical specification at specs/api-spec.pdf - what does it say about authentication?",
        agent_type=AgentType.ROUTER,
        context=TestCaseContext(
            has_codebase_indexed=True,
            router_mode=RouterMode.PLANNING,
        ),
    ),
    expected=ExpectedAgentOutput(
        judge_type=JudgeType.FILE_REQUESTS,
        max_clarifying_questions=0,
        disallowed_delegations=ALL_DELEGATIONS,
        disallowed_tools=["read_file"],
        expected_response="""The Router should immediately use file_requests to load the technical specification PDF.
Correct behavior: Set file_requests with the PDF path, acknowledge it will load the spec to answer the authentication question.
Incorrect behavior: Asking clarifying questions, claiming inability to access the file, or delegating to Research agent.""",
    ),
)


# ============================================================================
# Drafting Mode Cases
# Tests Router uses file_requests for documents in drafting mode
# ============================================================================

PRD_FILE_DRAFTING_MODE = ShotgunTestCase(
    name="prd_file_drafting_mode",
    inputs=TestCaseInput(
        prompt="Look at the PRD in docs/product-requirements.pdf and tell me the main features",
        agent_type=AgentType.ROUTER,
        context=TestCaseContext(
            has_codebase_indexed=False,
            router_mode=RouterMode.DRAFTING,
        ),
    ),
    expected=ExpectedAgentOutput(
        judge_type=JudgeType.FILE_REQUESTS,
        max_clarifying_questions=0,
        disallowed_delegations=ALL_DELEGATIONS,
        disallowed_tools=["read_file"],
        expected_response="""The Router should immediately use file_requests to load the PRD PDF file.
Correct behavior: Set file_requests with the PDF path, acknowledge it will load and identify the main features.
Incorrect behavior: Asking clarifying questions, claiming inability to access PDFs, or delegating to Research agent.""",
    ),
)

USER_STORIES_FILE_DRAFTING_MODE = ShotgunTestCase(
    name="user_stories_file_drafting_mode",
    inputs=TestCaseInput(
        prompt="Summarize the user stories from attachments/stories.pdf",
        agent_type=AgentType.ROUTER,
        context=TestCaseContext(
            has_codebase_indexed=False,
            router_mode=RouterMode.DRAFTING,
        ),
    ),
    expected=ExpectedAgentOutput(
        judge_type=JudgeType.FILE_REQUESTS,
        max_clarifying_questions=0,
        disallowed_delegations=ALL_DELEGATIONS,
        disallowed_tools=["read_file"],
        expected_response="""The Router should immediately use file_requests to load the user stories PDF.
Correct behavior: Set file_requests with the PDF path, acknowledge it will load and summarize the stories.
Incorrect behavior: Asking clarifying questions, claiming inability to access the file, or delegating to Research agent.""",
    ),
)

WIREFRAME_IMAGE_DRAFTING_MODE = ShotgunTestCase(
    name="wireframe_image_drafting_mode",
    inputs=TestCaseInput(
        prompt="Describe the wireframe in designs/dashboard-wireframe.png",
        agent_type=AgentType.ROUTER,
        context=TestCaseContext(
            has_codebase_indexed=False,
            router_mode=RouterMode.DRAFTING,
        ),
    ),
    expected=ExpectedAgentOutput(
        judge_type=JudgeType.FILE_REQUESTS,
        max_clarifying_questions=0,
        disallowed_delegations=ALL_DELEGATIONS,
        disallowed_tools=["read_file"],
        expected_response="""The Router should immediately use file_requests to load the wireframe image.
Correct behavior: Set file_requests with the image path, acknowledge it will load and describe the wireframe.
Incorrect behavior: Asking clarifying questions, claiming inability to view images, or delegating to Research agent.""",
    ),
)

SCREENSHOT_FOR_BUG_REPORT = ShotgunTestCase(
    name="screenshot_for_bug_report",
    inputs=TestCaseInput(
        prompt="Here's a screenshot of the bug: screenshots/error-state.png - what's happening here?",
        agent_type=AgentType.ROUTER,
        context=TestCaseContext(
            has_codebase_indexed=False,
            router_mode=RouterMode.DRAFTING,
        ),
    ),
    expected=ExpectedAgentOutput(
        judge_type=JudgeType.FILE_REQUESTS,
        max_clarifying_questions=0,
        disallowed_delegations=ALL_DELEGATIONS,
        disallowed_tools=["read_file"],
        expected_response="""The Router should immediately use file_requests to load the screenshot image.
Correct behavior: Set file_requests with the image path, acknowledge it will load and analyze the bug shown.
Incorrect behavior: Asking clarifying questions, claiming inability to view images, or delegating to Research agent.""",
    ),
)


# Export all test cases
DOCUMENT_FILE_CASES: list[ShotgunTestCase] = [
    # Planning mode cases
    PRD_FILE_PLANNING_MODE,
    USER_STORIES_FILE_PLANNING_MODE,
    QA_GUIDELINES_FILE_PLANNING_MODE,
    SPEC_DOC_FILE_PLANNING_MODE,
    # Drafting mode cases
    PRD_FILE_DRAFTING_MODE,
    USER_STORIES_FILE_DRAFTING_MODE,
    WIREFRAME_IMAGE_DRAFTING_MODE,
    SCREENSHOT_FOR_BUG_REPORT,
]
