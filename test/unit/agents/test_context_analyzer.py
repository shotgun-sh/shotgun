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
    ContextFormatter,
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
    assert analysis.agent_responses.count == 0


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
    assert analysis.agent_responses.count == 2
    assert analysis.codebase_understanding.count == 0


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
    assert analysis.agent_responses.count == 1


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
    assert analysis.agent_responses.count == 1


@pytest.mark.asyncio()
async def test_analyze_tool_calls(model_config: ModelConfig) -> None:
    """Test analyzing tool calls in messages."""
    analyzer = ContextAnalyzer(model_config)

    # Create test messages with tool calls
    message_history = [
        ModelRequest(parts=[UserPromptPart(content="Read main.py")]),
        ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="file_read",
                    args={"graph_id": "test", "file_path": "main.py"},
                    tool_call_id="call_1",
                )
            ]
        ),
        ModelRequest(parts=[ToolReturnPart(tool_name="file_read", content="# main.py content", tool_call_id="call_1")]),
        ModelResponse(parts=[TextPart(content="Here's the content of main.py")]),
    ]

    analysis = await analyzer.analyze_conversation(message_history, message_history)

    assert analysis.user_messages.count == 1
    assert analysis.agent_responses.count == 2
    assert analysis.codebase_understanding.count == 2  # tool call + tool result


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
    assert analysis.agent_responses.count == 1


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
    agent_response_pct = analysis.get_percentage(analysis.agent_responses)

    assert user_pct >= 0
    assert agent_response_pct >= 0
    assert user_pct + agent_response_pct <= 100


def test_format_analysis() -> None:
    """Test formatting the analysis as markdown."""
    # Agent context tokens excludes hints
    agent_context_tokens = 2000 + 3000 + 500 + 1000 + 1500 + 1500  # 9500
    total_tokens = agent_context_tokens + 500  # +500 for hints = 10000
    max_usable_tokens = int(200_000 * 0.8)  # 160,000
    free_space_tokens = max_usable_tokens - agent_context_tokens  # 150,500

    analysis = ContextAnalysis(
        user_messages=MessageTypeStats(count=5, tokens=2000),
        agent_responses=MessageTypeStats(count=7, tokens=3000),
        system_prompts=MessageTypeStats(count=1, tokens=500),
        system_status=MessageTypeStats(count=3, tokens=1000),
        codebase_understanding=MessageTypeStats(count=10, tokens=1500),
        artifact_management=MessageTypeStats(count=10, tokens=1500),
        web_research=MessageTypeStats(count=0, tokens=0),
        unknown=MessageTypeStats(count=0, tokens=0),
        hint_messages=MessageTypeStats(count=2, tokens=500),
        total_tokens=total_tokens,
        total_messages=38,
        context_window=200_000,
        agent_context_tokens=agent_context_tokens,
        model_name="claude-sonnet-4-5",
        max_usable_tokens=max_usable_tokens,
        free_space_tokens=free_space_tokens,
    )

    formatted = ContextFormatter.format_markdown(analysis)

    assert "# Conversation Context Analysis" in formatted
    assert "Model: claude-sonnet-4-5" in formatted
    assert "Total Context:" in formatted
    assert "Free Space:" in formatted
    assert "Autocompact Buffer: 500 tokens" in formatted
    assert "## Context Composition" in formatted

    # Check for visual bar (should have both filled and empty circles)
    assert "●" in formatted
    assert "○" in formatted

    assert "🧑 User Messages" in formatted
    assert "🤖 Agent Responses" in formatted
    assert "📋 System Prompts" in formatted
    assert "📊 System Status" in formatted
    assert "🔍 Codebase Understanding" in formatted
    assert "📦 Artifact Management" in formatted

    # Hints should NOT be shown in the formatted output
    assert "UI Elements" not in formatted
    assert "💡 Hints:" not in formatted

    # Web research and unknown should NOT be shown when count is 0
    assert "🌐 Web Research" not in formatted
    assert "⚠️  Unknown Tools" not in formatted


