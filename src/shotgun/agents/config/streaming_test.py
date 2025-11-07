"""Utility for testing streaming capability of OpenAI models."""

import logging

import httpx

logger = logging.getLogger(__name__)

# Maximum number of attempts to test streaming capability
MAX_STREAMING_TEST_ATTEMPTS = 3

# Timeout for each streaming test attempt (in seconds)
STREAMING_TEST_TIMEOUT = 10.0


async def check_streaming_capability(
    api_key: str, model_name: str, max_attempts: int = MAX_STREAMING_TEST_ATTEMPTS
) -> bool:
    """Check if the given OpenAI model supports streaming with this API key.

    Retries multiple times to handle transient network issues. Only returns False
    if streaming definitively fails after all retry attempts.

    Args:
        api_key: The OpenAI API key to test
        model_name: The model name (e.g., "gpt-5", "gpt-5-mini")
        max_attempts: Maximum number of attempts (default: 3)

    Returns:
        True if streaming is supported, False if it definitively fails
    """
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    # GPT-5 family uses max_completion_tokens instead of max_tokens
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": "test"}],
        "stream": True,
        "max_completion_tokens": 10,
    }

    last_error = None

    for attempt in range(1, max_attempts + 1):
        logger.debug(
            f"Streaming test attempt {attempt}/{max_attempts} for {model_name}"
        )

        try:
            async with httpx.AsyncClient(timeout=STREAMING_TEST_TIMEOUT) as client:
                async with client.stream(
                    "POST", url, json=payload, headers=headers
                ) as response:
                    # Check if we get a successful response
                    if response.status_code != 200:
                        last_error = f"HTTP {response.status_code}"
                        logger.warning(
                            f"Streaming test attempt {attempt} failed for {model_name}: {last_error}"
                        )

                        # For definitive errors (403 Forbidden, 404 Not Found), don't retry
                        if response.status_code in (403, 404):
                            logger.info(
                                f"Streaming definitively unsupported for {model_name} (HTTP {response.status_code})"
                            )
                            return False

                        # For other errors, retry
                        continue

                    # Try to read at least one chunk from the stream
                    try:
                        async for _ in response.aiter_bytes():
                            # Successfully received streaming data
                            logger.info(
                                f"Streaming test passed for {model_name} (attempt {attempt})"
                            )
                            return True
                    except Exception as e:
                        last_error = str(e)
                        logger.warning(
                            f"Streaming test attempt {attempt} failed for {model_name} while reading stream: {e}"
                        )
                        continue

        except httpx.TimeoutException:
            last_error = "timeout"
            logger.warning(
                f"Streaming test attempt {attempt} timed out for {model_name}"
            )
            continue
        except httpx.HTTPStatusError as e:
            last_error = str(e)
            logger.warning(
                f"Streaming test attempt {attempt} failed for {model_name}: {e}"
            )
            continue
        except Exception as e:
            last_error = str(e)
            logger.warning(
                f"Streaming test attempt {attempt} failed for {model_name} with unexpected error: {e}"
            )
            continue

        # If we got here without reading any chunks, streaming didn't work
        last_error = "no data received"
        logger.warning(
            f"Streaming test attempt {attempt} failed for {model_name}: no data received"
        )

    # All attempts exhausted
    logger.error(
        f"Streaming test failed for {model_name} after {max_attempts} attempts. "
        f"Last error: {last_error}. Assuming streaming is NOT supported."
    )
    return False
