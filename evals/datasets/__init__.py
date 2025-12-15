"""
Test case datasets for Shotgun agent evaluation.

Datasets are organized by agent type:
    datasets/
    ├── router_agent/     # Router clarifying questions tests
    ├── research_agent/   # Research capability tests (future)
    ├── specify_agent/    # Specification generation tests (future)
    └── ...
"""

from evals.datasets.router_agent import ALL_ROUTER_CASES, CLARIFYING_QUESTIONS_CASES

__all__ = ["CLARIFYING_QUESTIONS_CASES", "ALL_ROUTER_CASES"]
