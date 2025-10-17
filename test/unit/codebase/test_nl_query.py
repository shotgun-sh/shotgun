"""Unit tests for nl_query module."""

from unittest.mock import Mock, patch

import pytest

from shotgun.codebase.core.cypher_models import (
    CypherGenerationNotPossibleError,
    CypherGenerationResponse,
)
from shotgun.codebase.core.nl_query import generate_cypher
from shotgun.prompts import PromptLoader


def test_graph_schema_template_content():
    """Test that graph schema template contains expected schema information."""
    loader = PromptLoader()
    schema_content = loader.render("codebase/partials/graph_schema.j2")

    assert "# Codebase Graph Schema Definition" in schema_content
    assert "Project:" in schema_content
    assert "Package:" in schema_content
    assert "Module:" in schema_content
    assert "Class:" in schema_content
    assert "Function:" in schema_content
    assert "Method:" in schema_content
    assert "Relationships" in schema_content
    assert "CONTAINS_PACKAGE" in schema_content
    assert "DEFINES" in schema_content
    assert "INHERITS" in schema_content
    assert "CALLS" in schema_content


def test_graph_schema_includes_file_extensions():
    """Test that schema includes file extension information."""
    loader = PromptLoader()
    schema_content = loader.render("codebase/partials/graph_schema.j2")

    assert "extension includes the dot" in schema_content
    assert '".ts"' in schema_content
    assert '".py"' in schema_content
    assert '".js"' in schema_content


def test_graph_schema_includes_qualified_names():
    """Test that schema includes qualified name information."""
    loader = PromptLoader()
    schema_content = loader.render("codebase/partials/graph_schema.j2")

    assert "qualified_name: string" in schema_content


def test_graph_schema_includes_line_numbers():
    """Test that schema includes line number information."""
    loader = PromptLoader()
    schema_content = loader.render("codebase/partials/graph_schema.j2")

    assert "line_start: int" in schema_content
    assert "line_end: int" in schema_content


@pytest.mark.asyncio
async def test_generate_cypher_simple_query():
    """Test generating Cypher from simple natural language query."""
    nl_query = "Show me all functions in the codebase"
    expected_cypher = "MATCH (n:Function) RETURN n.name, n.qualified_name"

    # Mock the structured response
    mock_response = CypherGenerationResponse(
        cypher_query=expected_cypher,
        can_generate_valid_cypher=True,
        reason_cannot_generate=None,
    )

    with (
        patch("shotgun.codebase.core.nl_query.llm_cypher_prompt") as mock_llm_prompt,
        patch("shotgun.codebase.core.nl_query.get_provider_model") as mock_get_model,
    ):
        mock_model = Mock()
        mock_model.model_instance = "test-model"
        mock_get_model.return_value = mock_model
        mock_llm_prompt.return_value = mock_response

        result = await generate_cypher(nl_query)

        # The function adds cleanup and semicolon
        expected_cleaned = expected_cypher + ";"
        assert result == expected_cleaned
        mock_llm_prompt.assert_called_once()


@pytest.mark.asyncio
async def test_generate_cypher_complex_query():
    """Test generating Cypher from complex natural language query."""
    nl_query = "Find all classes that inherit from BaseClass and show their methods"
    expected_cypher = """
    MATCH (parent:Class {name: 'BaseClass'})<-[:INHERITS]-(child:Class)
    MATCH (child)-[:DEFINES_METHOD]->(method:Method)
    RETURN child.name, method.name
    """

    # Mock the structured response
    mock_response = CypherGenerationResponse(
        cypher_query=expected_cypher.strip(),
        can_generate_valid_cypher=True,
        reason_cannot_generate=None,
    )

    with (
        patch("shotgun.codebase.core.nl_query.llm_cypher_prompt") as mock_llm_prompt,
        patch("shotgun.codebase.core.nl_query.get_provider_model") as mock_get_model,
    ):
        mock_model = Mock()
        mock_model.model_instance = "test-model"
        mock_get_model.return_value = mock_model
        mock_llm_prompt.return_value = mock_response

        result = await generate_cypher(nl_query)

        assert "INHERITS" in result
        assert "DEFINES_METHOD" in result
        assert "BaseClass" in result


