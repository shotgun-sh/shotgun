"""
Router agent test case datasets.

Contains test cases for evaluating Router agent behavior.

Test case categories:
- Clarifying questions: Tests Router asks questions for vague/ambiguous prompts
- Planning: Tests Router creates appropriate plans for feature requests
- Research planning: Tests Router plans research-first when adding features to codebase
- Delegation routing: Tests Router correctly delegates to each agent for their files
- File write: Tests Router delegates to sub-agents which write files (not output to chat)
- File requests: Tests Router uses file_requests for binary files instead of asking questions

Exports:
- CLARIFYING_QUESTIONS_CASES: List of clarifying questions test cases
- PLANNING_CASES: List of planning behavior test cases
- RESEARCH_PLANNING_CASES: List of research-first planning test cases
- DELEGATION_ROUTING_CASES: List of delegation routing test cases
- FILE_WRITE_CASES: List of file write verification test cases
- FILE_REQUEST_CASES: List of file_requests behavior test cases
- ALL_ROUTER_CASES: Dict mapping test case names to test case objects
"""

from evals.datasets.router_agent.clarifying_questions_cases import (
    CACHE_REQUEST_ASKS_QUESTIONS,
    CLARIFYING_QUESTIONS_CASES,
    OPEN_SOURCE_MODELS_ASKS_QUESTIONS,
    PERFORMANCE_REQUEST_ASKS_QUESTIONS,
    VAGUE_PROMPT_CLARIFYING_QUESTIONS,
)
from evals.datasets.router_agent.delegation_routing_cases import (
    DELEGATION_ROUTING_CASES,
    MULTI_FILE_UPDATE_DELEGATES_SEPARATELY,
)
from evals.datasets.router_agent.file_request_cases import (
    FILE_REQUEST_CASES,
    IMAGE_FILE_REQUEST_NO_QUESTIONS,
    PDF_FILE_REQUEST_NO_QUESTIONS,
)
from evals.datasets.router_agent.file_write_cases import (
    FEATURE_REQUEST_CREATES_PLAN_WITH_FILES,
    FILE_WRITE_CASES,
    SPEC_REQUEST_CREATES_PLAN,
)
from evals.datasets.router_agent.planning_cases import (
    COMPLEX_FEATURE_ASKS_QUESTIONS,
    FEATURE_REQUEST_ASKS_QUESTIONS,
    PLANNING_CASES,
    SPECIFIC_FEATURE_CREATES_PLAN,
)
from evals.datasets.router_agent.research_planning_cases import (
    AUTH_FEATURE_PLANS_RESEARCH_FIRST,
    CACHE_FEATURE_PLANS_RESEARCH_FIRST,
    OLLAMA_FEATURE_PLANS_RESEARCH_FIRST,
    RESEARCH_PLANNING_CASES,
)

# Index of all Router test cases by name for discovery
ALL_ROUTER_CASES = {
    case.name: case
    for case in (
        CLARIFYING_QUESTIONS_CASES
        + PLANNING_CASES
        + RESEARCH_PLANNING_CASES
        + DELEGATION_ROUTING_CASES
        + FILE_WRITE_CASES
        + FILE_REQUEST_CASES
    )
}

__all__ = [
    # Collections
    "CLARIFYING_QUESTIONS_CASES",
    "PLANNING_CASES",
    "RESEARCH_PLANNING_CASES",
    "DELEGATION_ROUTING_CASES",
    "FILE_WRITE_CASES",
    "FILE_REQUEST_CASES",
    "ALL_ROUTER_CASES",
    # Clarifying questions test cases
    "VAGUE_PROMPT_CLARIFYING_QUESTIONS",
    "PERFORMANCE_REQUEST_ASKS_QUESTIONS",
    "CACHE_REQUEST_ASKS_QUESTIONS",
    "OPEN_SOURCE_MODELS_ASKS_QUESTIONS",
    # Planning test cases
    "FEATURE_REQUEST_ASKS_QUESTIONS",
    "COMPLEX_FEATURE_ASKS_QUESTIONS",
    "SPECIFIC_FEATURE_CREATES_PLAN",
    # Research planning test cases
    "OLLAMA_FEATURE_PLANS_RESEARCH_FIRST",
    "AUTH_FEATURE_PLANS_RESEARCH_FIRST",
    "CACHE_FEATURE_PLANS_RESEARCH_FIRST",
    # Delegation routing test cases
    "MULTI_FILE_UPDATE_DELEGATES_SEPARATELY",
    # File write test cases
    "FEATURE_REQUEST_CREATES_PLAN_WITH_FILES",
    "SPEC_REQUEST_CREATES_PLAN",
    # File request test cases
    "PDF_FILE_REQUEST_NO_QUESTIONS",
    "IMAGE_FILE_REQUEST_NO_QUESTIONS",
]
