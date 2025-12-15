"""
Router agent test case datasets.

Contains test cases for evaluating Router agent clarifying questions behavior.

Test cases:
- vague_prompt_clarifying_questions: Tests that Router asks clarifying questions for vague prompts

Exports:
- CLARIFYING_QUESTIONS_CASES: List of clarifying questions test cases
- ALL_ROUTER_CASES: Dict mapping test case names to test case objects
"""

from evals.datasets.router_agent.clarifying_questions_cases import (
    CLARIFYING_QUESTIONS_CASES,
    VAGUE_PROMPT_CLARIFYING_QUESTIONS,
)

# Index of all Router test cases by name for discovery
ALL_ROUTER_CASES = {case.name: case for case in CLARIFYING_QUESTIONS_CASES}

__all__ = [
    # Collections
    "CLARIFYING_QUESTIONS_CASES",
    "ALL_ROUTER_CASES",
    # Individual test cases
    "VAGUE_PROMPT_CLARIFYING_QUESTIONS",
]