def test_format_analysis_excludes_zero_counts() -> None:
    """Test that message types with zero count are excluded from display."""
    agent_context_tokens = 100 + 100  # user + agent responses = 200
    max_usable_tokens = int(200_000 * 0.8)  # 160,000
    free_space_tokens = max_usable_tokens - agent_context_tokens  # 159,800

    analysis = ContextAnalysis(
        user_messages=MessageTypeStats(count=2, tokens=100),
        agent_responses=MessageTypeStats(count=2, tokens=100),
        system_prompts=MessageTypeStats(count=0, tokens=0),
        system_status=MessageTypeStats(count=0, tokens=0),
        codebase_understanding=MessageTypeStats(count=0, tokens=0),
        artifact_management=MessageTypeStats(count=0, tokens=0),
        web_research=MessageTypeStats(count=0, tokens=0),
        unknown=MessageTypeStats(count=0, tokens=0),
        hint_messages=MessageTypeStats(count=0, tokens=0),
        total_tokens=200,
        total_messages=4,
        context_window=200_000,
        agent_context_tokens=agent_context_tokens,
        model_name="claude-sonnet-4-5",
        max_usable_tokens=max_usable_tokens,
        free_space_tokens=free_space_tokens,
    )

    formatted = ContextFormatter.format_markdown(analysis)

    # Should include user and agent responses
    assert "🧑 User Messages" in formatted
    assert "🤖 Agent Responses" in formatted

    # Should not include categories with zero count
    assert "📋 System Prompts" not in formatted
    assert "📊 System Status" not in formatted
    assert "🔍 Codebase Understanding" not in formatted


@pytest.mark.asyncio()
async def test_analyze_multi_part_message_no_double_counting(model_config: ModelConfig) -> None:
    """Test that messages with multiple parts are not double-counted.

    This is a regression test for a bug where a ModelRequest containing both
    a SystemPromptPart and UserPromptPart would count the full message tokens
    for both categories, leading to inflated totals and >100% context usage.
    """
    analyzer = ContextAnalyzer(model_config)

    # Create a message with BOTH system prompt and user prompt parts
    # This should only count tokens once total, split by part type
    multi_part_message = ModelRequest(
        parts=[
            AgentSystemPrompt(content="You are a helpful assistant."),
            UserPromptPart(content="Hello, how are you?"),
        ]
    )

    # Create a simple assistant response
    assistant_message = ModelResponse(parts=[TextPart(content="I'm doing well, thank you!")])

    message_history = [multi_part_message, assistant_message]

    analysis = await analyzer.analyze_conversation(message_history, message_history)

    # The key assertion: total tokens should NOT be double-counted
    # Even though we have a multi-part message, the total should be reasonable
    # and should never cause >100% context usage in a normal scenario

    # Calculate what percentage this would be
    context_usage_percentage = (analysis.total_tokens / analysis.context_window) * 100

    # With proper counting, this small conversation should be well under 100%
    assert context_usage_percentage < 1.0, (
        f"Context usage is {context_usage_percentage:.1f}%, which suggests double-counting. "
        f"Total tokens: {analysis.total_tokens}, "
        f"System prompts: {analysis.system_prompts.tokens}, "
        f"User messages: {analysis.user_messages.tokens}, "
        f"Agent responses: {analysis.agent_responses.tokens}"
    )

    # Verify that individual parts are counted separately
    assert analysis.system_prompts.count == 1
    assert analysis.user_messages.count == 1
    assert analysis.agent_responses.count == 1

    # Verify tokens are properly distributed (no single category has inflated counts)
    # The total should be the sum of all parts, not sum of duplicate full messages
    calculated_total = (
        analysis.system_prompts.tokens
        + analysis.user_messages.tokens
        + analysis.agent_responses.tokens
        + analysis.system_status.tokens
        + analysis.codebase_understanding.tokens
        + analysis.artifact_management.tokens
        + analysis.web_research.tokens
        + analysis.unknown.tokens
        + analysis.hint_messages.tokens
    )

    assert analysis.total_tokens == calculated_total, (
        "Total tokens should equal the sum of all part tokens"
    )