@pytest.mark.asyncio
async def test_generate_cypher_conceptual_query_raises_exception():
    """Test that conceptual queries raise CypherGenerationNotPossibleError."""
    nl_query = "What is the main purpose of this codebase?"

    # Mock response indicating the query cannot be converted
    mock_response = CypherGenerationResponse(
        cypher_query=None,
        can_generate_valid_cypher=False,
        reason_cannot_generate="This is a conceptual question requiring interpretation",
    )

    with (
        patch("shotgun.codebase.core.nl_query.llm_cypher_prompt") as mock_llm_prompt,
        patch("shotgun.codebase.core.nl_query.get_provider_model") as mock_get_model,
    ):
        mock_model = Mock()
        mock_model.model_instance = "test-model"
        mock_get_model.return_value = mock_model
        mock_llm_prompt.return_value = mock_response

        with pytest.raises(CypherGenerationNotPossibleError) as exc_info:
            await generate_cypher(nl_query)

        assert "conceptual question" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_generate_cypher_with_file_extension_query():
    """Test generating Cypher query involving file extensions."""
    nl_query = "Show all Python functions"
    expected_cypher = """
    MATCH (file:File)-[:CONTAINS_MODULE]->(module:Module)-[:DEFINES]->(func:Function)
    WHERE file.extension = '.py'
    RETURN func.name, func.qualified_name
    """

    # Mock the structured response
    mock_response = CypherGenerationResponse(
        cypher_query=expected_cypher.strip(),
        can_generate_valid_cypher=True,
        reason_cannot_generate=None,
    )

    with (
        patch("shotgun.codebase.core.nl_query.llm_cypher_prompt") as mock_llm_prompt,
        patch("shotgun.codebase.core.nl_query.get_provider_model") as mock_get_model,
    ):
        mock_model = Mock()
        mock_model.model_instance = "test-model"
        mock_get_model.return_value = mock_model
        mock_llm_prompt.return_value = mock_response

        result = await generate_cypher(nl_query)

        assert ".py" in result or "extension" in result


@pytest.mark.asyncio
async def test_generate_cypher_model_error():
    """Test handling model request errors."""
    nl_query = "Find all functions"

    with (
        patch("shotgun.codebase.core.nl_query.llm_cypher_prompt") as mock_llm_prompt,
        patch("shotgun.codebase.core.nl_query.get_provider_model") as mock_get_model,
    ):
        mock_model = Mock()
        mock_model.model_instance = "test-model"
        mock_get_model.return_value = mock_model
        mock_llm_prompt.side_effect = Exception("Model API error")

        with pytest.raises(Exception, match="Model API error"):
            await generate_cypher(nl_query)


@pytest.mark.asyncio
async def test_generate_cypher_provider_model_error():
    """Test handling provider model configuration errors."""
    nl_query = "Find all functions"

    with patch("shotgun.codebase.core.nl_query.get_provider_model") as mock_get_model:
        mock_get_model.side_effect = Exception("Provider configuration error")

        with pytest.raises(Exception, match="Provider configuration error"):
            await generate_cypher(nl_query)


@pytest.mark.asyncio
async def test_generate_cypher_request_structure():
    """Test that the model request has correct structure."""
    nl_query = "Test query"

    mock_response = Mock()
    mock_response.usage = Mock()
    mock_response.usage.total_tokens = 50
    # Mock the response structure that pydantic_ai returns
    # Mock the structured response
    mock_response = CypherGenerationResponse(
        cypher_query="MATCH (n) RETURN n",
        can_generate_valid_cypher=True,
        reason_cannot_generate=None,
    )

    with (
        patch("shotgun.codebase.core.nl_query.llm_cypher_prompt") as mock_llm_prompt,
        patch("shotgun.codebase.core.nl_query.get_provider_model") as mock_get_model,
    ):
        mock_model = Mock()
        mock_model.model_instance = "test-model"
        mock_get_model.return_value = mock_model
        mock_llm_prompt.return_value = mock_response

        result = await generate_cypher(nl_query)

        # Verify function was called and returns expected result
        mock_llm_prompt.assert_called_once()
        assert result == "MATCH (n) RETURN n;"


@pytest.mark.asyncio
async def test_generate_cypher_with_datetime():
    """Test generating Cypher query with datetime context."""
    nl_query = "Find functions created today"

    mock_response = Mock()
    mock_response.usage = Mock()
    mock_response.usage.total_tokens = 80
    # Mock the response structure that pydantic_ai returns
    # Mock the structured response
    mock_response = CypherGenerationResponse(
        cypher_query="MATCH (f:Function) WHERE f.created_at > timestamp() - 86400000 RETURN f",
        can_generate_valid_cypher=True,
        reason_cannot_generate=None,
    )

    with (
        patch("shotgun.codebase.core.nl_query.llm_cypher_prompt") as mock_llm_prompt,
        patch("shotgun.codebase.core.nl_query.get_provider_model") as mock_get_model,
    ):
        mock_model = Mock()
        mock_model.model_instance = "test-model"
        mock_get_model.return_value = mock_model
        mock_llm_prompt.return_value = mock_response

        result = await generate_cypher(nl_query)

        # Verify datetime context was included
        mock_llm_prompt.assert_called_once()
        assert "timestamp()" in result or "created_at" in result


