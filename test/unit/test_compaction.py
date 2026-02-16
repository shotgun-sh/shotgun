# type: ignore
"""Unit tests for compaction module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)
from pydantic_ai.usage import RequestUsage

from shotgun.agents.conversation.history.compaction import (
    apply_persistent_compaction,
)
from shotgun.agents.conversation.history.token_estimation import (
    estimate_tokens_hybrid,
    get_last_api_token_count,
)


@pytest.fixture
def mock_deps() -> MagicMock:
    deps = MagicMock()
    deps.llm_model = MagicMock()
    deps.llm_model.name_str = "test-model"
    deps.llm_model.provider.value = "openai"
    deps.llm_model.key_provider.value = "byok"
    deps.agent_mode.value = "research"
    return deps


def testget_last_api_token_count_with_usage():
    """API usage data is extracted from the last ModelResponse."""
    messages = [
        ModelRequest(parts=[UserPromptPart(content="hello")]),
        ModelResponse(
            parts=[TextPart(content="hi")],
            usage=RequestUsage(input_tokens=1000, output_tokens=50),
        ),
        ModelRequest(parts=[UserPromptPart(content="more")]),
        ModelResponse(
            parts=[TextPart(content="sure")],
            usage=RequestUsage(
                input_tokens=5000, output_tokens=100, cache_read_tokens=2000
            ),
        ),
    ]
    # Should return the LAST response's usage: 5000 + 2000
    assert get_last_api_token_count(messages) == 7000


def testget_last_api_token_count_no_usage():
    """Returns 0 when no ModelResponse has usage data with nonzero tokens."""
    messages = [
        ModelRequest(parts=[UserPromptPart(content="hello")]),
        ModelResponse(
            parts=[TextPart(content="hi")],
            usage=RequestUsage(input_tokens=0, output_tokens=0),
        ),
    ]
    assert get_last_api_token_count(messages) == 0


def testget_last_api_token_count_empty_messages():
    """Returns 0 for empty message list."""
    assert get_last_api_token_count([]) == 0


def testget_last_api_token_count_only_requests():
    """Returns 0 when there are no ModelResponse messages."""
    messages = [
        ModelRequest(parts=[UserPromptPart(content="hello")]),
    ]
    assert get_last_api_token_count(messages) == 0


def testget_last_api_token_count_cache_read_included():
    """cache_read_tokens are added to input_tokens."""
    messages = [
        ModelResponse(
            parts=[TextPart(content="hi")],
            usage=RequestUsage(
                input_tokens=3000, output_tokens=100, cache_read_tokens=7000
            ),
        ),
    ]
    assert get_last_api_token_count(messages) == 10000


@pytest.mark.anyio
async def test_apply_persistent_compaction_uses_api_tokens(mock_deps):
    """apply_persistent_compaction prefers API usage data over estimation."""
    messages = [
        ModelRequest(parts=[UserPromptPart(content="hello")]),
        ModelResponse(
            parts=[TextPart(content="hi")],
            usage=RequestUsage(
                input_tokens=50000, output_tokens=100, cache_read_tokens=10000
            ),
        ),
    ]

    with patch(
        "shotgun.agents.conversation.history.history_processors.token_limit_compactor",
        new_callable=AsyncMock,
    ) as mock_compactor:
        mock_compactor.return_value = messages

        await apply_persistent_compaction(messages, mock_deps)

        # Verify compactor was called with usage reflecting API token count (60000)
        ctx = mock_compactor.call_args[0][0]
        assert ctx.usage.input_tokens == 60000


@pytest.mark.anyio
async def test_apply_persistent_compaction_falls_back_to_estimation(mock_deps):
    """Falls back to text estimation when no API usage data is available."""
    messages = [
        ModelRequest(parts=[UserPromptPart(content="hello")]),
        ModelResponse(
            parts=[TextPart(content="hi")],
            usage=RequestUsage(input_tokens=0, output_tokens=0),
        ),
    ]

    with (
        patch(
            "shotgun.agents.conversation.history.history_processors.token_limit_compactor",
            new_callable=AsyncMock,
        ) as mock_compactor,
        patch(
            "shotgun.agents.conversation.history.compaction.estimate_tokens_from_messages",
            new_callable=AsyncMock,
            return_value=5000,
        ) as mock_estimate,
    ):
        mock_compactor.return_value = messages

        await apply_persistent_compaction(messages, mock_deps)

        # Should have called the estimation fallback
        mock_estimate.assert_called_once_with(messages, mock_deps.llm_model)

        # Verify compactor was called with estimated tokens
        ctx = mock_compactor.call_args[0][0]
        assert ctx.usage.input_tokens == 5000


@pytest.mark.anyio
async def test_estimate_tokens_hybrid_uses_api_plus_delta():
    """Hybrid estimation uses API count plus delta counting for new messages."""
    messages = [
        ModelRequest(parts=[UserPromptPart(content="hello")]),
        ModelResponse(
            parts=[TextPart(content="hi")],
            usage=RequestUsage(
                input_tokens=5000, output_tokens=100, cache_read_tokens=2000
            ),
        ),
        ModelRequest(parts=[UserPromptPart(content="follow up question")]),
    ]

    model_config = MagicMock()

    with patch(
        "shotgun.agents.conversation.history.token_estimation.estimate_tokens_from_messages",
        new_callable=AsyncMock,
        return_value=500,
    ) as mock_estimate:
        result = await estimate_tokens_hybrid(messages, model_config)

        # API count: 5000 + 2000 = 7000, delta: 500
        assert result == 7500

        # Should only count the delta (message after last response)
        mock_estimate.assert_called_once()
        delta_messages = mock_estimate.call_args[0][0]
        assert len(delta_messages) == 1
        assert isinstance(delta_messages[0], ModelRequest)


@pytest.mark.anyio
async def test_estimate_tokens_hybrid_falls_back_when_no_usage():
    """Falls back to full counting when no API usage data is available."""
    messages = [
        ModelRequest(parts=[UserPromptPart(content="hello")]),
        ModelResponse(
            parts=[TextPart(content="hi")],
            usage=RequestUsage(input_tokens=0, output_tokens=0),
        ),
    ]

    model_config = MagicMock()

    with patch(
        "shotgun.agents.conversation.history.token_estimation.estimate_tokens_from_messages",
        new_callable=AsyncMock,
        return_value=3000,
    ) as mock_estimate:
        result = await estimate_tokens_hybrid(messages, model_config)

        assert result == 3000
        # Should count all messages (full fallback)
        mock_estimate.assert_called_once_with(messages, model_config)


@pytest.mark.anyio
async def test_estimate_tokens_hybrid_no_delta_messages():
    """Returns just the API count when there are no messages after last response."""
    messages = [
        ModelRequest(parts=[UserPromptPart(content="hello")]),
        ModelResponse(
            parts=[TextPart(content="hi")],
            usage=RequestUsage(input_tokens=5000, output_tokens=100),
        ),
    ]

    model_config = MagicMock()

    with patch(
        "shotgun.agents.conversation.history.token_estimation.estimate_tokens_from_messages",
        new_callable=AsyncMock,
    ) as mock_estimate:
        result = await estimate_tokens_hybrid(messages, model_config)

        assert result == 5000
        # Should NOT call estimate since there's no delta
        mock_estimate.assert_not_called()
