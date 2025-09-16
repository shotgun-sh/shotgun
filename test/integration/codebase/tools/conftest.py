"""Configuration and shared fixtures for codebase tools integration tests."""

import asyncio
from pathlib import Path

import pytest
import pytest_asyncio
from pydantic_ai import Agent, RunContext

from shotgun.agents.config.models import CLAUDE_3_5_SONNET
from shotgun.agents.models import AgentDeps, AgentRuntimeOptions
from shotgun.agents.tools.codebase import (
    codebase_shell,
    directory_lister,
    file_read,
    query_graph,
    retrieve_code,
)
from shotgun.codebase import CodebaseService
from shotgun.codebase.models import CodebaseGraph, GraphStatus


@pytest_asyncio.fixture
async def codebase_service(temp_storage_dir: Path) -> CodebaseService:
    """Create a CodebaseService instance with temporary storage."""
    return CodebaseService(temp_storage_dir / "codebase_service")


@pytest.fixture
def test_codebase(temp_storage_dir: Path) -> Path:
    """Create a test codebase with multiple files for integration testing."""
    codebase_dir = temp_storage_dir / "test_codebase"
    codebase_dir.mkdir()

    # Create main module
    (codebase_dir / "main.py").write_text('''"""Main module for the test codebase."""

def main():
    """Main entry point."""
    calculator = Calculator()
    result = calculator.add(5, 3)
    print(f"Result: {result}")

if __name__ == "__main__":
    main()
''')

    # Create calculator module with classes and functions
    (
        codebase_dir / "calculator.py"
    ).write_text('''"""Calculator module with basic arithmetic operations."""

class Calculator:
    """A simple calculator class for basic math operations."""

    def __init__(self, precision=2):
        """Initialize calculator with precision setting."""
        self.precision = precision
        self.history = []

    def add(self, a, b):
        """Add two numbers together."""
        result = a + b
        self._record_operation(f"{a} + {b} = {result}")
        return round(result, self.precision)

    def subtract(self, a, b):
        """Subtract b from a."""
        result = a - b
        self._record_operation(f"{a} - {b} = {result}")
        return round(result, self.precision)

    def multiply(self, a, b):
        """Multiply two numbers."""
        result = a * b
        self._record_operation(f"{a} * {b} = {result}")
        return round(result, self.precision)

    def _record_operation(self, operation):
        """Private method to record operations in history."""
        self.history.append(operation)

    def get_history(self):
        """Get calculation history."""
        return self.history.copy()


class ScientificCalculator(Calculator):
    """Extended calculator with scientific functions."""

    def power(self, base, exponent):
        """Calculate base raised to the power of exponent."""
        result = base ** exponent
        self._record_operation(f"{base} ^ {exponent} = {result}")
        return round(result, self.precision)

    def square_root(self, number):
        """Calculate square root of a number."""
        import math
        result = math.sqrt(number)
        self._record_operation(f"√{number} = {result}")
        return round(result, self.precision)


def calculate_factorial(n):
    """Calculate factorial of n."""
    if n <= 1:
        return 1
    return n * calculate_factorial(n - 1)


def is_prime(n):
    """Check if a number is prime."""
    if n < 2:
        return False
    for i in range(2, int(n ** 0.5) + 1):
        if n % i == 0:
            return False
    return True
''')

    # Create utilities subdirectory
    utils_dir = codebase_dir / "utils"
    utils_dir.mkdir()

    (utils_dir / "__init__.py").write_text("")

    (utils_dir / "helpers.py").write_text('''"""Utility helper functions."""

def format_number(number, decimals=2):
    """Format a number with specified decimal places."""
    return f"{number:.{decimals}f}"


def validate_input(value):
    """Validate numeric input."""
    try:
        return float(value)
    except ValueError:
        raise ValueError(f"Invalid numeric input: {value}")


class InputValidator:
    """Class for input validation operations."""

    @staticmethod
    def is_numeric(value):
        """Check if value is numeric."""
        try:
            float(value)
            return True
        except ValueError:
            return False

    @classmethod
    def validate_range(cls, value, min_val, max_val):
        """Validate that value is within range."""
        if not cls.is_numeric(value):
            return False
        num_val = float(value)
        return min_val <= num_val <= max_val
''')

    # Create config file
    (codebase_dir / "config.py").write_text('''"""Configuration settings."""

DEFAULT_PRECISION = 2
MAX_HISTORY_SIZE = 100
SUPPORTED_OPERATIONS = ["add", "subtract", "multiply", "divide"]

class Config:
    """Configuration class."""

    def __init__(self):
        self.precision = DEFAULT_PRECISION
        self.history_size = MAX_HISTORY_SIZE

    def update(self, **kwargs):
        """Update configuration."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
''')

    # Create README
    (codebase_dir / "README.md").write_text("""# Test Codebase

This is a test codebase for integration testing.

## Features

- Basic calculator operations
- Scientific calculator functions
- Input validation utilities
- Configuration management

## Usage

```python
from calculator import Calculator

calc = Calculator()
result = calc.add(5, 3)
```
""")

    return codebase_dir


@pytest_asyncio.fixture
async def indexed_graph(
    codebase_service: CodebaseService, test_codebase: Path
) -> CodebaseGraph:
    """Create an indexed graph for testing."""
    # Create the graph (graph_id is generated automatically)
    created_graph = await codebase_service.create_graph(
        repo_path=test_codebase, name="Integration Test Graph"
    )

    # Wait for indexing to complete
    while True:
        current_graph = await codebase_service.get_graph(created_graph.graph_id)
        if current_graph.status == GraphStatus.READY:
            break
        await asyncio.sleep(0.1)

    return current_graph


@pytest.fixture
def agent_deps(codebase_service: CodebaseService, temp_storage_dir: Path) -> AgentDeps:
    """Create agent dependencies for testing."""
    runtime_options = AgentRuntimeOptions(
        interactive_mode=False,
        working_directory=temp_storage_dir,
    )

    # Use Claude 3.5 Sonnet for testing (fast and reliable)
    return AgentDeps(
        **runtime_options.model_dump(),
        llm_model=CLAUDE_3_5_SONNET,
        codebase_service=codebase_service,
    )


@pytest_asyncio.fixture
async def test_agent(agent_deps: AgentDeps) -> Agent:
    """Create a test agent with codebase tools registered."""
    agent = Agent(
        model=agent_deps.llm_model.pydantic_model_name,
        deps_type=AgentDeps,
        instrument=False,  # Disable instrumentation for tests
    )

    # Register all codebase tools
    agent.tool_plain(query_graph)
    agent.tool_plain(retrieve_code)
    agent.tool_plain(file_read)
    agent.tool_plain(directory_lister)
    agent.tool_plain(codebase_shell)

    return agent


@pytest.fixture
def run_context(agent_deps: AgentDeps) -> RunContext[AgentDeps]:
    """Create a run context for testing tool calls."""

    # Create a minimal mock RunContext
    class MockRunContext:
        def __init__(self, deps):
            self.deps = deps

    return MockRunContext(agent_deps)
