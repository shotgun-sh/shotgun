"""Unit tests for nl_query module."""

import time
from unittest.mock import Mock, patch

import pytest

from shotgun.codebase.core.nl_query import GRAPH_SCHEMA_AND_RULES, generate_cypher


def test_graph_schema_and_rules_content():
    """Test that GRAPH_SCHEMA_AND_RULES contains expected schema information."""
    assert "Node Labels and Their Key Properties" in GRAPH_SCHEMA_AND_RULES
    assert "Project:" in GRAPH_SCHEMA_AND_RULES
    assert "Package:" in GRAPH_SCHEMA_AND_RULES
    assert "Module:" in GRAPH_SCHEMA_AND_RULES
    assert "Class:" in GRAPH_SCHEMA_AND_RULES
    assert "Function:" in GRAPH_SCHEMA_AND_RULES
    assert "Method:" in GRAPH_SCHEMA_AND_RULES
    assert "Relationships" in GRAPH_SCHEMA_AND_RULES
    assert "CONTAINS_PACKAGE" in GRAPH_SCHEMA_AND_RULES
    assert "DEFINES" in GRAPH_SCHEMA_AND_RULES
    assert "INHERITS" in GRAPH_SCHEMA_AND_RULES
    assert "CALLS" in GRAPH_SCHEMA_AND_RULES


def test_graph_schema_includes_file_extensions():
    """Test that schema includes file extension information."""
    assert "extension includes the dot" in GRAPH_SCHEMA_AND_RULES
    assert '".ts"' in GRAPH_SCHEMA_AND_RULES
    assert '".py"' in GRAPH_SCHEMA_AND_RULES
    assert '".js"' in GRAPH_SCHEMA_AND_RULES


def test_graph_schema_includes_qualified_names():
    """Test that schema includes qualified name information."""
    assert "qualified_name: string" in GRAPH_SCHEMA_AND_RULES


def test_graph_schema_includes_line_numbers():
    """Test that schema includes line number information."""
    assert "line_start: int" in GRAPH_SCHEMA_AND_RULES
    assert "line_end: int" in GRAPH_SCHEMA_AND_RULES


@pytest.mark.asyncio
async def test_generate_cypher_simple_query():
    """Test generating Cypher from simple natural language query."""
    nl_query = "Show me all functions in the codebase"
    expected_cypher = "MATCH (n:Function) RETURN n.name, n.qualified_name"

    # Mock the response structure that pydantic_ai returns
    from pydantic_ai.messages import TextPart
    mock_text_part = Mock(spec=TextPart)
    mock_text_part.content = expected_cypher

    mock_response = Mock()
    mock_response.parts = [mock_text_part]

    with (
        patch("shotgun.codebase.core.nl_query.model_request") as mock_model_request,
        patch("shotgun.codebase.core.nl_query.get_provider_model") as mock_get_model,
    ):
        mock_model = Mock()
        mock_model.pydantic_model_name = "test-model"
        mock_get_model.return_value = mock_model
        mock_model_request.return_value = mock_response

        result = await generate_cypher(nl_query)

        # The function adds cleanup and semicolon
        expected_cleaned = expected_cypher + ";"
        assert result == expected_cleaned
        mock_model_request.assert_called_once()


@pytest.mark.asyncio
async def test_generate_cypher_complex_query():
    """Test generating Cypher from complex natural language query."""
    nl_query = "Find all classes that inherit from BaseClass and show their methods"
    expected_cypher = """
    MATCH (parent:Class {name: 'BaseClass'})<-[:INHERITS]-(child:Class)
    MATCH (child)-[:DEFINES_METHOD]->(method:Method)
    RETURN child.name, method.name
    """

    # Mock the response structure that pydantic_ai returns
    from pydantic_ai.messages import TextPart
    mock_text_part = Mock(spec=TextPart)
    mock_text_part.content = expected_cypher.strip()

    mock_response = Mock()
    mock_response.parts = [mock_text_part]

    with (
        patch("shotgun.codebase.core.nl_query.model_request") as mock_model_request,
        patch("shotgun.codebase.core.nl_query.get_provider_model") as mock_get_model,
    ):
        mock_model = Mock()
        mock_model.pydantic_model_name = "test-model"
        mock_get_model.return_value = mock_model
        mock_model_request.return_value = mock_response

        result = await generate_cypher(nl_query)

        assert "INHERITS" in result
        assert "DEFINES_METHOD" in result
        assert "BaseClass" in result


