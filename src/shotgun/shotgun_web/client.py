"""HTTP client for Shotgun Web API."""

import httpx

from shotgun.logging_config import get_logger

from .constants import (
    SHOTGUN_WEB_BASE_URL,
    UNIFICATION_TOKEN_CREATE_PATH,
    UNIFICATION_TOKEN_STATUS_PATH,
)
from .models import (
    TokenCreateRequest,
    TokenCreateResponse,
    TokenStatusResponse,
)

logger = get_logger(__name__)


class ShotgunWebClient:
    """HTTP client for Shotgun Web API."""

    def __init__(self, base_url: str | None = None, timeout: float = 10.0):
        """Initialize Shotgun Web client.

        Args:
            base_url: Base URL for Shotgun Web API. If None, uses SHOTGUN_WEB_BASE_URL
            timeout: Request timeout in seconds
        """
        self.base_url = base_url or SHOTGUN_WEB_BASE_URL
        self.timeout = timeout

    def create_unification_token(self, shotgun_instance_id: str) -> TokenCreateResponse:
        """Create a unification token for CLI authentication.

        Args:
            shotgun_instance_id: UUID for this shotgun instance

        Returns:
            Token creation response with token and auth URL

        Raises:
            httpx.HTTPError: If request fails
        """
        url = f"{self.base_url}{UNIFICATION_TOKEN_CREATE_PATH}"
        request_data = TokenCreateRequest(shotgun_instance_id=shotgun_instance_id)

        logger.debug("Creating unification token for instance %s", shotgun_instance_id)

        try:
            response = httpx.post(
                url,
                json=request_data.model_dump(),
                timeout=self.timeout,
            )
            response.raise_for_status()

            data = response.json()
            result = TokenCreateResponse.model_validate(data)

            logger.info(
                "Successfully created unification token, expires in %d seconds",
                result.expires_in_seconds,
            )
            return result

        except httpx.HTTPError as e:
            logger.error("Failed to create unification token: %s", e)
            raise

    def check_token_status(self, token: str) -> TokenStatusResponse:
        """Check token status and get keys if completed.

        Args:
            token: Unification token to check

        Returns:
            Token status response with status and keys (if completed)

        Raises:
            httpx.HTTPStatusError: If token not found (404) or expired (410)
            httpx.HTTPError: For other request failures
        """
        url = f"{self.base_url}{UNIFICATION_TOKEN_STATUS_PATH.format(token=token)}"

        logger.debug("Checking status for token %s...", token[:8])

        try:
            response = httpx.get(url, timeout=self.timeout)
            response.raise_for_status()

            data = response.json()
            result = TokenStatusResponse.model_validate(data)

            logger.debug("Token status: %s", result.status)
            return result

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.error("Token not found: %s", token[:8])
            elif e.response.status_code == 410:
                logger.error("Token expired: %s", token[:8])
            raise
        except httpx.HTTPError as e:
            logger.error("Failed to check token status: %s", e)
            raise


# Convenience functions for standalone use
def create_unification_token(shotgun_instance_id: str) -> TokenCreateResponse:
    """Create a unification token.

    Convenience function that creates a client and calls create_unification_token.

    Args:
        shotgun_instance_id: UUID for this shotgun instance

    Returns:
        Token creation response
    """
    client = ShotgunWebClient()
    return client.create_unification_token(shotgun_instance_id)


def check_token_status(token: str) -> TokenStatusResponse:
    """Check token status.

    Convenience function that creates a client and calls check_token_status.

    Args:
        token: Unification token to check

    Returns:
        Token status response
    """
    client = ShotgunWebClient()
    return client.check_token_status(token)
