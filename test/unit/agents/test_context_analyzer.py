"""Tests for ContextAnalyzer conversation composition analysis."""

import pytest
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from shotgun.agents.config.models import (
    KeyProvider,
    ModelConfig,
    ModelName,
    ProviderType,
)
from shotgun.agents.context_analyzer import (
    ContextAnalysis,
    ContextAnalyzer,
    MessageTypeStats,
)
from shotgun.agents.messages import AgentSystemPrompt, SystemStatusPrompt
from shotgun.tui.screens.chat_screen.hint_message import HintMessage


@pytest.fixture()
def model_config() -> ModelConfig:
    """Create a test model configuration."""
    return ModelConfig(
        name=ModelName.GPT_5_MINI,
        provider=ProviderType.OPENAI,
        key_provider=KeyProvider.BYOK,
        max_input_tokens=400_000,
        max_output_tokens=128_000,
        api_key="test-key",
    )


@pytest.mark.asyncio()
async def test_analyze_empty_conversation(model_config: ModelConfig) -> None:
    """Test analyzing an empty conversation."""
    analyzer = ContextAnalyzer(model_config)
    analysis = await analyzer.analyze_conversation([], [])

    assert analysis.total_messages == 0
    assert analysis.total_tokens == 0
    assert analysis.user_messages.count == 0
    assert analysis.assistant_messages.count == 0


@pytest.mark.asyncio()
async def test_analyze_user_and_assistant_messages(model_config: ModelConfig) -> None:
    """Test analyzing basic user and assistant messages."""
    analyzer = ContextAnalyzer(model_config)

    # Create test messages
    message_history = [
        ModelRequest(parts=[UserPromptPart(content="Hello")]),
        ModelResponse(parts=[TextPart(content="Hi there!")]),
        ModelRequest(parts=[UserPromptPart(content="How are you?")]),
        ModelResponse(parts=[TextPart(content="I'm doing well, thanks!")]),
    ]

    analysis = await analyzer.analyze_conversation(message_history, message_history)

    assert analysis.total_messages == 4
    assert analysis.user_messages.count == 2
    assert analysis.assistant_messages.count == 2
    assert analysis.tool_calls.count == 0


@pytest.mark.asyncio()
async def test_analyze_system_prompts(model_config: ModelConfig) -> None:
    """Test analyzing system prompts."""
    analyzer = ContextAnalyzer(model_config)

    # Create test messages with system prompts
    message_history = [
        ModelRequest(parts=[AgentSystemPrompt(content="You are a helpful assistant")]),
        ModelRequest(parts=[UserPromptPart(content="Hello")]),
        ModelResponse(parts=[TextPart(content="Hi there!")]),
    ]

    analysis = await analyzer.analyze_conversation(message_history, message_history)

    assert analysis.system_prompts.count == 1
    assert analysis.user_messages.count == 1
    assert analysis.assistant_messages.count == 1


@pytest.mark.asyncio()
async def test_analyze_system_status(model_config: ModelConfig) -> None:
    """Test analyzing system status messages."""
    analyzer = ContextAnalyzer(model_config)

    # Create test messages with system status
    message_history = [
        ModelRequest(parts=[SystemStatusPrompt(content="Current files: main.py, test.py")]),
        ModelRequest(parts=[UserPromptPart(content="What files are available?")]),
        ModelResponse(parts=[TextPart(content="You have main.py and test.py")]),
    ]

    analysis = await analyzer.analyze_conversation(message_history, message_history)

    assert analysis.system_status.count == 1
    assert analysis.user_messages.count == 1
    assert analysis.assistant_messages.count == 1


@pytest.mark.asyncio()
async def test_analyze_tool_calls(model_config: ModelConfig) -> None:
    """Test analyzing tool calls in messages."""
    analyzer = ContextAnalyzer(model_config)

    # Create test messages with tool calls
    message_history = [
        ModelRequest(parts=[UserPromptPart(content="Search for Python tutorials")]),
        ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="web_search",
                    args={"query": "Python tutorials"},
                    tool_call_id="call_1",
                )
            ]
        ),
        ModelRequest(parts=[ToolReturnPart(tool_name="web_search", content="Results...", tool_call_id="call_1")]),
        ModelResponse(parts=[TextPart(content="I found some tutorials for you")]),
    ]

    analysis = await analyzer.analyze_conversation(message_history, message_history)

    assert analysis.user_messages.count == 1
    assert analysis.assistant_messages.count == 2
    assert analysis.tool_calls.count == 1
    assert analysis.tool_results.count == 1


