"""Real token counting for all supported providers.

This module provides accurate token counting using each provider's official
APIs and libraries, eliminating the need for rough character-based estimation.
"""

from .anthropic import AnthropicTokenCounter
from .base import TokenCounter, extract_text_from_messages
from .openai import OpenAITokenCounter
from .sentencepiece_counter import SentencePieceTokenCounter
from .utils import (
    count_post_summary_tokens,
    count_tokens_from_message_parts,
    count_tokens_from_messages,
    get_token_counter,
)

__all__ = [
    # Base classes
    "TokenCounter",
    # Counter implementations
    "OpenAITokenCounter",
    "AnthropicTokenCounter",
    "SentencePieceTokenCounter",
    # Utility functions
    "get_token_counter",
    "count_tokens_from_messages",
    "count_post_summary_tokens",
    "count_tokens_from_message_parts",
    "extract_text_from_messages",
]
