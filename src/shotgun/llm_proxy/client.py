"""HTTP client for LiteLLM Proxy API."""

import logging
from typing import Any

import httpx
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from shotgun.api_endpoints import LITELLM_PROXY_BASE_URL
from shotgun.logging_config import get_logger

from .models import BudgetInfo, KeyInfoResponse, TeamInfoResponse

logger = get_logger(__name__)


def _is_retryable_http_error(exception: BaseException) -> bool:
    """Check if HTTP exception should trigger a retry.

    Args:
        exception: The exception to check

    Returns:
        True if the exception is a transient error that should be retried
    """
    # Retry on network errors and timeouts
    if isinstance(exception, (httpx.RequestError, httpx.TimeoutException)):
        return True

    # Retry on server errors (5xx) and rate limits (429)
    if isinstance(exception, httpx.HTTPStatusError):
        status_code = exception.response.status_code
        return status_code >= 500 or status_code == 429

    # Don't retry on other errors (e.g., 4xx client errors)
    return False


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
    ):
        """Initialize LiteLLM Proxy client.

        Args:
            api_key: LiteLLM API key for authentication
            base_url: Base URL for LiteLLM proxy. If None, uses LITELLM_PROXY_BASE_URL
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.base_url = base_url or LITELLM_PROXY_BASE_URL
        self.timeout = timeout

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=8),
        retry=retry_if_exception(_is_retryable_http_error),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def _request_with_retry(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make async HTTP request with exponential backoff retry and jitter.

        Uses tenacity to retry on transient errors (5xx, 429, network errors)
        with exponential backoff and jitter. Client errors (4xx except 429)
        are not retried.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            **kwargs: Additional arguments to pass to httpx request

        Returns:
            HTTP response

        Raises:
            httpx.HTTPError: If request fails after all retries
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(method, url, **kwargs)
            response.raise_for_status()
            return response

    async def get_key_info(self) -> KeyInfoResponse:
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

        response = await self._request_with_retry(
            "GET", url, params=params, headers=headers
        )

        data = response.json()
        result = KeyInfoResponse.model_validate(data)

        logger.info(
            "Successfully fetched key info: key_alias=%s, team_id=%s",
            result.info.key_alias,
            result.info.team_id,
        )
        return result

    async def get_team_info(self, team_id: str) -> TeamInfoResponse:
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

        response = await self._request_with_retry(
            "GET", url, params=params, headers=headers
        )

        data = response.json()
        result = TeamInfoResponse.model_validate(data)

        logger.info(
            "Successfully fetched team info: team_alias=%s",
            result.team_info.team_alias,
        )
        return result

    async def get_budget_info(self) -> BudgetInfo:
        """Get team-level budget information for this key.

        Budget is always configured at the team level, never at the key level.
        This method fetches the team_id from the key info, then retrieves
        the team's budget information.

        Returns:
            Team-level budget information

        Raises:
            httpx.HTTPError: If request fails
            ValueError: If team has no budget configured
        """
        logger.debug("Fetching budget info")

        # Get key info to retrieve team_id
        key_response = await self.get_key_info()
        key_info = key_response.info

        # Fetch team budget (budget is always at team level)
        logger.debug(
            "Fetching team budget for team_id=%s",
            key_info.team_id,
        )
        team_response = await self.get_team_info(key_info.team_id)
        team_info = team_response.team_info

        if team_info.max_budget is None:
            raise ValueError(
                f"Team (team_id={key_info.team_id}) has no max_budget configured"
            )

        logger.debug("Using team-level budget: $%.6f", team_info.max_budget)
        return BudgetInfo.from_team_info(team_info)


# Convenience function for standalone use
async def get_budget_info(api_key: str, base_url: str | None = None) -> BudgetInfo:
    """Get budget information for an API key.

    Convenience function that creates a client and calls get_budget_info.

    Args:
        api_key: LiteLLM API key
        base_url: Optional base URL for LiteLLM proxy

    Returns:
        Budget information
    """
    client = LiteLLMProxyClient(api_key, base_url=base_url)
    return await client.get_budget_info()
