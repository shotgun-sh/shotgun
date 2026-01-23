"""Tests for mermaid validation tools."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from shotgun.agents.tools.mermaid_validation import (
    MermaidBatchResult,
    MermaidValidationResult,
    _call_batch_validation_api,
    _call_validation_api,
    extract_mermaid_diagrams,
    validate_mermaid,
    validate_mermaid_in_content,
)


# Tests for MermaidValidationResult model


def test_mermaid_validation_result_valid():
    result = MermaidValidationResult(valid=True, diagram_type="flowchart-v2")
    assert result.valid is True
    assert result.diagram_type == "flowchart-v2"
    assert result.error_message is None
    assert result.error_line is None


def test_mermaid_validation_result_invalid():
    result = MermaidValidationResult(
        valid=False,
        error_message="Parse error",
        error_line=3,
    )
    assert result.valid is False
    assert result.error_message == "Parse error"
    assert result.error_line == 3


# Tests for MermaidBatchResult model


def test_mermaid_batch_result_all_valid():
    results = [
        MermaidValidationResult(valid=True, diagram_type="flowchart"),
        MermaidValidationResult(valid=True, diagram_type="sequence"),
    ]
    batch = MermaidBatchResult(
        total=2, valid_count=2, invalid_count=0, results=results
    )
    assert batch.all_valid is True


def test_mermaid_batch_result_not_all_valid():
    results = [
        MermaidValidationResult(valid=True, diagram_type="flowchart"),
        MermaidValidationResult(valid=False, error_message="Error"),
    ]
    batch = MermaidBatchResult(
        total=2, valid_count=1, invalid_count=1, results=results
    )
    assert batch.all_valid is False


# Tests for extract_mermaid_diagrams function


def test_extract_mermaid_diagrams_no_diagrams():
    content = "# Hello\n\nThis is just text."
    result = extract_mermaid_diagrams(content)
    assert result == []


def test_extract_mermaid_diagrams_single_diagram():
    content = """# Doc

```mermaid
flowchart TD
    A --> B
```

End."""
    result = extract_mermaid_diagrams(content)
    assert len(result) == 1
    diagram, start, end = result[0]
    assert "flowchart TD" in diagram
    assert "A --> B" in diagram


def test_extract_mermaid_diagrams_multiple_diagrams():
    content = """# Doc

```mermaid
flowchart TD
    A --> B
```

Some text

