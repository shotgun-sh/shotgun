"""Service for querying local Ollama instance.

This service provides async methods to check if Ollama is running
and list available models.
"""

from datetime import datetime

import httpx
from pydantic import BaseModel

from shotgun.logging_config import get_logger

logger = get_logger(__name__)

DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_TIMEOUT = 3.0


class OllamaModel(BaseModel):
    """Information about an Ollama model."""

    name: str
    size: int  # bytes
    modified_at: datetime


class OllamaStatus(BaseModel):
    """Status of the local Ollama instance."""

    running: bool
    models: list[OllamaModel]
    error: str | None = None


def format_size(size_bytes: int) -> str:
    """Format byte size to human-readable string.

    Args:
        size_bytes: Size in bytes.

    Returns:
        Human-readable size string (e.g., "4.7 GB").
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024**2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024**3:
        return f"{size_bytes / 1024**2:.1f} MB"
    else:
        return f"{size_bytes / 1024**3:.1f} GB"


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
                    model = OllamaModel(
                        name=model_data.get("name", ""),
                        size=model_data.get("size", 0),
                        modified_at=model_data.get("modified_at", datetime.now()),
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
    "OllamaModel",
    "OllamaStatus",
    "format_size",
    "get_ollama_status",
    "DEFAULT_OLLAMA_URL",
    "DEFAULT_TIMEOUT",
]
