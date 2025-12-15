"""
Evaluation suites for Shotgun agents.

Organized by agent type:
- router_suites: Router delegation and workflow test suites
"""

from evals.suites.router_suites import ROUTER_SUITES, router_core, router_smoke

__all__ = [
    "ROUTER_SUITES",
    "router_smoke",
    "router_core",
]