@pytest.mark.asyncio
async def test_generate_cypher_with_file_extension_query():
    """Test generating Cypher query involving file extensions."""
    nl_query = "Show all Python functions"
    expected_cypher = """
    MATCH (file:File)-[:CONTAINS_MODULE]->(module:Module)-[:DEFINES]->(func:Function)
    WHERE file.extension = '.py'
    RETURN func.name, func.qualified_name
    """

    mock_response = Mock()
    mock_response.usage = Mock()
    mock_response.usage.total_tokens = 120
    # Mock the response structure that pydantic_ai returns
    from pydantic_ai.messages import TextPart
    mock_text_part = Mock(spec=TextPart)
    mock_text_part.content = expected_cypher.strip()
    mock_response.parts = [mock_text_part]

    with (
        patch("shotgun.codebase.core.nl_query.model_request") as mock_model_request,
        patch("shotgun.codebase.core.nl_query.get_provider_model") as mock_get_model,
    ):
        mock_model = Mock()
        mock_model.pydantic_model_name = "test-model"
        mock_get_model.return_value = mock_model
        mock_model_request.return_value = mock_response

        result = await generate_cypher(nl_query)

        assert ".py" in result or "extension" in result


@pytest.mark.asyncio
async def test_generate_cypher_model_error():
    """Test handling model request errors."""
    nl_query = "Find all functions"

    with (
        patch("shotgun.codebase.core.nl_query.model_request") as mock_model_request,
        patch("shotgun.codebase.core.nl_query.get_provider_model") as mock_get_model,
    ):
        mock_model = Mock()
        mock_model.pydantic_model_name = "test-model"
        mock_get_model.return_value = mock_model
        mock_model_request.side_effect = Exception("Model API error")

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
    from pydantic_ai.messages import TextPart
    mock_text_part = Mock(spec=TextPart)
    mock_text_part.content = "MATCH (n) RETURN n"
    mock_response.parts = [mock_text_part]

    with (
        patch("shotgun.codebase.core.nl_query.model_request") as mock_model_request,
        patch("shotgun.codebase.core.nl_query.get_provider_model") as mock_get_model,
    ):
        mock_model = Mock()
        mock_model.pydantic_model_name = "test-model"
        mock_get_model.return_value = mock_model
        mock_model_request.return_value = mock_response

        result = await generate_cypher(nl_query)

        # Verify function was called and returns expected result
        mock_model_request.assert_called_once()
        assert result == "MATCH (n) RETURN n;"


@pytest.mark.asyncio
async def test_generate_cypher_with_datetime():
    """Test generating Cypher query with datetime context."""
    nl_query = "Find functions created today"

    mock_response = Mock()
    mock_response.usage = Mock()
    mock_response.usage.total_tokens = 80
    # Mock the response structure that pydantic_ai returns
    from pydantic_ai.messages import TextPart
    mock_text_part = Mock(spec=TextPart)
    mock_text_part.content = "MATCH (f:Function) WHERE f.created_at > timestamp() - 86400000 RETURN f"
    mock_response.parts = [mock_text_part]

    with (
        patch("shotgun.codebase.core.nl_query.model_request") as mock_model_request,
        patch("shotgun.codebase.core.nl_query.get_provider_model") as mock_get_model,
    ):
        mock_model = Mock()
        mock_model.pydantic_model_name = "test-model"
        mock_get_model.return_value = mock_model
        mock_model_request.return_value = mock_response

        await generate_cypher(nl_query)

        # Verify datetime context was included
        mock_model_request.assert_called_once()
        call_kwargs = mock_model_request.call_args.kwargs

        # The function should be called with messages parameter
        assert "messages" in call_kwargs
        messages = call_kwargs["messages"]
        assert len(messages) == 1

        # Get the user prompt content
        model_request = messages[0]
        user_part = model_request.parts[1]  # Second part is UserPromptPart
        user_content = user_part.content

        # Should include current date/time information
        assert "Current datetime:" in user_content
        assert str(time.localtime().tm_year) in user_content


