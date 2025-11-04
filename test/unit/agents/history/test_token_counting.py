"""Unit tests for token counting with empty messages."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai.messages import ModelRequest, UserPromptPart

from shotgun.agents.history.token_counting.anthropic import AnthropicTokenCounter
from shotgun.agents.history.token_counting.openai import OpenAITokenCounter
from shotgun.agents.history.token_counting.sentencepiece_counter import (
    SentencePieceTokenCounter,
)


@pytest.mark.asyncio
async def test_anthropic_empty_text_no_api_call():
    """Test that Anthropic counter returns 0 for empty text without API call."""
    with patch("anthropic.AsyncAnthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_anthropic.return_value = mock_client
        counter = AnthropicTokenCounter("claude-3-opus", "test-key")
        counter.client = mock_client

        # Test empty string
        result = await counter.count_tokens("")
        assert result == 0
        counter.client.messages.count_tokens.assert_not_called()

        # Test whitespace-only string
        result = await counter.count_tokens("   \n\t  ")
        assert result == 0
        counter.client.messages.count_tokens.assert_not_called()


@pytest.mark.asyncio
async def test_anthropic_empty_messages_no_api_call():
    """Test that Anthropic counter returns 0 for empty message list without API call."""
    with patch("anthropic.AsyncAnthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_anthropic.return_value = mock_client
        counter = AnthropicTokenCounter("claude-3-opus", "test-key")
        counter.client = mock_client

        # Test empty list
        result = await counter.count_message_tokens([])
        assert result == 0
        counter.client.messages.count_tokens.assert_not_called()


@pytest.mark.asyncio
async def test_openai_empty_text_no_encoding():
    """Test that OpenAI counter returns 0 for empty text without encoding."""
    with patch("tiktoken.get_encoding") as mock_get_encoding:
        mock_encoding = MagicMock()
        mock_get_encoding.return_value = mock_encoding

        counter = OpenAITokenCounter("gpt-4")

        # Test empty string
        result = await counter.count_tokens("")
        assert result == 0
        mock_encoding.encode.assert_not_called()

        # Test whitespace-only string
        result = await counter.count_tokens("   \n\t  ")
        assert result == 0
        mock_encoding.encode.assert_not_called()


@pytest.mark.asyncio
async def test_openai_empty_messages_no_encoding():
    """Test that OpenAI counter returns 0 for empty message list without encoding."""
    with patch("tiktoken.get_encoding") as mock_get_encoding:
        mock_encoding = MagicMock()
        mock_get_encoding.return_value = mock_encoding

        counter = OpenAITokenCounter("gpt-4")

        # Test empty list
        result = await counter.count_message_tokens([])
        assert result == 0
        mock_encoding.encode.assert_not_called()


@pytest.mark.asyncio
async def test_sentencepiece_empty_text_no_tokenization():
    """Test that SentencePiece counter returns 0 for empty text without tokenization."""
    counter = SentencePieceTokenCounter("gemini-1.5-pro")

    # Don't initialize the tokenizer
    assert counter.sp is None

    # Test empty string - should not trigger tokenizer loading
    result = await counter.count_tokens("")
    assert result == 0
    assert counter.sp is None  # Tokenizer should not be loaded

    # Test whitespace-only string
    result = await counter.count_tokens("   \n\t  ")
    assert result == 0
    assert counter.sp is None  # Tokenizer should not be loaded


@pytest.mark.asyncio
async def test_sentencepiece_empty_messages_no_tokenization():
    """Test that SentencePiece counter returns 0 for empty message list without tokenization."""
    counter = SentencePieceTokenCounter("gemini-1.5-pro")

    # Don't initialize the tokenizer
    assert counter.sp is None

    # Test empty list - should not trigger tokenizer loading
    result = await counter.count_message_tokens([])
    assert result == 0
    assert counter.sp is None  # Tokenizer should not be loaded


@pytest.mark.asyncio
async def test_non_empty_text_calls_api():
    """Test that non-empty text properly calls the API/encoding."""
    # Anthropic
    with patch("anthropic.AsyncAnthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_anthropic.return_value = mock_client
        counter = AnthropicTokenCounter("claude-3-opus", "test-key")
        counter.client = mock_client
        counter.client.messages.count_tokens.return_value = MagicMock(input_tokens=5)

        result = await counter.count_tokens("Hello world")
        assert result == 5
        counter.client.messages.count_tokens.assert_called_once()

    # OpenAI
    with patch("tiktoken.get_encoding") as mock_get_encoding:
        mock_encoding = MagicMock()
        mock_encoding.encode.return_value = [1, 2, 3, 4, 5]
        mock_get_encoding.return_value = mock_encoding

        counter = OpenAITokenCounter("gpt-4")
        result = await counter.count_tokens("Hello world")
        assert result == 5
        mock_encoding.encode.assert_called_once_with("Hello world")


@pytest.mark.asyncio
async def test_messages_with_content():
    """Test that messages with content are properly processed."""
    # Create a test message with content
    message = ModelRequest(parts=[UserPromptPart(content="Test message")])

    with patch("anthropic.AsyncAnthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_anthropic.return_value = mock_client
        counter = AnthropicTokenCounter("claude-3-opus", "test-key")
        counter.client = mock_client
        counter.client.messages.count_tokens.return_value = MagicMock(input_tokens=3)

        result = await counter.count_message_tokens([message])
        assert result == 3
        counter.client.messages.count_tokens.assert_called_once()

        # Verify the extracted text was passed
        call_args = counter.client.messages.count_tokens.call_args
        assert "Test message" in call_args[1]["messages"][0]["content"]
