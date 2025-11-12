"""HTTP client for LiteLLM Proxy API."""

import time
from typing import Any

import httpx

from shotgun.api_endpoints import LITELLM_PROXY_BASE_URL
from shotgun.logging_config import get_logger

from .models import BudgetInfo, KeyInfoResponse, TeamInfoResponse

logger = get_logger(__name__)


class LiteLLMProxyClient:
    """HTTP client for LiteLLM Proxy API.

    Provides methods to query budget information and key/team metadata
    from a LiteLLM proxy server.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        timeout: float = 10.0,
        max_retries: int = 3,
    ):
        """Initialize LiteLLM Proxy client.

        Args:
            api_key: LiteLLM API key for authentication
            base_url: Base URL for LiteLLM proxy. If None, uses LITELLM_PROXY_BASE_URL
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts for failed requests
        """
        self.api_key = api_key
        self.base_url = base_url or LITELLM_PROXY_BASE_URL
        self.timeout = timeout
        self.max_retries = max_retries

    def _request_with_retry(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make HTTP request with exponential backoff retry.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            **kwargs: Additional arguments to pass to httpx request

        Returns:
            HTTP response

        Raises:
            httpx.HTTPError: If request fails after all retries
        """
        last_exception = None

        for attempt in range(self.max_retries):
            try:
                response = httpx.request(method, url, timeout=self.timeout, **kwargs)
                response.raise_for_status()
                return response

            except httpx.HTTPError as e:
                last_exception = e
                # Don't retry on client errors (4xx) except 429 (rate limit)
                if isinstance(e, httpx.HTTPStatusError):
                    if 400 <= e.response.status_code < 500 and e.response.status_code != 429:
                        logger.error(
                            "Client error from LiteLLM proxy: %s - %s",
                            e.response.status_code,
                            e.response.text,
                        )
                        raise

                # Log and retry on server errors (5xx) or network errors
                if attempt < self.max_retries - 1:
                    wait_seconds = 2**attempt  # 1s, 2s, 4s
                    logger.warning(
                        "Request failed (attempt %d/%d): %s. Retrying in %ds...",
                        attempt + 1,
                        self.max_retries,
                        e,
                        wait_seconds,
                    )
                    time.sleep(wait_seconds)
                else:
                    logger.error(
                        "Request failed after %d attempts: %s", self.max_retries, e
                    )

        if last_exception:
            raise last_exception
        raise RuntimeError("Request failed with no exception captured")

    def get_key_info(self) -> KeyInfoResponse:
        """Get key information from LiteLLM proxy.

        Returns:
            Key information including spend, budget, and team_id

        Raises:
            httpx.HTTPError: If request fails
        """
        url = f"{self.base_url}/key/info"
        params = {"key": self.api_key}
        headers = {"Authorization": f"Bearer {self.api_key}"}

        logger.debug("Fetching key info from %s", url)

        response = self._request_with_retry("GET", url, params=params, headers=headers)

        data = response.json()
        result = KeyInfoResponse.model_validate(data)

        logger.info(
            "Successfully fetched key info: key_alias=%s, team_id=%s",
            result.info.key_alias,
            result.info.team_id,
        )
        return result

    def get_team_info(self, team_id: str) -> TeamInfoResponse:
        """Get team information from LiteLLM proxy.

        Args:
            team_id: Team identifier

        Returns:
            Team information including spend and budget

        Raises:
            httpx.HTTPError: If request fails
        """
        url = f"{self.base_url}/team/info"
        params = {"team_id": team_id}
        headers = {"Authorization": f"Bearer {self.api_key}"}

        logger.debug("Fetching team info from %s for team_id=%s", url, team_id)

        response = self._request_with_retry("GET", url, params=params, headers=headers)

        data = response.json()
        result = TeamInfoResponse.model_validate(data)

        logger.info(
            "Successfully fetched team info: team_alias=%s",
            result.team_info.team_alias,
        )
        return result

    def get_budget_info(self) -> BudgetInfo:
        """Get budget information with automatic key/team resolution.

        Checks if the key has a budget set. If yes, returns key-level budget.
        If no, fetches and returns team-level budget.

        Returns:
            Unified budget information

        Raises:
            httpx.HTTPError: If request fails
            ValueError: If neither key nor team has budget configured
        """
        logger.debug("Fetching budget info")

        # Get key info first
        key_response = self.get_key_info()
        key_info = key_response.info

        # Check if key has its own budget
        if key_info.max_budget is not None:
            logger.debug("Using key-level budget: $%.6f", key_info.max_budget)
            return BudgetInfo.from_key_info(key_info)

        # Key doesn't have budget, fetch team budget
        logger.debug(
            "Key has no budget, fetching team budget for team_id=%s",
            key_info.team_id,
        )
        team_response = self.get_team_info(key_info.team_id)
        team_info = team_response.team_info

        if team_info.max_budget is None:
            raise ValueError(
                f"Neither key nor team (team_id={key_info.team_id}) has max_budget configured"
            )

        logger.debug("Using team-level budget: $%.6f", team_info.max_budget)
        return BudgetInfo.from_team_info(team_info)


# Convenience function for standalone use
def get_budget_info(api_key: str, base_url: str | None = None) -> BudgetInfo:
    """Get budget information for an API key.

    Convenience function that creates a client and calls get_budget_info.

    Args:
        api_key: LiteLLM API key
        base_url: Optional base URL for LiteLLM proxy

    Returns:
        Budget information
    """
    client = LiteLLMProxyClient(api_key, base_url=base_url)
    return client.get_budget_info()