@pytest.mark.asyncio()
async def test_analyze_hint_messages(model_config: ModelConfig) -> None:
    """Test analyzing hint messages in UI history."""
    analyzer = ContextAnalyzer(model_config)

    # Create test messages
    message_history = [
        ModelRequest(parts=[UserPromptPart(content="Hello")]),
        ModelResponse(parts=[TextPart(content="Hi there!")]),
    ]

    ui_message_history = [
        message_history[0],
        message_history[1],
        HintMessage(message="Usage: 100 tokens"),
        HintMessage(message="Context: 2 messages"),
    ]

    analysis = await analyzer.analyze_conversation(message_history, ui_message_history)

    assert analysis.hint_messages.count == 2
    assert analysis.user_messages.count == 1
    assert analysis.assistant_messages.count == 1


@pytest.mark.asyncio()
async def test_percentage_calculation(model_config: ModelConfig) -> None:
    """Test that percentages are calculated correctly."""
    analyzer = ContextAnalyzer(model_config)

    message_history = [
        ModelRequest(parts=[UserPromptPart(content="Hello")]),
        ModelResponse(parts=[TextPart(content="Hi there!")]),
    ]

    analysis = await analyzer.analyze_conversation(message_history, message_history)

    # Check that percentages add up (approximately, due to token counting)
    user_pct = analysis.get_percentage(analysis.user_messages)
    assistant_pct = analysis.get_percentage(analysis.assistant_messages)

    assert user_pct >= 0
    assert assistant_pct >= 0
    assert user_pct + assistant_pct <= 100


def test_format_analysis() -> None:
    """Test formatting the analysis as markdown."""
    analysis = ContextAnalysis(
        user_messages=MessageTypeStats(count=5, tokens=2000),
        assistant_messages=MessageTypeStats(count=7, tokens=3000),
        system_prompts=MessageTypeStats(count=1, tokens=500),
        system_status=MessageTypeStats(count=3, tokens=1000),
        tool_calls=MessageTypeStats(count=10, tokens=1500),
        tool_results=MessageTypeStats(count=10, tokens=1500),
        hint_messages=MessageTypeStats(count=2, tokens=500),
        total_tokens=10000,
        total_messages=38,
        context_window=200_000,
    )

    formatted = analysis.format_analysis()

    assert "# Conversation Context Analysis" in formatted
    assert "## Message Composition" in formatted
    assert "🧑 User Messages:" in formatted
    assert "🤖 Assistant Messages:" in formatted
    assert "📋 System Prompts:" in formatted
    assert "📊 System Status:" in formatted
    assert "🔧 Tool Calls:" in formatted
    assert "📥 Tool Results:" in formatted
    assert "💡 Hints:" in formatted
    assert "## Summary" in formatted
    assert "Total Messages: 38" in formatted
    assert "Total Tokens: ~10,000" in formatted


def test_format_analysis_excludes_zero_counts() -> None:
    """Test that message types with zero count are excluded from display."""
    analysis = ContextAnalysis(
        user_messages=MessageTypeStats(count=2, tokens=100),
        assistant_messages=MessageTypeStats(count=2, tokens=100),
        system_prompts=MessageTypeStats(count=0, tokens=0),
        system_status=MessageTypeStats(count=0, tokens=0),
        tool_calls=MessageTypeStats(count=0, tokens=0),
        tool_results=MessageTypeStats(count=0, tokens=0),
        hint_messages=MessageTypeStats(count=0, tokens=0),
        total_tokens=200,
        total_messages=4,
        context_window=200_000,
    )

    formatted = analysis.format_analysis()

    # Should include user and assistant
    assert "🧑 User Messages:" in formatted
    assert "🤖 Assistant Messages:" in formatted

    # Should not include categories with zero count
    assert "📋 System Prompts:" not in formatted
    assert "📊 System Status:" not in formatted
    assert "🔧 Tool Calls:" not in formatted