@pytest.mark.asyncio
async def test_generate_cypher_empty_query():
    """Test handling empty natural language query."""
    nl_query = ""

    mock_response = Mock()
    mock_response.usage = Mock()
    mock_response.usage.total_tokens = 10
    # Mock the response structure that pydantic_ai returns
    # Mock the structured response
    mock_response = CypherGenerationResponse(
        cypher_query="MATCH (n) RETURN n LIMIT 10",
        can_generate_valid_cypher=True,
        reason_cannot_generate=None,
    )

    with (
        patch("shotgun.codebase.core.nl_query.llm_cypher_prompt") as mock_llm_prompt,
        patch("shotgun.codebase.core.nl_query.get_provider_model") as mock_get_model,
    ):
        mock_model = Mock()
        mock_model.model_instance = "test-model"
        mock_get_model.return_value = mock_model
        mock_llm_prompt.return_value = mock_response

        result = await generate_cypher(nl_query)

        # Should still generate some default query and add semicolon
        assert result == "MATCH (n) RETURN n LIMIT 10;"


@pytest.mark.asyncio
async def test_generate_cypher_whitespace_query():
    """Test handling whitespace-only query."""
    nl_query = "   \n\t   "

    mock_response = Mock()
    mock_response.usage = Mock()
    mock_response.usage.total_tokens = 15
    # Mock the response structure that pydantic_ai returns
    # Mock the structured response
    mock_response = CypherGenerationResponse(
        cypher_query="MATCH (n) RETURN count(n)",
        can_generate_valid_cypher=True,
        reason_cannot_generate=None,
    )

    with (
        patch("shotgun.codebase.core.nl_query.llm_cypher_prompt") as mock_llm_prompt,
        patch("shotgun.codebase.core.nl_query.get_provider_model") as mock_get_model,
    ):
        mock_model = Mock()
        mock_model.model_instance = "test-model"
        mock_get_model.return_value = mock_model
        mock_llm_prompt.return_value = mock_response

        result = await generate_cypher(nl_query)

        assert "MATCH" in result


@pytest.mark.asyncio
async def test_generate_cypher_unicode_query():
    """Test handling unicode characters in query."""
    nl_query = "Find functions with names containing café or naïve"

    mock_response = Mock()
    mock_response.usage = Mock()
    mock_response.usage.total_tokens = 90
    # Mock the response structure that pydantic_ai returns
    # Mock the structured response
    mock_response = CypherGenerationResponse(
        cypher_query="MATCH (f:Function) WHERE f.name CONTAINS 'café' OR f.name CONTAINS 'naïve' RETURN f",
        can_generate_valid_cypher=True,
        reason_cannot_generate=None,
    )

    with (
        patch("shotgun.codebase.core.nl_query.llm_cypher_prompt") as mock_llm_prompt,
        patch("shotgun.codebase.core.nl_query.get_provider_model") as mock_get_model,
    ):
        mock_model = Mock()
        mock_model.model_instance = "test-model"
        mock_get_model.return_value = mock_model
        mock_llm_prompt.return_value = mock_response

        result = await generate_cypher(nl_query)

        assert "café" in result
        assert "naïve" in result


@pytest.mark.asyncio
async def test_generate_cypher_long_query():
    """Test handling very long natural language queries."""
    nl_query = "Find all Python functions that are defined in classes that inherit from BaseException and have more than 10 lines of code and were created in the last month and have docstrings that contain the word 'error' or 'exception'"

    expected_cypher = """
    MATCH (cls:Class)-[:INHERITS]->(base:Class {name: 'BaseException'})
    MATCH (cls)-[:DEFINES_METHOD]->(func:Function)
    WHERE (func.line_end - func.line_start) > 10
    AND func.created_at > timestamp() - 2592000000
    AND (func.docstring CONTAINS 'error' OR func.docstring CONTAINS 'exception')
    RETURN func.name, func.qualified_name, cls.name
    """
    # Mock the structured response
    mock_response = CypherGenerationResponse(
        cypher_query=expected_cypher.strip(),
        can_generate_valid_cypher=True,
        reason_cannot_generate=None,
    )

    with (
        patch("shotgun.codebase.core.nl_query.llm_cypher_prompt") as mock_llm_prompt,
        patch("shotgun.codebase.core.nl_query.get_provider_model") as mock_get_model,
    ):
        mock_model = Mock()
        mock_model.model_instance = "test-model"
        mock_get_model.return_value = mock_model
        mock_llm_prompt.return_value = mock_response

        result = await generate_cypher(nl_query)

        assert "BaseException" in result
        assert "INHERITS" in result
        assert "line_end - func.line_start" in result