@pytest.mark.asyncio
async def test_generate_cypher_empty_query():
    """Test handling empty natural language query."""
    nl_query = ""

    mock_response = Mock()
    mock_response.usage = Mock()
    mock_response.usage.total_tokens = 10
    # Mock the response structure that pydantic_ai returns
    from pydantic_ai.messages import TextPart
    mock_text_part = Mock(spec=TextPart)
    mock_text_part.content = "MATCH (n) RETURN n LIMIT 10"
    mock_response.parts = [mock_text_part]

    with (
        patch("shotgun.codebase.core.nl_query.model_request") as mock_model_request,
        patch("shotgun.codebase.core.nl_query.get_provider_model") as mock_get_model,
    ):
        mock_model = Mock()
        mock_model.pydantic_model_name = "test-model"
        mock_get_model.return_value = mock_model
        mock_model_request.return_value = mock_response

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
    from pydantic_ai.messages import TextPart
    mock_text_part = Mock(spec=TextPart)
    mock_text_part.content = "MATCH (n) RETURN count(n)"
    mock_response.parts = [mock_text_part]

    with (
        patch("shotgun.codebase.core.nl_query.model_request") as mock_model_request,
        patch("shotgun.codebase.core.nl_query.get_provider_model") as mock_get_model,
    ):
        mock_model = Mock()
        mock_model.pydantic_model_name = "test-model"
        mock_get_model.return_value = mock_model
        mock_model_request.return_value = mock_response

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
    from pydantic_ai.messages import TextPart
    mock_text_part = Mock(spec=TextPart)
    mock_text_part.content = "MATCH (f:Function) WHERE f.name CONTAINS 'café' OR f.name CONTAINS 'naïve' RETURN f"
    mock_response.parts = [mock_text_part]

    with (
        patch("shotgun.codebase.core.nl_query.model_request") as mock_model_request,
        patch("shotgun.codebase.core.nl_query.get_provider_model") as mock_get_model,
    ):
        mock_model = Mock()
        mock_model.pydantic_model_name = "test-model"
        mock_get_model.return_value = mock_model
        mock_model_request.return_value = mock_response

        result = await generate_cypher(nl_query)

        assert "café" in result
        assert "naïve" in result


@pytest.mark.asyncio
async def test_generate_cypher_long_query():
    """Test handling very long natural language queries."""
    nl_query = "Find all Python functions that are defined in classes that inherit from BaseException and have more than 10 lines of code and were created in the last month and have docstrings that contain the word 'error' or 'exception'"

    mock_response = Mock()
    mock_response.usage = Mock()
    mock_response.usage.total_tokens = 200
    # Mock the response structure that pydantic_ai returns
    from pydantic_ai.messages import TextPart
    mock_text_part = Mock(spec=TextPart)
    mock_text_part.content = """
    MATCH (base:Class {name: 'BaseException'})<-[:INHERITS*]-(cls:Class)-[:DEFINES_METHOD]->(func:Function)
    WHERE func.line_end - func.line_start > 10
    AND func.created_at > timestamp() - 2592000000
    AND (func.docstring CONTAINS 'error' OR func.docstring CONTAINS 'exception')
    RETURN func.name, func.qualified_name, cls.name
    """
    mock_response.parts = [mock_text_part]

    with (
        patch("shotgun.codebase.core.nl_query.model_request") as mock_model_request,
        patch("shotgun.codebase.core.nl_query.get_provider_model") as mock_get_model,
    ):
        mock_model = Mock()
        mock_model.pydantic_model_name = "test-model"
        mock_get_model.return_value = mock_model
        mock_model_request.return_value = mock_response

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
    from pydantic_ai.messages import TextPart
    mock_text_part = Mock(spec=TextPart)
    mock_text_part.content = "MATCH (m:Module)-[:DEFINES]->(f:Function) RETURN m.name, count(f) ORDER BY count(f) DESC"
    mock_response.parts = [mock_text_part]

    with (
        patch("shotgun.codebase.core.nl_query.model_request") as mock_model_request,
        patch("shotgun.codebase.core.nl_query.get_provider_model") as mock_get_model,
    ):
        mock_model = Mock()
        mock_model.pydantic_model_name = "test-model"
        mock_get_model.return_value = mock_model
        mock_model_request.return_value = mock_response

        result = await generate_cypher(nl_query)

        assert "count(" in result
        assert "ORDER BY" in result


