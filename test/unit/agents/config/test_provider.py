"""Tests for provider model cache behavior."""

from unittest.mock import MagicMock, patch

import pytest

from shotgun.agents.config.models import KeyProvider, ProviderType
from shotgun.agents.config.provider import (
    _MAX_MODEL_CACHE_SIZE,
    get_or_create_model,
)


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear the LRU cache before and after each test."""
    get_or_create_model.cache_clear()
    yield
    get_or_create_model.cache_clear()


def test_cache_returns_same_instance():
    """Cache hits return the exact same Model object."""
    mock_model = MagicMock()

    with patch(
        "shotgun.agents.config.provider._create_openai_compat_model",
        return_value=mock_model,
    ):
        result1 = get_or_create_model(
            provider=ProviderType.OPENAI_COMPATIBLE,
            key_provider=KeyProvider.BYOK,
            model_name="model-a",
            api_key="key-a",
            base_url="http://localhost:11434",
        )
        result2 = get_or_create_model(
            provider=ProviderType.OPENAI_COMPATIBLE,
            key_provider=KeyProvider.BYOK,
            model_name="model-a",
            api_key="key-a",
            base_url="http://localhost:11434",
        )

    assert result1 is result2
    info = get_or_create_model.cache_info()
    assert info.hits == 1
    assert info.misses == 1


def test_cache_evicts_when_exceeding_max_size():
    """LRU eviction keeps cache bounded at _MAX_MODEL_CACHE_SIZE."""
    mock_model = MagicMock()

    with patch(
        "shotgun.agents.config.provider._create_openai_compat_model",
        return_value=mock_model,
    ):
        for i in range(_MAX_MODEL_CACHE_SIZE + 2):
            get_or_create_model(
                provider=ProviderType.OPENAI_COMPATIBLE,
                key_provider=KeyProvider.BYOK,
                model_name=f"model-{i}",
                api_key=f"key-{i}",
                base_url="http://localhost:11434",
            )

    info = get_or_create_model.cache_info()
    assert info.currsize == _MAX_MODEL_CACHE_SIZE


def test_evicted_entry_is_recreated():
    """After eviction, requesting the same model creates a new instance."""
    mock_model = MagicMock()

    with patch(
        "shotgun.agents.config.provider._create_openai_compat_model",
        return_value=mock_model,
    ) as mock_create:
        # Fill cache beyond max to evict model-0
        for i in range(_MAX_MODEL_CACHE_SIZE + 1):
            get_or_create_model(
                provider=ProviderType.OPENAI_COMPATIBLE,
                key_provider=KeyProvider.BYOK,
                model_name=f"model-{i}",
                api_key=f"key-{i}",
                base_url="http://localhost:11434",
            )

        # Request model-0 again — should be a miss (it was evicted)
        get_or_create_model(
            provider=ProviderType.OPENAI_COMPATIBLE,
            key_provider=KeyProvider.BYOK,
            model_name="model-0",
            api_key="key-0",
            base_url="http://localhost:11434",
        )

    info = get_or_create_model.cache_info()
    # All initial creates + 1 re-creation of model-0
    assert info.misses == _MAX_MODEL_CACHE_SIZE + 2
    assert info.hits == 0


def test_max_cache_size_is_reasonable():
    assert _MAX_MODEL_CACHE_SIZE == 8
