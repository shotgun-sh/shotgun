"""Test research agent system prompt rendering."""

from unittest.mock import MagicMock

import pytest

from shotgun.agents.common import build_agent_system_prompt
from shotgun.agents.models import AgentDeps


@pytest.fixture
def mock_context():
    """Create mock RunContext for testing."""
    context = MagicMock()
    context.deps = MagicMock(spec=AgentDeps)
    context.deps.interactive_mode = True
    return context


def test_research_system_prompt_renders_correctly(mock_context):
    """Test that the research agent system prompt renders without errors."""
    result = build_agent_system_prompt("research", mock_context)

    # Verify the result is a non-empty string
    assert isinstance(result, str)
    assert len(result) > 0

    # Verify key content is present
    assert "Research Assistant" in result
    # The prompt should contain research-specific instructions
    assert "research" in result.lower()
    assert "artifact" in result.lower()


def test_research_system_prompt_with_interactive_mode_variations(mock_context):
    """Test system prompt rendering with different interactive_mode values."""
    # Test with interactive_mode=True
    mock_context.deps.interactive_mode = True
    result_interactive = build_agent_system_prompt("research", mock_context)
    assert isinstance(result_interactive, str)
    assert len(result_interactive) > 0

    # Test with interactive_mode=False
    mock_context.deps.interactive_mode = False
    result_non_interactive = build_agent_system_prompt("research", mock_context)
    assert isinstance(result_non_interactive, str)
    assert len(result_non_interactive) > 0

    # Both should render successfully
    assert (
        result_interactive != result_non_interactive
    )  # Should be different due to interactive_mode


def test_research_system_prompt_template_loading():
    """Test that the system prompt function loads the correct template."""
    from unittest.mock import patch

    mock_context = MagicMock()
    mock_context.deps.interactive_mode = True

    with patch("shotgun.agents.common.PromptLoader") as mock_loader_class:
        mock_loader = MagicMock()
        mock_loader_class.return_value = mock_loader
        mock_loader.render.return_value = "Test system prompt"

        result = build_agent_system_prompt("research", mock_context)

        # Verify render was called with correct parameters
        mock_loader.render.assert_called_once_with(
            "agents/research.j2",
            interactive_mode=True,
            mode="research",
        )
        assert result == "Test system prompt"
