"""Unit tests for context validation module."""

# type: ignore

from unittest.mock import patch

import pytest
from pydantic_ai import RunUsage
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart

from shotgun.agents.config.models import (
    KeyProvider,
    ModelConfig,
    ModelName,
    ProviderType,
)
from shotgun.agents.history.constants import TOKEN_LIMIT_RATIO
from shotgun.agents.history.validation import (
    ContextValidationResult,
    validate_context_for_model,
)


@pytest.fixture
def claude_sonnet_config():
    """Create a test ModelConfig for Claude Sonnet 4.5."""
    return ModelConfig(
        name=ModelName.CLAUDE_SONNET_4_5,
        provider=ProviderType.ANTHROPIC,
        key_provider=KeyProvider.BYOK,
        max_input_tokens=200_000,
        max_output_tokens=16_000,
        api_key="test-key",
    )


@pytest.fixture
def gemini_pro_config():
    """Create a test ModelConfig for Gemini 2.5 Pro."""
    return ModelConfig(
        name=ModelName.GEMINI_2_5_PRO,
        provider=ProviderType.GOOGLE,
        key_provider=KeyProvider.BYOK,
        max_input_tokens=1_000_000,
        max_output_tokens=65_536,
        api_key="test-key",
    )


@pytest.fixture
def sample_messages_with_usage():
    """Create sample messages with usage data for testing."""
    return [
        ModelRequest(parts=[UserPromptPart(content="Hello")]),
        ModelResponse(
            parts=[TextPart(content="Hi there!")],
            usage=RunUsage(input_tokens=10, output_tokens=5, cache_read_tokens=0),
        ),
        ModelRequest(parts=[UserPromptPart(content="How are you?")]),
        ModelResponse(
            parts=[TextPart(content="I'm doing well, thanks!")],
            usage=RunUsage(input_tokens=25, output_tokens=10, cache_read_tokens=0),
        ),
    ]


@pytest.fixture
def sample_messages_no_usage():
    """Create sample messages without usage data (for testing fallback)."""
    return [
        ModelRequest(parts=[UserPromptPart(content="Hello")]),
        ModelResponse(parts=[TextPart(content="Hi there!")]),
        ModelRequest(parts=[UserPromptPart(content="How are you?")]),
        ModelResponse(parts=[TextPart(content="I'm doing well, thanks!")]),
    ]


def test_context_validation_result_properties():
    """Test ContextValidationResult property calculations."""
    # Valid scenario: 50K tokens, 100K max
    result = ContextValidationResult(is_valid=True, current_tokens=50_000, max_tokens=100_000)
    assert result.is_valid is True
    assert result.current_tokens == 50_000
    assert result.max_tokens == 100_000
    assert result.current_tokens_k == 50
    assert result.max_tokens_k == 100
    assert result.overflow_tokens == 0

    # Invalid scenario: 150K tokens, 100K max
    result = ContextValidationResult(is_valid=False, current_tokens=150_000, max_tokens=100_000)
    assert result.is_valid is False
    assert result.current_tokens == 150_000
    assert result.max_tokens == 100_000
    assert result.current_tokens_k == 150
    assert result.max_tokens_k == 100
    assert result.overflow_tokens == 50_000


@pytest.mark.asyncio
async def test_validate_context_within_limit(claude_sonnet_config):
    """Test validation passes when conversation fits within model limit."""
    # Create messages with usage data: 50K input + 5K output = 55K total
    # Well within 80% of 200K = 160K limit
    messages = [
        ModelRequest(parts=[UserPromptPart(content="Hello")]),
        ModelResponse(
            parts=[TextPart(content="Hi there!")],
            usage=RunUsage(input_tokens=50_000, output_tokens=5_000, cache_read_tokens=0),
        ),
    ]
    result = await validate_context_for_model(messages, claude_sonnet_config)

    assert result.is_valid is True
    assert result.current_tokens == 55_000  # input + output
    assert result.max_tokens == int(200_000 * TOKEN_LIMIT_RATIO)  # 160K
    assert result.overflow_tokens == 0


@pytest.mark.asyncio
async def test_validate_context_exceeds_limit(claude_sonnet_config):
    """Test validation fails when conversation exceeds model limit."""
    # Create messages with usage data: 170K input + 10K output = 180K total
    # Exceeds 80% of 200K = 160K limit
    messages = [
        ModelRequest(parts=[UserPromptPart(content="Hello")]),
        ModelResponse(
            parts=[TextPart(content="Hi there!")],
            usage=RunUsage(input_tokens=170_000, output_tokens=10_000, cache_read_tokens=0),
        ),
    ]
    result = await validate_context_for_model(messages, claude_sonnet_config)

    assert result.is_valid is False
    assert result.current_tokens == 180_000  # input + output
    assert result.max_tokens == int(200_000 * TOKEN_LIMIT_RATIO)  # 160K
    assert result.overflow_tokens == 20_000


