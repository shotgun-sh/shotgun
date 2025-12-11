"""
Test case datasets for Shotgun agent evaluation.

Datasets are organized by agent type:
    datasets/
    ├── router_agent/     # Router delegation and plan creation tests
    ├── research_agent/   # Research capability tests (future)
    ├── specify_agent/    # Specification generation tests (future)
    └── ...
"""

from evals.datasets.router_agent import DELEGATION_CASES

__all__ = ["DELEGATION_CASES"]
