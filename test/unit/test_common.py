"""Unit tests for agents.common module."""

# type: ignore

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic_ai import Agent, UsageLimits

from shotgun.agents.common import (
    create_base_agent,
    create_usage_limits,
    ensure_file_exists,
    get_file_history,
    register_common_tools,
)
from shotgun.agents.config.models import ModelConfig, ProviderType
from shotgun.agents.models import AgentDeps, AgentRuntimeOptions


class TestEnsureFileExists:
    """Test suite for ensure_file_exists function."""

    def test_creates_new_file_with_header(self):
        """Test creating a new file with header."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Change to temp directory
            original_cwd = Path.cwd()
            try:
                import os

                os.chdir(temp_dir)

                result = ensure_file_exists("test.md", "# Test Header")

                # Check the result
                expected_content = "# Test Header\n\n"
                assert result == expected_content

                # Check the file was created
                shotgun_dir = Path(temp_dir) / ".shotgun"
                file_path = shotgun_dir / "test.md"
                assert file_path.exists()
                assert file_path.read_text(encoding="utf-8") == expected_content

            finally:
                os.chdir(original_cwd)

    def test_returns_existing_file_content(self):
        """Test returning content from existing file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = Path.cwd()
            try:
                import os

                os.chdir(temp_dir)

                # Create the .shotgun directory and file
                shotgun_dir = Path(temp_dir) / ".shotgun"
                shotgun_dir.mkdir()
                file_path = shotgun_dir / "existing.md"
                existing_content = "# Existing Content\n\nSome text here."
                file_path.write_text(existing_content, encoding="utf-8")

                result = ensure_file_exists("existing.md", "# New Header")

                # Should return existing content, not create new
                assert result == existing_content

            finally:
                os.chdir(original_cwd)

    def test_adds_header_to_empty_file(self):
        """Test adding header to existing but empty file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = Path.cwd()
            try:
                import os

                os.chdir(temp_dir)

                # Create empty file
                shotgun_dir = Path(temp_dir) / ".shotgun"
                shotgun_dir.mkdir()
                file_path = shotgun_dir / "empty.md"
                file_path.write_text("", encoding="utf-8")

                result = ensure_file_exists("empty.md", "# Added Header")

                expected_content = "# Added Header\n\n"
                assert result == expected_content
                assert file_path.read_text(encoding="utf-8") == expected_content

            finally:
                os.chdir(original_cwd)

    def test_handles_file_operation_error(self):
        """Test handling file operation errors."""
        with patch("pathlib.Path.exists", side_effect=Exception("File error")):
            result = ensure_file_exists("error.md", "# Error Header")

            # Should return header content as fallback
            assert result == "# Error Header\n\n"


class TestPromptTemplateIntegration:
    """Test suite for prompt template integration."""

    def test_interactive_mode_template_rendering(self):
        """Test that templates render correctly for interactive mode."""
        from shotgun.prompts import PromptLoader

        loader = PromptLoader()
        result = loader.render(
            "agents/partials/interactive_mode.j2",
            interactive_mode=True,
            context="test context"
        )
        # Interactive mode should render empty (no warning)
        assert result.strip() == ""

    def test_non_interactive_mode_template_rendering(self):
        """Test that templates render correctly for non-interactive mode."""
        from shotgun.prompts import PromptLoader

        loader = PromptLoader()
        result = loader.render(
            "agents/partials/interactive_mode.j2",
            interactive_mode=False,
            context="research output"
        )

        assert "USER INTERACTION IS DISABLED" in result
        assert "non-interactive mode" in result
        assert "ask_user tool" in result
        assert "research output" in result


class TestRegisterCommonTools:
    """Test suite for register_common_tools function."""

    def test_registers_additional_tools(self):
        """Test registration of additional tools."""
        mock_agent = MagicMock(spec=Agent)
        mock_tool1 = MagicMock()
        mock_tool2 = MagicMock()
        additional_tools = [mock_tool1, mock_tool2]

        register_common_tools(mock_agent, additional_tools, False)

        # Verify additional tools were registered
        assert mock_agent.tool_plain.call_count >= 2
        mock_agent.tool_plain.assert_any_call(mock_tool1)
        mock_agent.tool_plain.assert_any_call(mock_tool2)

    def test_registers_interactive_tool_when_enabled(self):
        """Test registration of ask_user tool when interactive mode enabled."""
        mock_agent = MagicMock(spec=Agent)

        with patch("shotgun.agents.common.ask_user") as mock_ask_user:
            register_common_tools(mock_agent, [], True)
            mock_agent.tool.assert_any_call(mock_ask_user)

    def test_skips_interactive_tool_when_disabled(self):
        """Test that ask_user tool is not registered when interactive mode disabled."""
        mock_agent = MagicMock(spec=Agent)

        with patch("shotgun.agents.common.ask_user") as mock_ask_user:
            register_common_tools(mock_agent, [], False)
            # ask_user should not be registered with either tool or tool_plain
            if mock_agent.tool.call_args_list:
                calls = [call.args[0] for call in mock_agent.tool.call_args_list]
                assert mock_ask_user not in calls
            # Also verify it wasn't called at all
            mock_agent.tool.assert_not_called()

    def test_always_registers_file_management_tools(self):
        """Test that file management tools are always registered."""
        mock_agent = MagicMock(spec=Agent)

        with (
            patch("shotgun.agents.common.read_file") as mock_read_file,
            patch("shotgun.agents.common.write_file") as mock_write_file,
            patch("shotgun.agents.common.append_file") as mock_append_file,
        ):
            register_common_tools(mock_agent, [], False)

            mock_agent.tool_plain.assert_any_call(mock_read_file)
            mock_agent.tool_plain.assert_any_call(mock_write_file)
            mock_agent.tool_plain.assert_any_call(mock_append_file)


class TestCreateBaseAgent:
    """Test suite for create_base_agent function."""

    @pytest.fixture
    def mock_model_config(self):
        """Create a mock ModelConfig for testing."""
        return ModelConfig(
            name="test-model",
            provider=ProviderType.OPENAI,
            max_input_tokens=4096,
            max_output_tokens=2048,
        )

    @pytest.fixture
    def mock_agent_runtime_options(self):
        """Create mock AgentRuntimeOptions for testing."""
        return AgentRuntimeOptions(interactive_mode=False)

    @pytest.fixture
    def mock_system_prompt_fn(self):
        """Create a mock system prompt function."""

        def system_prompt_fn(ctx):
            return "Test system prompt"

        return system_prompt_fn

    def test_creates_agent_with_model_config(
        self, mock_model_config, mock_agent_runtime_options, mock_system_prompt_fn
    ):
        """Test successful agent creation with model configuration."""
        with (
            patch("shotgun.agents.common.ensure_shotgun_directory_exists"),
            patch(
                "shotgun.agents.common.get_provider_model",
                return_value=mock_model_config,
            ),
            patch("shotgun.agents.common.get_config_manager") as mock_config_mgr,
            patch("shotgun.agents.common.Agent") as mock_agent_class,
        ):
            # Mock config manager
            mock_config = MagicMock()
            mock_config.default_provider = ProviderType.OPENAI
            mock_config_mgr.return_value.load.return_value = mock_config

            # Mock Agent instance
            mock_agent_instance = MagicMock()
            mock_agent_class.return_value = mock_agent_instance

            agent, deps = create_base_agent(
                mock_system_prompt_fn, mock_agent_runtime_options
            )

            # Verify agent was created with correct model
            mock_agent_class.assert_called_once()
            args, kwargs = mock_agent_class.call_args
            assert args[0] == mock_model_config.pydantic_model_name
            assert kwargs["deps_type"] == AgentDeps
            assert kwargs["instrument"] is True

            # Verify system prompt was registered
            mock_agent_instance.system_prompt.assert_called_once_with(
                mock_system_prompt_fn
            )

            # Verify dependencies were created correctly
            assert isinstance(deps, AgentDeps)
            assert deps.llm_model == mock_model_config

    def test_handles_provider_model_error(
        self, mock_agent_runtime_options, mock_system_prompt_fn
    ):
        """Test handling of provider model configuration errors."""
        with (
            patch("shotgun.agents.common.ensure_shotgun_directory_exists"),
            patch(
                "shotgun.agents.common.get_provider_model",
                side_effect=Exception("Config error"),
            ),
        ):
            with pytest.raises(ValueError, match="Configured model is required"):
                create_base_agent(mock_system_prompt_fn, mock_agent_runtime_options)

    def test_registers_additional_tools(
        self, mock_model_config, mock_agent_runtime_options, mock_system_prompt_fn
    ):
        """Test registration of additional tools."""
        mock_tool = MagicMock()
        additional_tools = [mock_tool]

        with (
            patch("shotgun.agents.common.ensure_shotgun_directory_exists"),
            patch(
                "shotgun.agents.common.get_provider_model",
                return_value=mock_model_config,
            ),
            patch("shotgun.agents.common.get_config_manager") as mock_config_mgr,
            patch("shotgun.agents.common.Agent") as mock_agent_class,
        ):
            mock_config = MagicMock()
            mock_config.default_provider = ProviderType.OPENAI
            mock_config_mgr.return_value.load.return_value = mock_config

            mock_agent_instance = MagicMock()
            mock_agent_class.return_value = mock_agent_instance

            agent, deps = create_base_agent(
                mock_system_prompt_fn,
                mock_agent_runtime_options,
                additional_tools=additional_tools,
            )

            # Verify additional tool was registered
            mock_agent_instance.tool_plain.assert_any_call(mock_tool)

    def test_interactive_mode_registers_ask_user(
        self, mock_model_config, mock_system_prompt_fn
    ):
        """Test that interactive mode registers ask_user tool."""
        interactive_agent_runtime_options = AgentRuntimeOptions(interactive_mode=True)

        with (
            patch("shotgun.agents.common.ensure_shotgun_directory_exists"),
            patch(
                "shotgun.agents.common.get_provider_model",
                return_value=mock_model_config,
            ),
            patch("shotgun.agents.common.get_config_manager") as mock_config_mgr,
            patch("shotgun.agents.common.Agent") as mock_agent_class,
            patch("shotgun.agents.common.ask_user") as mock_ask_user,
        ):
            mock_config = MagicMock()
            mock_config.default_provider = ProviderType.OPENAI
            mock_config_mgr.return_value.load.return_value = mock_config

            mock_agent_instance = MagicMock()
            mock_agent_class.return_value = mock_agent_instance

            agent, deps = create_base_agent(
                mock_system_prompt_fn, interactive_agent_runtime_options
            )

            # Verify ask_user was registered
            mock_agent_instance.tool.assert_any_call(mock_ask_user)
            assert deps.interactive_mode is True


class TestCreateUsageLimits:
    """Test suite for create_usage_limits function."""

    def test_returns_usage_limits_with_correct_values(self):
        """Test that usage limits are created with expected values."""
        limits = create_usage_limits()

        assert isinstance(limits, UsageLimits)
        assert limits.request_limit == 100
        assert limits.tool_calls_limit == 100


class TestGetFileHistory:
    """Test suite for get_file_history function."""

    def test_returns_file_content_on_success(self):
        """Test returning file content when read_file succeeds."""
        expected_content = "File content here"

        with patch("shotgun.agents.common.read_file", return_value=expected_content):
            result = get_file_history("test.md")
            assert result == expected_content

    def test_returns_fallback_message_on_error(self):
        """Test returning fallback message when read_file fails."""
        with patch(
            "shotgun.agents.common.read_file", side_effect=Exception("File not found")
        ):
            result = get_file_history("missing.md")

            expected = "No missing history available."
            assert result == expected

    def test_removes_md_extension_in_fallback_message(self):
        """Test that .md extension is removed in fallback message."""
        with patch("shotgun.agents.common.read_file", side_effect=Exception("Error")):
            result = get_file_history("research.md")

            assert "No research history available." == result
            assert ".md" not in result.replace("research.md", "research")


class TestIntegrationScenarios:
    """Integration test scenarios for common.py functions."""

    def test_file_workflow_integration(self):
        """Test the complete file workflow."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = Path.cwd()
            try:
                import os

                os.chdir(temp_dir)

                # First ensure file exists
                content1 = ensure_file_exists("workflow.md", "# Workflow")
                assert content1 == "# Workflow\n\n"

                # File should exist now, so subsequent calls return content
                content2 = ensure_file_exists("workflow.md", "# Different Header")
                assert content2 == "# Workflow\n\n"  # Original content preserved

            finally:
                os.chdir(original_cwd)

    def test_template_context_variations(self):
        """Test template rendering with various context strings."""
        from shotgun.prompts import PromptLoader

        loader = PromptLoader()
        contexts = ["research output", "plans", "task lists", "documentation"]

        for context in contexts:
            result = loader.render(
                "agents/partials/interactive_mode.j2",
                interactive_mode=False,
                context=context
            )
            assert context in result
            assert "USER INTERACTION IS DISABLED" in result

    def test_usage_limits_consistency(self):
        """Test that usage limits are consistent across multiple calls."""
        limits1 = create_usage_limits()
        limits2 = create_usage_limits()

        assert limits1.request_limit == limits2.request_limit
        assert limits1.tool_calls_limit == limits2.tool_calls_limit