@pytest.mark.asyncio
async def test_validate_context_at_exact_limit(claude_sonnet_config):
    """Test validation fails when conversation is at exact limit."""
    # Create messages with usage data: exactly 160K tokens (80% of 200K)
    max_allowed = int(200_000 * TOKEN_LIMIT_RATIO)  # 160K
    messages = [
        ModelRequest(parts=[UserPromptPart(content="Hello")]),
        ModelResponse(
            parts=[TextPart(content="Hi there!")],
            usage=RunUsage(input_tokens=max_allowed, output_tokens=0, cache_read_tokens=0),
        ),
    ]
    result = await validate_context_for_model(messages, claude_sonnet_config)

    # Should be invalid because we check current < max (not <=)
    assert result.is_valid is False
    assert result.current_tokens == max_allowed
    assert result.max_tokens == max_allowed


@pytest.mark.asyncio
async def test_validate_context_large_model(gemini_pro_config):
    """Test validation with large context window model (Gemini)."""
    # Create messages with 300K tokens (290K input + 10K output)
    # This would exceed Claude (200K * 0.8 = 160K) but fits Gemini (1M * 0.8 = 800K)
    messages = [
        ModelRequest(parts=[UserPromptPart(content="Hello")]),
        ModelResponse(
            parts=[TextPart(content="Hi there!")],
            usage=RunUsage(input_tokens=290_000, output_tokens=10_000, cache_read_tokens=0),
        ),
    ]
    result = await validate_context_for_model(messages, gemini_pro_config)

    assert result.is_valid is True
    assert result.current_tokens == 300_000
    assert result.max_tokens == int(1_000_000 * TOKEN_LIMIT_RATIO)  # 800K


@pytest.mark.asyncio
async def test_validate_context_empty_messages(claude_sonnet_config):
    """Test validation with empty message list (fallback to estimation)."""
    # Empty messages have no usage data, should fall back to estimation
    with patch("shotgun.agents.history.validation.estimate_tokens_from_messages", return_value=0):
        result = await validate_context_for_model([], claude_sonnet_config)

        assert result.is_valid is True
        assert result.current_tokens == 0


@pytest.mark.asyncio
async def test_validate_context_model_switching_scenario(claude_sonnet_config, gemini_pro_config):
    """Test scenario where conversation fits Gemini but not Claude."""
    # Create messages with 250K tokens (240K input + 10K output)
    messages = [
        ModelRequest(parts=[UserPromptPart(content="Hello")]),
        ModelResponse(
            parts=[TextPart(content="Hi there!")],
            usage=RunUsage(input_tokens=240_000, output_tokens=10_000, cache_read_tokens=0),
        ),
    ]

    # Should fit in Gemini (800K limit)
    gemini_result = await validate_context_for_model(messages, gemini_pro_config)
    assert gemini_result.is_valid is True

    # Should NOT fit in Claude (160K limit)
    claude_result = await validate_context_for_model(messages, claude_sonnet_config)
    assert claude_result.is_valid is False
    assert claude_result.overflow_tokens > 0


@pytest.mark.asyncio
async def test_validate_context_token_estimation_error(claude_sonnet_config, sample_messages_no_usage):
    """Test that token estimation errors propagate correctly when fallback fails."""
    # Messages without usage data should fall back to estimation
    # If estimation fails, error should propagate
    with patch("shotgun.agents.history.validation.estimate_tokens_from_messages", side_effect=RuntimeError("Token counting failed")):
        with pytest.raises(RuntimeError, match="Token counting failed"):
            await validate_context_for_model(sample_messages_no_usage, claude_sonnet_config)


@pytest.mark.asyncio
async def test_validate_context_with_cache_tokens(claude_sonnet_config):
    """Test validation correctly includes cache_read_tokens (for future prompt caching)."""
    # Create messages with cache tokens (currently 0, but test the calculation)
    messages = [
        ModelRequest(parts=[UserPromptPart(content="Hello")]),
        ModelResponse(
            parts=[TextPart(content="Hi there!")],
            usage=RunUsage(input_tokens=50_000, output_tokens=5_000, cache_read_tokens=10_000),
        ),
    ]
    result = await validate_context_for_model(messages, claude_sonnet_config)

    # Should include cache_read_tokens: 50K input + 10K cache + 5K output = 65K total
    assert result.is_valid is True
    assert result.current_tokens == 65_000
    assert result.max_tokens == int(200_000 * TOKEN_LIMIT_RATIO)  # 160K


@pytest.mark.asyncio
async def test_validate_context_fallback_to_estimation(claude_sonnet_config, sample_messages_no_usage):
    """Test that validation falls back to estimation when no usage data available."""
    # Messages without usage data should use estimation
    with patch("shotgun.agents.history.validation.estimate_tokens_from_messages", return_value=75_000):
        result = await validate_context_for_model(sample_messages_no_usage, claude_sonnet_config)

        assert result.is_valid is True
        assert result.current_tokens == 75_000
        assert result.max_tokens == int(200_000 * TOKEN_LIMIT_RATIO)  # 160K
