"""
Router agent test case datasets.

Contains test cases for evaluating Router agent:
- Delegation correctness (selecting appropriate sub-agent)
- Plan creation quality
- Multi-step workflow coordination
- Error handling for edge cases
"""

from evals.datasets.router_agent.delegation_cases import DELEGATION_CASES

__all__ = ["DELEGATION_CASES"]
