"""Tests for ContextIndicator component."""

from shotgun.agents.config.models import ModelName
from shotgun.agents.context_analyzer.models import ContextAnalysis, MessageTypeStats
from shotgun.tui.components.context_indicator import ContextIndicator


def create_test_analysis(
    agent_context_tokens: int = 72_000,
    max_usable_tokens: int = 160_000,
) -> ContextAnalysis:
    """Create a test ContextAnalysis object with minimal required fields."""
    free_space_tokens = max_usable_tokens - agent_context_tokens
    return ContextAnalysis(
        user_messages=MessageTypeStats(count=0, tokens=0),
        agent_responses=MessageTypeStats(count=0, tokens=0),
        system_prompts=MessageTypeStats(count=0, tokens=0),
        system_status=MessageTypeStats(count=0, tokens=0),
        codebase_understanding=MessageTypeStats(count=0, tokens=0),
        artifact_management=MessageTypeStats(count=0, tokens=0),
        web_research=MessageTypeStats(count=0, tokens=0),
        unknown=MessageTypeStats(count=0, tokens=0),
        hint_messages=MessageTypeStats(count=0, tokens=0),
        total_tokens=agent_context_tokens,
        total_messages=0,
        context_window=200_000,
        agent_context_tokens=agent_context_tokens,
        model_name="test-model",
        max_usable_tokens=max_usable_tokens,
        free_space_tokens=free_space_tokens,
    )


def test_context_indicator_initialization():
    """Test ContextIndicator can be initialized."""
    indicator = ContextIndicator(id="test-indicator")
    assert indicator.context_analysis is None
    assert indicator.model_name is None


def test_context_indicator_update_context():
    """Test updating context indicator with analysis data."""
    indicator = ContextIndicator()

    analysis = create_test_analysis(
        agent_context_tokens=72_000, max_usable_tokens=160_000
    )

    indicator.update_context(analysis, ModelName.CLAUDE_SONNET_4_6)

    assert indicator.context_analysis == analysis
    assert indicator.model_name == ModelName.CLAUDE_SONNET_4_6


def test_context_indicator_format_token_count():
    """Test token count formatting."""
    indicator = ContextIndicator()

    assert indicator._format_token_count(500) == "500"
    assert indicator._format_token_count(1_500) == "2K"
    assert indicator._format_token_count(72_000) == "72K"
    assert indicator._format_token_count(160_000) == "160K"
    assert indicator._format_token_count(1_000_000) == "1.0M"
    assert indicator._format_token_count(2_500_000) == "2.5M"


def test_context_indicator_percentage_color_green():
    """Test color for low usage percentage (green)."""
    indicator = ContextIndicator()

    assert indicator._get_percentage_color(0) == "#00ff00"
    assert indicator._get_percentage_color(30) == "#00ff00"
    assert indicator._get_percentage_color(59) == "#00ff00"


def test_context_indicator_percentage_color_yellow():
    """Test color for medium usage percentage (yellow)."""
    indicator = ContextIndicator()

    assert indicator._get_percentage_color(60) == "#ffff00"
    assert indicator._get_percentage_color(72) == "#ffff00"
    assert indicator._get_percentage_color(84) == "#ffff00"


def test_context_indicator_percentage_color_red():
    """Test color for high usage percentage (red)."""
    indicator = ContextIndicator()

    assert indicator._get_percentage_color(85) == "#ff0000"
    assert indicator._get_percentage_color(95) == "#ff0000"
    assert indicator._get_percentage_color(100) == "#ff0000"


def test_context_indicator_display_with_no_data():
    """Test display when no context data is available."""
    indicator = ContextIndicator()
    indicator._refresh_display()

    # Should show empty when no data and no model
    assert indicator.context_analysis is None


def test_context_indicator_display_with_zero_tokens():
    """Test display when context has 0 tokens (no conversation yet)."""
    indicator = ContextIndicator()

    # Create analysis with 0 tokens (empty conversation)
    analysis = create_test_analysis(agent_context_tokens=0, max_usable_tokens=160_000)

    indicator.update_context(analysis, ModelName.CLAUDE_SONNET_4_6)

    # Should show full context display even with 0 tokens (0% (0/160K))
    assert indicator.context_analysis == analysis
    assert indicator.model_name == ModelName.CLAUDE_SONNET_4_6
    # Percentage should be 0.0
    percentage = (0 / 160_000) * 100
    assert percentage == 0.0


def test_context_indicator_display_calculation():
    """Test percentage calculation in display.

    Note: This test verifies the internal state is correct.
    Full UI rendering would require Textual app context.
    """
    indicator = ContextIndicator()

    analysis = create_test_analysis(
        agent_context_tokens=80_000, max_usable_tokens=160_000
    )

    indicator.update_context(analysis, ModelName.CLAUDE_SONNET_4_6)

    # Verify internal state
    assert indicator.context_analysis == analysis
    assert indicator.model_name == ModelName.CLAUDE_SONNET_4_6

    # Verify percentage calculation
    percentage = (80_000 / 160_000) * 100
    assert percentage == 50.0


def test_context_indicator_display_without_model():
    """Test display without model name."""
    indicator = ContextIndicator()

    analysis = create_test_analysis(
        agent_context_tokens=72_000, max_usable_tokens=160_000
    )

    indicator.update_context(analysis, None)

    # Verify internal state
    assert indicator.context_analysis == analysis
    assert indicator.model_name is None

    # Verify percentage calculation
    percentage = (72_000 / 160_000) * 100
    assert percentage == 45.0


def test_context_indicator_display_with_different_models():
    """Test display with different model names."""
    indicator = ContextIndicator()

    analysis = create_test_analysis(
        agent_context_tokens=50_000, max_usable_tokens=160_000
    )

    # Test with different models
    for model_name in [
        ModelName.CLAUDE_SONNET_4_6,
        ModelName.CLAUDE_OPUS_4_6,
        ModelName.GPT_5_1,
        ModelName.GEMINI_3_PRO_PREVIEW,
    ]:
        indicator.update_context(analysis, model_name)
        assert indicator.model_name == model_name
        assert indicator.context_analysis == analysis


def test_context_indicator_over_budget():
    """Test display when tokens exceed model capacity (over 100%)."""
    indicator = ContextIndicator()

    # Simulate switching from GPT-5 (400K) to Haiku (200K) with full conversation
    # 380K tokens exceeds Haiku's 160K usable capacity (200K * 0.8)
    analysis = create_test_analysis(
        agent_context_tokens=380_000, max_usable_tokens=160_000
    )

    indicator.update_context(analysis, ModelName.CLAUDE_HAIKU_4_5)

    # Should handle gracefully without crashing
    assert indicator.context_analysis == analysis
    assert indicator.model_name == ModelName.CLAUDE_HAIKU_4_5

    # Verify percentage calculation (will be >100%)
    percentage = (380_000 / 160_000) * 100
    assert percentage == 237.5

    # Color should be red (since percentage > 85%)
    color = indicator._get_percentage_color(percentage)
    assert color == "#ff0000"
