"""Tests for provider model cache behavior and model override."""

from unittest.mock import MagicMock, patch

import pytest

from shotgun.agents.config.models import KeyProvider, ModelName, ProviderType
from shotgun.agents.config.provider import (
    _MAX_MODEL_CACHE_SIZE,
    _has_provider_key,
    get_or_create_model,
    set_general_model_override,
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


def test_set_general_model_override_sets_and_clears():
    """Test that set_general_model_override sets and clears the global."""
    import shotgun.agents.config.provider as provider_module

    # Set override
    set_general_model_override(ModelName.CLAUDE_SONNET_4_6)
    assert provider_module._general_model_override == ModelName.CLAUDE_SONNET_4_6

    # Clear override
    set_general_model_override(None)
    assert provider_module._general_model_override is None


def test_has_provider_key_checks_env_vars():
    """Test that _has_provider_key checks environment variables."""
    from shotgun.agents.config.models import ShotgunConfig

    config = ShotgunConfig(shotgun_instance_id="test-id")

    # No keys in config or env
    with patch.dict("os.environ", {}, clear=True):
        assert _has_provider_key(config, ProviderType.OPENAI) is False
        assert _has_provider_key(config, ProviderType.ANTHROPIC) is False
        assert _has_provider_key(config, ProviderType.GOOGLE) is False

    # Keys in env vars only
    with patch.dict(
        "os.environ",
        {
            "OPENAI_API_KEY": "sk-test",
            "ANTHROPIC_API_KEY": "sk-ant-test",
            "GEMINI_API_KEY": "gm-test",
        },
    ):
        assert _has_provider_key(config, ProviderType.OPENAI) is True
        assert _has_provider_key(config, ProviderType.ANTHROPIC) is True
        assert _has_provider_key(config, ProviderType.GOOGLE) is True
