"""Integration tests for retrieve_code codebase tool."""

import pytest
from pydantic_ai import RunContext

from shotgun.agents.models import AgentDeps
from shotgun.agents.tools.codebase import retrieve_code
from shotgun.codebase.models import CodebaseGraph


@pytest.mark.integration
@pytest.mark.asyncio
async def test_retrieve_code_class_success(
    indexed_graph: CodebaseGraph,
    run_context: RunContext[AgentDeps],
):
    """Test retrieving code for a known class."""
    result = await retrieve_code(
        ctx=run_context,
        graph_id=indexed_graph.graph_id,
        qualified_name="Integration Test Graph.calculator.Calculator",
    )

    # Should succeed
    assert result.found is True
    assert result.qualified_name == "Integration Test Graph.calculator.Calculator"
    assert result.source_code is not None
    assert len(result.source_code) > 0

    # Should contain class definition and some methods
    assert "class Calculator" in result.source_code
    assert "def __init__" in result.source_code
    assert "def add" in result.source_code

    # Should have file information
    assert result.file_path is not None
    assert result.file_path.endswith("calculator.py")
    assert result.line_start is not None
    assert result.line_end is not None
    assert result.line_start > 0
    assert result.line_end > result.line_start

    # Test string representation
    result_str = str(result)
    assert isinstance(result_str, str)
    assert "Calculator" in result_str
    assert "def add" in result_str


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skip(reason="Will come back to this later")
async def test_retrieve_code_function_success(
    indexed_graph: CodebaseGraph,
    run_context: RunContext[AgentDeps],
):
    """Test retrieving code for a known function."""
    result = await retrieve_code(
        ctx=run_context,
        graph_id=indexed_graph.graph_id,
        qualified_name="Integration Test Graph.calculator.calculate_factorial",
    )

    # Should succeed
    assert result.found is True
    assert (
        result.qualified_name == "Integration Test Graph.calculator.calculate_factorial"
    )
    assert result.source_code is not None

    # Should contain function definition
    assert "def calculate_factorial" in result.source_code
    assert "factorial" in result.source_code.lower()

    # Should have file information
    assert result.file_path is not None
    assert result.file_path.endswith("calculator.py")
    assert result.line_start is not None
    assert result.line_end is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_retrieve_code_method_success(
    indexed_graph: CodebaseGraph,
    run_context: RunContext[AgentDeps],
):
    """Test retrieving code for a method within a class."""
    result = await retrieve_code(
        ctx=run_context,
        graph_id=indexed_graph.graph_id,
        qualified_name="Integration Test Graph.calculator.Calculator.add",
    )

    # Should succeed
    assert result.found is True
    assert result.qualified_name == "Integration Test Graph.calculator.Calculator.add"
    assert result.source_code is not None

    # Should contain method definition
    assert "def add" in result.source_code
    assert "Add two numbers" in result.source_code

    # Should have file and line information
    assert result.file_path is not None
    assert result.line_start is not None
    assert result.line_end is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_retrieve_code_inherited_class(
    indexed_graph: CodebaseGraph,
    run_context: RunContext[AgentDeps],
):
    """Test retrieving code for an inherited class."""
    result = await retrieve_code(
        ctx=run_context,
        graph_id=indexed_graph.graph_id,
        qualified_name="Integration Test Graph.calculator.ScientificCalculator",
    )

    # Should succeed
    assert result.found is True
    assert (
        result.qualified_name
        == "Integration Test Graph.calculator.ScientificCalculator"
    )
    assert result.source_code is not None

    # Should contain class definition and inheritance
    assert "class ScientificCalculator" in result.source_code
    assert "Calculator" in result.source_code  # inheritance
    assert "def power" in result.source_code or "def square_root" in result.source_code


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skip(reason="Will come back to this later")
async def test_retrieve_code_utility_function(
    indexed_graph: CodebaseGraph,
    run_context: RunContext[AgentDeps],
):
    """Test retrieving code for utility functions in subdirectories."""
    result = await retrieve_code(
        ctx=run_context,
        graph_id=indexed_graph.graph_id,
        qualified_name="Integration Test Graph.utils.helpers.format_number",
    )

    # Should succeed
    assert result.found is True
    assert result.qualified_name == "Integration Test Graph.utils.helpers.format_number"
    assert result.source_code is not None

    # Should contain function definition
    assert "def format_number" in result.source_code
    assert "decimal places" in result.source_code

    # Should have file information pointing to utils directory
    assert result.file_path is not None
    assert "utils" in result.file_path
    assert "helpers.py" in result.file_path


