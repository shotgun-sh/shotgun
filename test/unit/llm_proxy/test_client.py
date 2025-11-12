"""Tests for LiteLLM Proxy API client."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from shotgun.api_endpoints import LITELLM_PROXY_BASE_URL
from shotgun.llm_proxy.client import LiteLLMProxyClient
from shotgun.llm_proxy.models import BudgetSource


@pytest.fixture
def mock_httpx_request():
    """Mock httpx.request."""
    with patch("httpx.request") as mock:
        yield mock


def test_client_init():
    """Test LiteLLMProxyClient initialization."""
    client = LiteLLMProxyClient(api_key="test-key")
    assert client.api_key == "test-key"
    assert client.base_url == LITELLM_PROXY_BASE_URL
    assert client.timeout == 10.0


def test_client_init_custom():
    """Test LiteLLMProxyClient with custom parameters."""
    client = LiteLLMProxyClient(
        api_key="custom-key",
        base_url="https://custom.url",
        timeout=30.0,
    )
    assert client.api_key == "custom-key"
    assert client.base_url == "https://custom.url"
    assert client.timeout == 30.0


def test_get_key_info_success(mock_httpx_request):
    """Test successful get_key_info call."""
    # Setup mock response
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "key": "sk-test",
        "info": {
            "key_name": "sk-...test",
            "key_alias": "TestKey",
            "spend": 1.5,
            "max_budget": 10.0,
            "team_id": "team-123",
            "user_id": "user-456",
            "models": ["gpt-4"],
        },
    }
    mock_response.raise_for_status = MagicMock()
    mock_httpx_request.return_value = mock_response

    # Call method
    client = LiteLLMProxyClient(api_key="test-key")
    result = client.get_key_info()

    # Assertions
    assert result.key == "sk-test"
    assert result.info.spend == 1.5
    assert result.info.max_budget == 10.0
    assert result.info.team_id == "team-123"

    # Verify HTTP call
    mock_httpx_request.assert_called_once()
    call_args = mock_httpx_request.call_args
    assert call_args[0][0] == "GET"
    assert "key=test-key" in call_args[0][1] or call_args[1]["params"]["key"] == "test-key"
    assert call_args[1]["headers"]["Authorization"] == "Bearer test-key"


def test_get_team_info_success(mock_httpx_request):
    """Test successful get_team_info call."""
    # Setup mock response
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "team_id": "team-123",
        "team_info": {
            "team_id": "team-123",
            "team_alias": "TestTeam",
            "max_budget": 50.0,
            "spend": 12.5,
            "models": [],
        },
    }
    mock_response.raise_for_status = MagicMock()
    mock_httpx_request.return_value = mock_response

    # Call method
    client = LiteLLMProxyClient(api_key="test-key")
    result = client.get_team_info("team-123")

    # Assertions
    assert result.team_id == "team-123"
    assert result.team_info.spend == 12.5
    assert result.team_info.max_budget == 50.0

    # Verify HTTP call
    mock_httpx_request.assert_called_once()


def test_get_budget_info_key_level(mock_httpx_request):
    """Test get_budget_info with key-level budget."""
    # Setup mock response for get_key_info
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "key": "sk-test",
        "info": {
            "key_name": "sk-...test",
            "spend": 3.0,
            "max_budget": 10.0,  # Key has budget
            "team_id": "team-123",
            "user_id": "user-456",
            "models": [],
        },
    }
    mock_response.raise_for_status = MagicMock()
    mock_httpx_request.return_value = mock_response

    # Call method
    client = LiteLLMProxyClient(api_key="test-key")
    result = client.get_budget_info()

    # Assertions
    assert result.max_budget == 10.0
    assert result.spend == 3.0
    assert result.remaining == 7.0
    assert result.source == BudgetSource.KEY
    assert result.percentage_used == 30.0

    # Should only call get_key_info, not get_team_info
    mock_httpx_request.assert_called_once()


def test_get_budget_info_team_level(mock_httpx_request):
    """Test get_budget_info with team-level budget (key has no budget)."""
    # Setup mock responses
    def mock_request_side_effect(method, url, *args, **kwargs):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        if "/key/info" in url:
            # Key has no budget, must fetch team budget
            mock_response.json.return_value = {
                "key": "sk-test",
                "info": {
                    "key_name": "sk-...test",
                    "spend": 0.0,
                    "max_budget": None,  # No key budget
                    "team_id": "team-456",
                    "user_id": "user-789",
                    "models": [],
                },
            }
        elif "/team/info" in url:
            mock_response.json.return_value = {
                "team_id": "team-456",
                "team_info": {
                    "team_id": "team-456",
                    "max_budget": 100.0,
                    "spend": 25.0,
                    "models": [],
                },
            }

        return mock_response

    mock_httpx_request.side_effect = mock_request_side_effect

    # Call method
    client = LiteLLMProxyClient(api_key="test-key")
    result = client.get_budget_info()

    # Assertions
    assert result.max_budget == 100.0
    assert result.spend == 25.0
    assert result.remaining == 75.0
    assert result.source == BudgetSource.TEAM
    assert result.percentage_used == 25.0

    # Should call both get_key_info and get_team_info
    assert mock_httpx_request.call_count == 2


def test_get_budget_info_no_budget_configured(mock_httpx_request):
    """Test get_budget_info when neither key nor team has budget."""
    # Setup mock responses
    def mock_request_side_effect(method, url, *args, **kwargs):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        if "/key/info" in url:
            mock_response.json.return_value = {
                "key": "sk-test",
                "info": {
                    "key_name": "sk-...test",
                    "spend": 0.0,
                    "max_budget": None,
                    "team_id": "team-789",
                    "user_id": "user-101",
                    "models": [],
                },
            }
        elif "/team/info" in url:
            mock_response.json.return_value = {
                "team_id": "team-789",
                "team_info": {
                    "team_id": "team-789",
                    "max_budget": None,  # No team budget either
                    "spend": 0.0,
                    "models": [],
                },
            }

        return mock_response

    mock_httpx_request.side_effect = mock_request_side_effect

    # Call method and expect ValueError
    client = LiteLLMProxyClient(api_key="test-key")
    with pytest.raises(ValueError, match="Neither key nor team.*has max_budget configured"):
        client.get_budget_info()


def test_retry_on_server_error(mock_httpx_request):
    """Test retry logic on server error."""
    # First two attempts fail with 500, third succeeds
    mock_response_success = MagicMock()
    mock_response_success.json.return_value = {
        "key": "sk-test",
        "info": {
            "key_name": "sk-...test",
            "spend": 0.0,
            "max_budget": None,
            "team_id": "team-123",
            "user_id": "user-456",
            "models": [],
        },
    }
    mock_response_success.raise_for_status = MagicMock()

    mock_httpx_request.side_effect = [
        httpx.HTTPStatusError("Server Error", request=MagicMock(), response=MagicMock(status_code=500)),
        httpx.HTTPStatusError("Server Error", request=MagicMock(), response=MagicMock(status_code=503)),
        mock_response_success,
    ]

    client = LiteLLMProxyClient(api_key="test-key")
    result = client.get_key_info()

    # Should succeed after retries
    assert result.key == "sk-test"
    assert mock_httpx_request.call_count == 3


def test_no_retry_on_client_error(mock_httpx_request):
    """Test that client errors (4xx except 429) are not retried."""
    mock_response = MagicMock()
    mock_response.status_code = 404

    mock_httpx_request.side_effect = httpx.HTTPStatusError(
        "Not Found", request=MagicMock(), response=mock_response
    )

    client = LiteLLMProxyClient(api_key="test-key")

    with pytest.raises(httpx.HTTPStatusError):
        client.get_key_info()

    # Should only be called once (no retries)
    assert mock_httpx_request.call_count == 1


def test_http_error_propagation(mock_httpx_request):
    """Test that HTTP errors are propagated after retries."""
    mock_httpx_request.side_effect = httpx.RequestError("Connection failed", request=MagicMock())

    client = LiteLLMProxyClient(api_key="test-key")

    with pytest.raises(httpx.RequestError):
        client.get_key_info()
