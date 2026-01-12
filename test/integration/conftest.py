"""Configuration and shared fixtures for integration tests."""

import asyncio
import os
from pathlib import Path

import pytest
import pytest_asyncio

from shotgun.codebase import CodebaseService

# Load environment variables from .env file
try:
    from dotenv import load_dotenv

    # Load from project root (two levels up from test/integration/)
    project_root = Path(__file__).parent.parent.parent
    load_dotenv(project_root / ".env")
except ImportError:
    # python-dotenv not available, skip loading
    pass


def disable_logging():
    """Disable logging during tests to avoid logger issues and noise."""
    import logging

    logging.disable(logging.CRITICAL)


def pytest_configure(config):
    """Configure pytest for integration tests."""
    # Disable logging during tests to avoid issues and noise
    disable_logging()

    # Add custom markers
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration test (requires LLM configuration)",
    )
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "llm: mark test as requiring LLM calls")


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def service(tmp_path: Path) -> CodebaseService:
    """Create a CodebaseService instance with temporary storage."""
    return CodebaseService(tmp_path / "storage")


@pytest.fixture
def simple_python_codebase(tmp_path: Path) -> Path:
    """Create a simple test codebase with basic Python files."""
    codebase_dir = tmp_path / "simple_codebase"
    codebase_dir.mkdir()

    # Create a simple Python file
    (codebase_dir / "example.py").write_text('''"""Simple example module."""

class Example:
    """Example class with methods."""

    def __init__(self, value: int = 0):
        """Initialize with a value."""
        self.value = value

    def get_value(self) -> int:
        """Get the current value."""
        return self.value

    def hello(self) -> str:
        """Return a greeting."""
        return "world"


def test_function() -> bool:
    """A simple test function."""
    return True


def another_function(a: int, b: int) -> int:
    """Another function that adds numbers."""
    return a + b
''')

    return codebase_dir


@pytest.fixture
def calculator_codebase(tmp_path: Path) -> Path:
    """Create a calculator test codebase with multiple files."""
    codebase_dir = tmp_path / "calculator_codebase"
    codebase_dir.mkdir()

    # Create calculator.py
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

    def _record_operation(self, operation):
        """Private method to record operations in history."""
        self.history.append(operation)

    def get_history(self):
        """Get calculation history."""
        return self.history.copy()


class ScientificCalculator(Calculator):
    """Extended calculator with scientific functions."""

    def __init__(self, precision=4):
        """Initialize scientific calculator with higher default precision."""
        super().__init__(precision)
        self.mode = "scientific"

    def power(self, base, exponent):
        """Calculate base to the power of exponent."""
        result = base ** exponent
        self._record_operation(f"{base} ^ {exponent} = {result}")
        return round(result, self.precision)
''')

    # Create utils.py
    (
        codebase_dir / "utils.py"
    ).write_text('''"""Utility functions for mathematical operations."""

def validate_number(value):
    """Validate that a value is a number."""
    if not isinstance(value, (int, float)):
        raise TypeError(f"Expected number, got {type(value)}")
    return True


def test_validation():
    """Test function for number validation."""
    try:
        validate_number(42)
        validate_number(3.14)
        return True
    except TypeError:
        return False


class MathConstants:
    """Class containing mathematical constants."""

    PI = 3.14159
    E = 2.71828

    @classmethod
    def get_constant(cls, name):
        """Get a mathematical constant by name."""
        return getattr(cls, name.upper(), None)
''')

    return codebase_dir


def check_llm_configuration():
    """Check if LLM is properly configured for integration tests."""
    return bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY"))


def pytest_runtest_setup(item):
    """Setup for individual test runs."""
    # Skip tests that require LLM if not configured
    # Exception: tests that explicitly test "without_api_key" scenarios should always run
    if "integration" in item.keywords:
        if "without_api_key" not in item.name and not check_llm_configuration():
            pytest.skip("LLM not configured - skipping integration test")