@pytest.mark.asyncio
async def test_generate_cypher_relationship_query():
    """Test generating Cypher for relationship-focused queries."""
    nl_query = "Which functions call other functions in different modules?"

    mock_response = Mock()
    mock_response.usage = Mock()
    mock_response.usage.total_tokens = 110
    # Mock the response structure that pydantic_ai returns
    from pydantic_ai.messages import TextPart
    mock_text_part = Mock(spec=TextPart)
    mock_text_part.content = """
    MATCH (caller:Function)-[:CALLS]->(callee:Function)
    MATCH (caller)<-[:DEFINES]-(m1:Module)
    MATCH (callee)<-[:DEFINES]-(m2:Module)
    WHERE m1 <> m2
    RETURN caller.qualified_name, callee.qualified_name, m1.name, m2.name
    """
    mock_response.parts = [mock_text_part]

    with (
        patch("shotgun.codebase.core.nl_query.model_request") as mock_model_request,
        patch("shotgun.codebase.core.nl_query.get_provider_model") as mock_get_model,
    ):
        mock_model = Mock()
        mock_model.pydantic_model_name = "test-model"
        mock_get_model.return_value = mock_model
        mock_model_request.return_value = mock_response

        result = await generate_cypher(nl_query)

        assert "CALLS" in result
        assert "WHERE m1 <> m2" in result or "WHERE" in result


def test_graph_schema_completeness():
    """Test that graph schema includes all necessary node types."""
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
        assert f"{node_type}:" in GRAPH_SCHEMA_AND_RULES


def test_graph_schema_relationship_completeness():
    """Test that graph schema includes all necessary relationship types."""
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
        assert rel_type in GRAPH_SCHEMA_AND_RULES


@pytest.mark.asyncio
async def test_generate_cypher_timeout_handling():
    """Test handling of request timeouts."""
    nl_query = "Find functions"

    with (
        patch("shotgun.codebase.core.nl_query.model_request") as mock_model_request,
        patch("shotgun.codebase.core.nl_query.get_provider_model") as mock_get_model,
    ):
        mock_model = Mock()
        mock_model.pydantic_model_name = "test-model"
        mock_get_model.return_value = mock_model

        # Simulate timeout
        import asyncio

        mock_model_request.side_effect = asyncio.TimeoutError("Request timed out")

        with pytest.raises(RuntimeError, match="Failed to generate Cypher query"):
            await generate_cypher(nl_query)


@pytest.mark.asyncio
async def test_generate_cypher_response_validation():
    """Test validation of model response structure."""
    nl_query = "Test query"

    # Mock response without required parts attribute
    mock_response = Mock()
    mock_response.parts = None  # Invalid parts

    with (
        patch("shotgun.codebase.core.nl_query.model_request") as mock_model_request,
        patch("shotgun.codebase.core.nl_query.get_provider_model") as mock_get_model,
    ):
        mock_model = Mock()
        mock_model.pydantic_model_name = "test-model"
        mock_get_model.return_value = mock_model
        mock_model_request.return_value = mock_response

        with pytest.raises(RuntimeError, match="Failed to generate Cypher query"):
            await generate_cypher(nl_query)
