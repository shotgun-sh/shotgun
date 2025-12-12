"""
Router agent test case datasets.

Contains test cases for evaluating Router agent:
- Delegation correctness (selecting appropriate sub-agent)
- Plan creation quality
- Multi-step workflow coordination
- Error handling for edge cases

Exports:
- DELEGATION_CASES: List of all test cases
- ALL_ROUTER_CASES: Dict mapping test case names to test case objects
"""

from evals.datasets.router_agent.delegation_cases import (
    # Plan Creation cases
    CREATE_PLAN_BASIC,
    CREATE_PLAN_COMPLEX,
    CREATE_PLAN_WITH_RESEARCH,
    # Direct Delegation cases
    DELEGATE_TO_EXPORT,
    DELEGATE_TO_RESEARCH_BASIC,
    DELEGATE_TO_RESEARCH_WEB_SEARCH,
    DELEGATE_TO_SPECIFY,
    DELEGATE_TO_TASKS,
    # List of all cases
    DELEGATION_CASES,
    # Error Handling cases
    HANDLE_AMBIGUOUS_REQUEST,
    HANDLE_OUT_OF_SCOPE,
    # Multi-Step Workflow cases
    WORKFLOW_FULL_PIPELINE,
    WORKFLOW_RESEARCH_TO_SPECIFY,
)

# Index of all Router test cases by name for discovery
ALL_ROUTER_CASES = {case.name: case for case in DELEGATION_CASES}

__all__ = [
    # Collections
    "DELEGATION_CASES",
    "ALL_ROUTER_CASES",
    # Direct Delegation cases
    "DELEGATE_TO_RESEARCH_BASIC",
    "DELEGATE_TO_RESEARCH_WEB_SEARCH",
    "DELEGATE_TO_SPECIFY",
    "DELEGATE_TO_TASKS",
    "DELEGATE_TO_EXPORT",
    # Plan Creation cases
    "CREATE_PLAN_BASIC",
    "CREATE_PLAN_COMPLEX",
    "CREATE_PLAN_WITH_RESEARCH",
    # Multi-Step Workflow cases
    "WORKFLOW_RESEARCH_TO_SPECIFY",
    "WORKFLOW_FULL_PIPELINE",
    # Error Handling cases
    "HANDLE_AMBIGUOUS_REQUEST",
    "HANDLE_OUT_OF_SCOPE",
]