@pytest.mark.integration
@pytest.mark.asyncio
async def test_retrieve_code_class_in_subdirectory(
    indexed_graph: CodebaseGraph,
    run_context: RunContext[AgentDeps],
):
    """Test retrieving code for a class in a subdirectory."""
    result = await retrieve_code(
        ctx=run_context,
        graph_id=indexed_graph.graph_id,
        qualified_name="Integration Test Graph.utils.helpers.InputValidator",
    )

    # Should succeed
    assert result.found is True
    assert (
        result.qualified_name == "Integration Test Graph.utils.helpers.InputValidator"
    )
    assert result.source_code is not None

    # Should contain class definition and methods
    assert "class InputValidator" in result.source_code
    assert "is_numeric" in result.source_code
    assert "validate_range" in result.source_code


@pytest.mark.integration
@pytest.mark.asyncio
async def test_retrieve_code_nonexistent_entity(
    indexed_graph: CodebaseGraph,
    run_context: RunContext[AgentDeps],
):
    """Test retrieving code for a non-existent entity."""
    result = await retrieve_code(
        ctx=run_context,
        graph_id=indexed_graph.graph_id,
        qualified_name="NonExistentClass",
    )

    # Should fail gracefully
    assert result.found is False
    assert result.qualified_name == "NonExistentClass"
    assert result.source_code is None
    assert result.error is not None
    assert "not found" in result.error.lower()

    # String representation should show error
    result_str = str(result)
    assert "Not Found" in result_str
    assert "NonExistentClass" in result_str


@pytest.mark.integration
@pytest.mark.asyncio
async def test_retrieve_code_invalid_graph_id(
    run_context: RunContext[AgentDeps],
):
    """Test retrieving code with invalid graph ID."""
    result = await retrieve_code(
        ctx=run_context,
        graph_id="nonexistent-graph-id",
        qualified_name="Integration Test Graph.calculator.Calculator",
    )

    # Should fail gracefully
    assert result.found is False
    assert result.qualified_name == "Integration Test Graph.calculator.Calculator"
    assert result.source_code is None
    assert result.error is not None
    assert "graph" in result.error.lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_retrieve_code_no_codebase_service(
    indexed_graph: CodebaseGraph,
):
    """Test retrieving code when no codebase service is available."""

    # Create run context without codebase service
    class MockRunContextNoService:
        def __init__(self):
            self.deps = type("MockDeps", (), {"codebase_service": None})()

    context = MockRunContextNoService()

    result = await retrieve_code(
        ctx=context,
        graph_id=indexed_graph.graph_id,
        qualified_name="Integration Test Graph.calculator.Calculator",
    )

    # Should fail gracefully
    assert result.found is False
    assert result.error is not None
    assert "codebase service" in result.error.lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_retrieve_code_malformed_qualified_name(
    indexed_graph: CodebaseGraph,
    run_context: RunContext[AgentDeps],
):
    """Test retrieving code with malformed qualified names."""
    test_cases = [
        "",  # Empty name
        ".",  # Just dot
        "..invalid",  # Double dot
        "Class.",  # Ending with dot
    ]

    for qualified_name in test_cases:
        result = await retrieve_code(
            ctx=run_context,
            graph_id=indexed_graph.graph_id,
            qualified_name=qualified_name,
        )

        # Should fail gracefully
        assert result.found is False
        assert result.qualified_name == qualified_name
        assert result.source_code is None
        assert result.error is not None


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skip(reason="Will come back to this later")
async def test_retrieve_code_string_representation_success(
    indexed_graph: CodebaseGraph,
    run_context: RunContext[AgentDeps],
):
    """Test string representation of successful code retrieval."""
    result = await retrieve_code(
        ctx=run_context,
        graph_id=indexed_graph.graph_id,
        qualified_name="Integration Test Graph.calculator.Calculator",
    )

    assert result.found is True

    result_str = str(result)
    assert isinstance(result_str, str)
    assert len(result_str) > 0

    # Should contain key information
    assert "Calculator" in result_str
    assert "calculator.py" in result_str
    assert "class Calculator" in result_str

    # Should show line numbers
    assert f"Line {result.line_start}" in result_str

    # Should not show raw field names
    assert "qualified_name:" not in result_str
    assert "file_path:" not in result_str


@pytest.mark.integration
@pytest.mark.asyncio
async def test_retrieve_code_string_representation_failure(
    indexed_graph: CodebaseGraph,
    run_context: RunContext[AgentDeps],
):
    """Test string representation of failed code retrieval."""
    result = await retrieve_code(
        ctx=run_context,
        graph_id=indexed_graph.graph_id,
        qualified_name="NonExistentClass",
    )

    assert result.found is False

    result_str = str(result)
    assert isinstance(result_str, str)
    assert len(result_str) > 0

    # Should show error message
    assert "Not Found" in result_str
    assert "NonExistentClass" in result_str
    assert "query_graph" in result_str  # Should suggest using query_graph
