"""Utility for testing streaming capability of OpenAI models."""

import logging

import httpx

logger = logging.getLogger(__name__)


async def check_streaming_capability(api_key: str, model_name: str) -> bool:
    """Check if the given OpenAI model supports streaming with this API key.

    Args:
        api_key: The OpenAI API key to test
        model_name: The model name (e.g., "gpt-5", "gpt-5-mini")

    Returns:
        True if streaming is supported, False otherwise
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

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                # Check if we get a successful response
                if response.status_code != 200:
                    logger.warning(
                        f"Streaming test failed for {model_name}: HTTP {response.status_code}"
                    )
                    return False

                # Try to read at least one chunk from the stream
                try:
                    async for _ in response.aiter_bytes():
                        # Successfully received streaming data
                        logger.info(f"Streaming test passed for {model_name}")
                        return True
                except Exception as e:
                    logger.warning(
                        f"Streaming test failed for {model_name} while reading stream: {e}"
                    )
                    return False

    except httpx.TimeoutException:
        logger.warning(f"Streaming test timed out for {model_name}")
        return False
    except httpx.HTTPStatusError as e:
        logger.warning(f"Streaming test failed for {model_name}: {e}")
        return False
    except Exception as e:
        logger.warning(f"Streaming test failed for {model_name} with unexpected error: {e}")
        return False

    # If we got here without reading any chunks, streaming didn't work
    logger.warning(f"Streaming test failed for {model_name}: no data received")
    return False