@pytest.mark.asyncio
async def test_generate_cypher_aggregation_query():
    """Test generating Cypher for aggregation queries."""
    nl_query = "How many functions are there in each module?"

    mock_response = Mock()
    mock_response.usage = Mock()
    mock_response.usage.total_tokens = 70
    # Mock the response structure that pydantic_ai returns
    # Mock the structured response
    mock_response = CypherGenerationResponse(
        cypher_query="MATCH (m:Module)-[:DEFINES]->(f:Function) RETURN m.name, count(f) ORDER BY count(f) DESC",
        can_generate_valid_cypher=True,
        reason_cannot_generate=None,
    )

    with (
        patch("shotgun.codebase.core.nl_query.llm_cypher_prompt") as mock_llm_prompt,
        patch("shotgun.codebase.core.nl_query.get_provider_model") as mock_get_model,
    ):
        mock_model = Mock()
        mock_model.model_instance = "test-model"
        mock_get_model.return_value = mock_model
        mock_llm_prompt.return_value = mock_response

        result = await generate_cypher(nl_query)

        assert "count(" in result
        assert "ORDER BY" in result


@pytest.mark.asyncio
async def test_generate_cypher_relationship_query():
    """Test generating Cypher for relationship-focused queries."""
    nl_query = "Which functions call other functions in different modules?"

    expected_cypher = """
    MATCH (caller:Function)-[:CALLS]->(callee:Function)
    MATCH (caller)<-[:DEFINES]-(m1:Module)
    MATCH (callee)<-[:DEFINES]-(m2:Module)
    WHERE m1 <> m2
    RETURN caller.qualified_name, callee.qualified_name, m1.name, m2.name
    """
    # Mock the structured response
    mock_response = CypherGenerationResponse(
        cypher_query=expected_cypher.strip(),
        can_generate_valid_cypher=True,
        reason_cannot_generate=None,
    )

    with (
        patch("shotgun.codebase.core.nl_query.llm_cypher_prompt") as mock_llm_prompt,
        patch("shotgun.codebase.core.nl_query.get_provider_model") as mock_get_model,
    ):
        mock_model = Mock()
        mock_model.model_instance = "test-model"
        mock_get_model.return_value = mock_model
        mock_llm_prompt.return_value = mock_response

        result = await generate_cypher(nl_query)

        assert "CALLS" in result
        assert "WHERE m1 <> m2" in result or "WHERE" in result


def test_graph_schema_completeness():
    """Test that graph schema includes all necessary node types."""
    loader = PromptLoader()
    schema_content = loader.render("codebase/partials/graph_schema.j2")

    required_nodes = [
        "Project",
        "Package",
        "Folder",
        "File",
        "Module",
        "Class",
        "Function",
        "Method",
        "ExternalPackage",
        "FileMetadata",
        "DeletionLog",
    ]

    for node_type in required_nodes:
        assert f"{node_type}:" in schema_content


def test_graph_schema_relationship_completeness():
    """Test that graph schema includes all necessary relationship types."""
    loader = PromptLoader()
    schema_content = loader.render("codebase/partials/graph_schema.j2")

    required_relationships = [
        "CONTAINS_PACKAGE",
        "CONTAINS_FOLDER",
        "CONTAINS_FILE",
        "CONTAINS_MODULE",
        "DEFINES",
        "DEFINES_METHOD",
        "INHERITS",
        "OVERRIDES",
        "DEPENDS_ON_EXTERNAL",
        "CALLS",
    ]

    for rel_type in required_relationships:
        assert rel_type in schema_content


@pytest.mark.asyncio
async def test_generate_cypher_timeout_handling():
    """Test handling of request timeouts."""
    nl_query = "Find functions"

    with (
        patch("shotgun.codebase.core.nl_query.llm_cypher_prompt") as mock_llm_prompt,
        patch("shotgun.codebase.core.nl_query.get_provider_model") as mock_get_model,
    ):
        mock_model = Mock()
        mock_model.model_instance = "test-model"
        mock_get_model.return_value = mock_model

        # Simulate timeout
        import asyncio

        mock_llm_prompt.side_effect = asyncio.TimeoutError("Request timed out")

        with pytest.raises(RuntimeError, match="Failed to generate Cypher query"):
            await generate_cypher(nl_query)


@pytest.mark.asyncio
async def test_generate_cypher_response_validation():
    """Test validation of model response structure."""
    nl_query = "Test query"

    # Mock response with invalid structure (not a CypherGenerationResponse)
    mock_response = Mock()
    mock_response.can_generate_valid_cypher = True
    mock_response.cypher_query = (
        None  # Invalid: says it can generate but provides no query
    )

    with (
        patch("shotgun.codebase.core.nl_query.llm_cypher_prompt") as mock_llm_prompt,
        patch("shotgun.codebase.core.nl_query.get_provider_model") as mock_get_model,
    ):
        mock_model = Mock()
        mock_model.model_instance = "test-model"
        mock_get_model.return_value = mock_model
        mock_llm_prompt.return_value = mock_response

        with pytest.raises(
            RuntimeError, match="LLM indicated success but provided no query"
        ):
            await generate_cypher(nl_query)
