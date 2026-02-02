"""Service for querying local Ollama instance.

This service provides async methods to check if Ollama is running
and list available models.
"""

from datetime import datetime
from enum import StrEnum

import httpx
from pydantic import BaseModel

from shotgun.logging_config import get_logger

logger = get_logger(__name__)

DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_TIMEOUT = 3.0


class OllamaCapability(StrEnum):
    """Capabilities that an Ollama model may support."""

    COMPLETION = "completion"
    VISION = "vision"


class OllamaModel(BaseModel):
    """Information about an Ollama model."""

    name: str
    size: int  # bytes
    modified_at: datetime
    capabilities: list[str] = []  # e.g., ["completion", "vision"]

    @property
    def supports_vision(self) -> bool:
        """Check if this model supports vision/image input."""
        return OllamaCapability.VISION in self.capabilities


class OllamaStatus(BaseModel):
    """Status of the local Ollama instance."""

    running: bool
    models: list[OllamaModel]
    error: str | None = None


async def get_model_capabilities(
    base_url: str,
    model_name: str,
    client: httpx.AsyncClient,
) -> list[str]:
    """Fetch model capabilities from Ollama /api/show endpoint.

    Args:
        base_url: Base URL for Ollama API.
        model_name: Name of the model to query.
        client: HTTP client to use.

    Returns:
        List of capability strings (OllamaCapability values).
    """
    try:
        response = await client.post(
            f"{base_url}/api/show",
            json={"name": model_name},
        )
        if response.status_code == 200:
            data = response.json()
            # Ollama returns capabilities in model_info or details
            # The format varies, so we check multiple locations
            capabilities: list[str] = data.get("capabilities", [])
            if not capabilities:
                # Some versions put it in model_info
                model_info = data.get("model_info", {})
                if model_info:
                    # Check for vision capability markers
                    # Vision models typically have projector architecture
                    arch = model_info.get("general.architecture", "")
                    if "clip" in arch.lower() or OllamaCapability.VISION in str(model_info).lower():
                        capabilities = [OllamaCapability.COMPLETION, OllamaCapability.VISION]
                    else:
                        capabilities = [OllamaCapability.COMPLETION]
            return capabilities
    except Exception as e:
        logger.debug(f"Failed to fetch capabilities for {model_name}: {e}")
    return []


async def get_ollama_status(
    base_url: str = DEFAULT_OLLAMA_URL,
    timeout: float = DEFAULT_TIMEOUT,
) -> OllamaStatus:
    """Check if Ollama is running and get available models.

    Args:
        base_url: Base URL for Ollama API.
        timeout: Request timeout in seconds.

    Returns:
        OllamaStatus with running state and available models.
    """
    async with httpx.AsyncClient(timeout=timeout) as client:
        # First check if Ollama is running
        try:
            response = await client.get(f"{base_url}/")
            if response.status_code != 200:
                return OllamaStatus(
                    running=False,
                    models=[],
                    error=f"Unexpected status code: {response.status_code}",
                )
        except httpx.ConnectError:
            logger.debug("Ollama is not running (connection refused)")
            return OllamaStatus(
                running=False,
                models=[],
                error="Ollama is not running",
            )
        except httpx.TimeoutException:
            logger.debug("Ollama check timed out")
            return OllamaStatus(
                running=False,
                models=[],
                error="Connection timed out",
            )
        except httpx.RequestError as e:
            logger.debug(f"Ollama request error: {e}")
            return OllamaStatus(
                running=False,
                models=[],
                error=str(e),
            )

        # Ollama is running, now get models
        try:
            response = await client.get(f"{base_url}/api/tags")
            response.raise_for_status()
            data = response.json()

            models = []
            for model_data in data.get("models", []):
                try:
                    model_name = model_data.get("name", "")
                    # Fetch capabilities for each model
                    capabilities = await get_model_capabilities(
                        base_url, model_name, client
                    )
                    model = OllamaModel(
                        name=model_name,
                        size=model_data.get("size", 0),
                        modified_at=model_data.get("modified_at", datetime.now()),
                        capabilities=capabilities,
                    )
                    models.append(model)
                except Exception as e:
                    logger.warning(f"Failed to parse model data: {e}")
                    continue

            return OllamaStatus(running=True, models=models)

        except httpx.HTTPStatusError as e:
            logger.warning(f"Failed to fetch Ollama models: {e}")
            return OllamaStatus(
                running=True,
                models=[],
                error=f"Failed to fetch models: {e.response.status_code}",
            )
        except Exception as e:
            logger.warning(f"Error fetching Ollama models: {e}")
            return OllamaStatus(
                running=True,
                models=[],
                error=str(e),
            )


__all__ = [
    "OllamaCapability",
    "OllamaModel",
    "OllamaStatus",
    "get_model_capabilities",
    "get_ollama_status",
    "DEFAULT_OLLAMA_URL",
    "DEFAULT_TIMEOUT",
]
