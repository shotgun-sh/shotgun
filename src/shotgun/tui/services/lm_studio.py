"""Service for querying local LM Studio instance.

This service provides async methods to check if LM Studio is running
and list available models. LM Studio provides an OpenAI-compatible API.
"""

import httpx
from pydantic import BaseModel

from shotgun.logging_config import get_logger

logger = get_logger(__name__)

DEFAULT_LM_STUDIO_URL = "http://localhost:1234"
DEFAULT_TIMEOUT = 3.0
LM_STUDIO_DOWNLOAD_URL = "https://lmstudio.ai/"


class LMStudioModel(BaseModel):
    """Information about an LM Studio model."""

    id: str  # Model identifier (e.g., "lmstudio-community/Meta-Llama-3-8B-Instruct-GGUF")
    object: str = "model"  # Always "model"
    owned_by: str = "lmstudio"

    @property
    def name(self) -> str:
        """Get the model name (alias for id)."""
        return self.id

    @property
    def supports_tools(self) -> bool:
        """Check if this model supports tool/function calling.

        LM Studio models loaded via the server generally support function calling
        if the model itself has been trained for it. We assume support since
        LM Studio doesn't expose capability metadata.
        """
        return True

    @property
    def supports_vision(self) -> bool:
        """Check if this model supports vision/image input.

        LM Studio doesn't expose vision capability metadata via API.
        We conservatively assume False.
        """
        return False


class LMStudioStatus(BaseModel):
    """Status of the local LM Studio instance."""

    running: bool
    models: list[LMStudioModel]
    error: str | None = None


async def get_lm_studio_status(
    base_url: str = DEFAULT_LM_STUDIO_URL,
    timeout: float = DEFAULT_TIMEOUT,
) -> LMStudioStatus:
    """Check if LM Studio is running and get available models.

    LM Studio provides an OpenAI-compatible API at /v1/models.

    Args:
        base_url: Base URL for LM Studio API (default: http://localhost:1234).
        timeout: Request timeout in seconds.

    Returns:
        LMStudioStatus with running state and available models.
    """
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            # LM Studio uses OpenAI-compatible /v1/models endpoint
            response = await client.get(f"{base_url}/v1/models")
            if response.status_code != 200:
                return LMStudioStatus(
                    running=False,
                    models=[],
                    error=f"Unexpected status code: {response.status_code}",
                )

            data = response.json()
            models = []

            # Parse the OpenAI-compatible response format
            # {"object": "list", "data": [{"id": "model-name", "object": "model", ...}]}
            for model_data in data.get("data", []):
                try:
                    model = LMStudioModel(
                        id=model_data.get("id", ""),
                        object=model_data.get("object", "model"),
                        owned_by=model_data.get("owned_by", "lmstudio"),
                    )
                    models.append(model)
                except Exception as e:
                    logger.warning(f"Failed to parse LM Studio model data: {e}")
                    continue

            return LMStudioStatus(running=True, models=models)

        except httpx.ConnectError:
            logger.debug("LM Studio is not running (connection refused)")
            return LMStudioStatus(
                running=False,
                models=[],
                error="LM Studio is not running",
            )
        except httpx.TimeoutException:
            logger.debug("LM Studio check timed out")
            return LMStudioStatus(
                running=False,
                models=[],
                error="Connection timed out",
            )
        except httpx.RequestError as e:
            logger.debug(f"LM Studio request error: {e}")
            return LMStudioStatus(
                running=False,
                models=[],
                error=str(e),
            )
        except Exception as e:
            logger.warning(f"Error checking LM Studio status: {e}")
            return LMStudioStatus(
                running=False,
                models=[],
                error=str(e),
            )


async def has_lm_studio_models_available(
    base_url: str = DEFAULT_LM_STUDIO_URL,
) -> bool:
    """Check if LM Studio is running and has at least one model available.

    This is a convenience function that combines get_lm_studio_status checks.

    Args:
        base_url: Base URL for LM Studio API.

    Returns:
        True if LM Studio is running and has models, False otherwise.
    """
    status = await get_lm_studio_status(base_url=base_url)
    return status.running and bool(status.models)


def sanitize_lm_studio_model_name_for_id(name: str) -> str:
    """Sanitize LM Studio model name for use as a DOM ID.

    Replaces characters not allowed in Textual widget IDs.

    Args:
        name: The LM Studio model name (e.g., "lmstudio-community/Meta-Llama-3-8B-Instruct-GGUF").

    Returns:
        Sanitized string safe for use as DOM ID.
    """
    return name.replace(":", "-").replace("/", "-").replace(".", "-")


__all__ = [
    "LMStudioModel",
    "LMStudioStatus",
    "get_lm_studio_status",
    "has_lm_studio_models_available",
    "sanitize_lm_studio_model_name_for_id",
    "DEFAULT_LM_STUDIO_URL",
    "DEFAULT_TIMEOUT",
    "LM_STUDIO_DOWNLOAD_URL",
]
