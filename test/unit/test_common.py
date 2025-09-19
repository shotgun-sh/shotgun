"""Unit tests for agents.common module."""

# type: ignore

from unittest.mock import patch

import pytest
from pydantic_ai import UsageLimits

from shotgun.agents.common import (
    create_base_agent,
    create_usage_limits,
)
from shotgun.agents.models import AgentRuntimeOptions


class TestCreateUsageLimits:
    """Test suite for create_usage_limits function."""

    def test_returns_usage_limits_with_correct_values(self):
        """Test that usage limits are created with expected values."""
        limits = create_usage_limits()

        assert isinstance(limits, UsageLimits)
        assert limits.request_limit == 100
        assert limits.tool_calls_limit == 100

    def test_usage_limits_consistency(self):
        """Test that usage limits are consistent across multiple calls."""
        limits1 = create_usage_limits()
        limits2 = create_usage_limits()

        assert limits1.request_limit == limits2.request_limit
        assert limits1.tool_calls_limit == limits2.tool_calls_limit


class TestCreateBaseAgent:
    """Test suite for create_base_agent function."""

    def test_handles_provider_model_error(self):
        """Test handling of provider model configuration errors."""

        def mock_system_prompt_fn(ctx):
            return "Test system prompt"

        agent_runtime_options = AgentRuntimeOptions(interactive_mode=False)

        with (
            patch("shotgun.agents.common.ensure_shotgun_directory_exists"),
            patch(
                "shotgun.agents.common.get_provider_model",
                side_effect=Exception("Config error"),
            ),
        ):
            with pytest.raises(ValueError, match="Configured model is required"):
                create_base_agent(mock_system_prompt_fn, agent_runtime_options)


class TestPromptTemplateIntegration:
    """Test suite for prompt template integration."""

    def test_interactive_mode_template_rendering(self):
        """Test that templates render correctly for interactive mode."""
        from shotgun.prompts import PromptLoader

        loader = PromptLoader()
        result = loader.render(
            "agents/partials/interactive_mode.j2",
            interactive_mode=True,
        )
        # Interactive mode should show interaction instructions
        assert "IMPORTANT" in result
        assert "USER INTERACTION IS ENABLED" in result

    def test_non_interactive_mode_template_rendering(self):
        """Test that templates render correctly for non-interactive mode."""
        from shotgun.prompts import PromptLoader

        loader = PromptLoader()
        result = loader.render(
            "agents/partials/interactive_mode.j2",
            interactive_mode=False,
        )

        assert "USER INTERACTION IS DISABLED" in result
        assert "non-interactive mode" in result
        assert "ask_user tool" in result

    def test_template_context_variations(self):
        """Test template rendering with various context strings."""
        from shotgun.prompts import PromptLoader

        loader = PromptLoader()
        contexts = ["research output", "plans", "task lists", "documentation"]

        for context in contexts:
            result = loader.render(
                "agents/partials/interactive_mode.j2",
                interactive_mode=False,
            )
            assert "USER INTERACTION IS DISABLED" in result


class TestArtifactSystemIntegration:
    """Test suite for artifact system integration with agents."""

    def test_artifact_tools_importable(self):
        """Test that artifact tools are importable from common module."""
        from shotgun.agents.common import (
            create_artifact,
            list_artifacts,
            read_artifact,
            write_artifact_section,
        )

        # These functions should be importable and callable
        assert callable(create_artifact)
        assert callable(list_artifacts)
        assert callable(read_artifact)
        assert callable(write_artifact_section)

    def test_system_status_message_callable(self):
        """Test that system status message function is callable."""
        from shotgun.agents.common import add_system_status_message

        # Test that the function can be called (it's async so we can't easily test the full flow)
        assert callable(add_system_status_message)

    def test_run_agent_function_callable(self):
        """Test that run_agent function is available."""
        from shotgun.agents.common import run_agent

        assert callable(run_agent)