```mermaid
sequenceDiagram
    Alice->>Bob: Hello
```
"""
    result = extract_mermaid_diagrams(content)
    assert len(result) == 2
    assert "flowchart TD" in result[0][0]
    assert "sequenceDiagram" in result[1][0]


def test_extract_mermaid_diagrams_case_insensitive():
    content = """```MERMAID
flowchart TD
    A --> B
```"""
    result = extract_mermaid_diagrams(content)
    assert len(result) == 1


def test_extract_mermaid_diagrams_whitespace_after_mermaid():
    content = """```mermaid
flowchart TD
    A --> B
```"""
    result = extract_mermaid_diagrams(content)
    assert len(result) == 1


# Tests for _call_validation_api function


@pytest.mark.anyio
async def test_call_validation_api_valid_response():
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "valid": True,
        "diagramType": "flowchart-v2",
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.post = AsyncMock(return_value=mock_response)
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client.return_value = mock_instance

        result = await _call_validation_api("flowchart TD\n    A --> B")

        assert result.valid is True
        assert result.diagram_type == "flowchart-v2"


@pytest.mark.anyio
async def test_call_validation_api_invalid_response():
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "valid": False,
        "error": {
            "message": "Parse error",
            "line": 2,
        },
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.post = AsyncMock(return_value=mock_response)
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client.return_value = mock_instance

        result = await _call_validation_api("invalid diagram")

        assert result.valid is False
        assert result.error_message == "Parse error"
        assert result.error_line == 2


@pytest.mark.anyio
async def test_call_validation_api_timeout_error():
    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.post = AsyncMock(
            side_effect=httpx.TimeoutException("timeout")
        )
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client.return_value = mock_instance

        result = await _call_validation_api("diagram")

        assert result.valid is False
        assert "timed out" in result.error_message


@pytest.mark.anyio
async def test_call_validation_api_request_error():
    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.post = AsyncMock(
            side_effect=httpx.RequestError("connection failed")
        )
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client.return_value = mock_instance

        result = await _call_validation_api("diagram")

        assert result.valid is False
        assert "request failed" in result.error_message


# Tests for _call_batch_validation_api function


@pytest.mark.anyio
async def test_call_batch_validation_api_valid_response():
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "results": [
            {"valid": True, "diagramType": "flowchart"},
            {"valid": True, "diagramType": "sequence"},
        ]
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.post = AsyncMock(return_value=mock_response)
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client.return_value = mock_instance

        diagrams = [{"id": "0", "diagram": "d1"}, {"id": "1", "diagram": "d2"}]
        results = await _call_batch_validation_api(diagrams)

        assert len(results) == 2
        assert all(r.valid for r in results)


@pytest.mark.anyio
async def test_call_batch_validation_api_mixed_response():
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "results": [
            {"valid": True, "diagramType": "flowchart"},
            {"valid": False, "error": {"message": "Error", "line": 1}},
        ]
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.post = AsyncMock(return_value=mock_response)
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client.return_value = mock_instance

        diagrams = [{"id": "0", "diagram": "d1"}, {"id": "1", "diagram": "d2"}]
        results = await _call_batch_validation_api(diagrams)

        assert len(results) == 2
        assert results[0].valid is True
        assert results[1].valid is False


@pytest.mark.anyio
async def test_call_batch_validation_api_timeout_error():
    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.post = AsyncMock(
            side_effect=httpx.TimeoutException("timeout")
        )
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client.return_value = mock_instance

        diagrams = [{"id": "0", "diagram": "d1"}, {"id": "1", "diagram": "d2"}]
        results = await _call_batch_validation_api(diagrams)

        assert len(results) == 2
        assert all(not r.valid for r in results)
        assert all("timed out" in r.error_message for r in results)


# Tests for validate_mermaid tool function


@pytest.mark.anyio
async def test_validate_mermaid_valid_diagram():
    mock_ctx = MagicMock()

    with patch(
        "shotgun.agents.tools.mermaid_validation._call_validation_api"
    ) as mock_api:
        mock_api.return_value = MermaidValidationResult(
            valid=True, diagram_type="flowchart-v2"
        )

        result = await validate_mermaid(mock_ctx, "flowchart TD\n    A --> B")

        assert "Valid" in result
        assert "flowchart-v2" in result


@pytest.mark.anyio
async def test_validate_mermaid_invalid_diagram():
    mock_ctx = MagicMock()

    with patch(
        "shotgun.agents.tools.mermaid_validation._call_validation_api"
    ) as mock_api:
        mock_api.return_value = MermaidValidationResult(
            valid=False, error_message="Parse error", error_line=2
        )

        result = await validate_mermaid(mock_ctx, "invalid diagram")

        assert "Invalid" in result
        assert "line 2" in result
        assert "Parse error" in result


# Tests for validate_mermaid_in_content tool function


@pytest.mark.anyio
async def test_validate_mermaid_in_content_no_diagrams():
    mock_ctx = MagicMock()

    result = await validate_mermaid_in_content(
        mock_ctx, "# Just text\n\nNo diagrams here."
    )

    assert "No mermaid diagrams found" in result


@pytest.mark.anyio
async def test_validate_mermaid_in_content_all_valid():
    mock_ctx = MagicMock()
    content = """# Doc

```mermaid
flowchart TD
    A --> B
```
"""
    with patch(
        "shotgun.agents.tools.mermaid_validation._call_batch_validation_api"
    ) as mock_api:
        mock_api.return_value = [
            MermaidValidationResult(valid=True, diagram_type="flowchart")
        ]

        result = await validate_mermaid_in_content(mock_ctx, content)

        assert "Found 1 mermaid diagram" in result
        assert "All diagrams are valid" in result


@pytest.mark.anyio
async def test_validate_mermaid_in_content_some_invalid():
    mock_ctx = MagicMock()
    content = """# Doc

```mermaid
flowchart TD
    A --> B
```

```mermaid
invalid
```
"""
    with patch(
        "shotgun.agents.tools.mermaid_validation._call_batch_validation_api"
    ) as mock_api:
        mock_api.return_value = [
            MermaidValidationResult(valid=True, diagram_type="flowchart"),
            MermaidValidationResult(valid=False, error_message="Parse error"),
        ]

        result = await validate_mermaid_in_content(mock_ctx, content)

        assert "Found 2 mermaid diagram" in result
        assert "1 diagram(s) have errors" in result
