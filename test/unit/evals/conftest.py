"""Test configuration for evals package tests.

Adds the evals package to sys.path since it's not part of the installed package.
"""

import sys
from pathlib import Path

# Add the repo root to sys.path so 'evals' package can be imported
repo_root = Path(__file__).parent.parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))
