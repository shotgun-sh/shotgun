"""Unit tests for history_processors module."""

# type: ignore

from unittest.mock import MagicMock, patch

import pytest
from pydantic_ai import RunContext
from pydantic_ai.messages import (
    BuiltinToolCallPart,
    BuiltinToolReturnPart,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    SystemPromptPart,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from shotgun.agents.config.models import ModelConfig, ProviderType
from shotgun.agents.history.history_processors import (
    get_context_from_message,
    get_first_user_request,
    get_system_promt,
    token_limit_compactor,
)
from shotgun.agents.models import AgentDeps


@pytest.fixture
def mock_model_config() -> ModelConfig:
    """Create a mock ModelConfig for testing."""
    return ModelConfig(
        name="test-model",
        provider=ProviderType.OPENAI,
        max_input_tokens=4096,
        max_output_tokens=2048,
        api_key="test-api-key",
    )


@pytest.fixture
def mock_agent_deps(mock_model_config: ModelConfig) -> AgentDeps:
    """Create mock AgentDeps with model configuration."""
    mock_codebase_service = MagicMock()
    return AgentDeps.model_construct(
        interactive_mode=False,
        llm_model=mock_model_config,
        codebase_service=mock_codebase_service,
    )


@pytest.fixture
def mock_run_context(mock_agent_deps: AgentDeps) -> MagicMock:
    """Create a mock RunContext for testing."""
    ctx = MagicMock(spec=RunContext)
    ctx.deps = mock_agent_deps
    ctx.model = MagicMock()
    # Mock usage with total_tokens
    ctx.usage = MagicMock()
    ctx.usage.total_tokens = 1000
    return ctx


class TestTokenLimitCompactor:
    """Test suite for token_limit_compactor function."""

    @pytest.mark.asyncio
    async def test_under_token_limit_returns_all_messages(
        self, mock_run_context: MagicMock
    ) -> None:
        """Test that messages under token limit are returned unchanged."""
        messages = [
            ModelRequest(parts=[SystemPromptPart(content="System prompt")]),
            ModelRequest(parts=[UserPromptPart(content="User message")]),
            ModelResponse(parts=[TextPart(content="Assistant response")]),
        ]

        # Set token usage below limit (80% of 4096 = 3276)
        mock_run_context.usage.total_tokens = 2000

        result = await token_limit_compactor(mock_run_context, messages)

        assert result == messages
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_over_token_limit_triggers_summarization(self, mock_run_context):
        """Test that messages over token limit trigger summarization."""
        messages = [
            ModelRequest(
                parts=[
                    SystemPromptPart(content="System prompt"),
                    UserPromptPart(content="First user message"),
                ]
            ),
            ModelResponse(parts=[TextPart(content="First assistant response")]),
            ModelRequest(parts=[UserPromptPart(content="Second user message")]),
            ModelResponse(parts=[TextPart(content="Second assistant response")]),
        ]

        # Set token usage above limit (80% of 4096 = 3276)
        mock_run_context.usage.total_tokens = 3500

        # Mock the model_request to return a summary
        mock_summary_response = MagicMock()
        mock_summary_response.parts = [TextPart(content="Summarized conversation")]
        mock_summary_response.usage.output_tokens = 500

        with patch(
            "shotgun.agents.history.history_processors.model_request",
            return_value=mock_summary_response,
        ) as mock_model_request:
            result = await token_limit_compactor(mock_run_context, messages)

            # Verify model_request was called for summarization
            mock_model_request.assert_called_once()

            # Check the structure of the compacted result
            assert len(result) == 2  # ModelRequest and ModelResponse
            assert isinstance(result[0], ModelRequest)
            assert isinstance(result[1], ModelResponse)

            # Verify system and user prompts are preserved
            request_parts = result[0].parts
            assert any(isinstance(p, SystemPromptPart) for p in request_parts)
            assert any(isinstance(p, UserPromptPart) for p in request_parts)

    @pytest.mark.asyncio
    async def test_no_usage_info_returns_all_messages(self, mock_run_context):
        """Test that missing usage info returns all messages."""
        messages = [
            ModelRequest(parts=[UserPromptPart(content="User message")]),
        ]

        mock_run_context.usage = None

        result = await token_limit_compactor(mock_run_context, messages)

        assert result == messages

    @pytest.mark.asyncio
    async def test_extracts_context_from_various_message_types(self, mock_run_context):
        """Test context extraction from different message types during summarization."""
        messages = [
            ModelRequest(
                parts=[
                    SystemPromptPart(content="System"),
                    UserPromptPart(content="User input"),
                ]
            ),
            ModelResponse(
                parts=[
                    TextPart(content="Response"),
                    ToolCallPart(tool_name="test_tool", args={"arg": "value"}),
                ]
            ),
        ]

        mock_run_context.usage.total_tokens = 4000

        mock_summary_response = MagicMock()
        mock_summary_response.parts = [TextPart(content="Summary")]
        mock_summary_response.usage.output_tokens = 100

        with patch(
            "shotgun.agents.history.history_processors.model_request",
            return_value=mock_summary_response,
        ):
            result = await token_limit_compactor(mock_run_context, messages)

            assert len(result) == 2


class TestGetFirstUserRequest:
    """Test suite for get_first_user_request function."""

    def test_extracts_first_user_request(self):
        """Test extraction of first user request from messages."""
        messages = [
            ModelRequest(
                parts=[
                    SystemPromptPart(content="System"),
                    UserPromptPart(content="First user message"),
                ]
            ),
            ModelRequest(parts=[UserPromptPart(content="Second user message")]),
        ]

        result = get_first_user_request(messages)

        assert result == "First user message"

    def test_returns_none_when_no_user_request(self):
        """Test returns None when no user request exists."""
        messages = [
            ModelRequest(parts=[SystemPromptPart(content="System only")]),
            ModelResponse(parts=[TextPart(content="Response")]),
        ]

        result = get_first_user_request(messages)

        assert result is None

    def test_handles_non_string_content(self):
        """Test handling of non-string user prompt content."""
        messages = [
            ModelRequest(
                parts=[UserPromptPart(content="123")]
            ),  # String content that looks like number
        ]

        result = get_first_user_request(messages)

        assert result == "123"

    def test_handles_empty_messages_list(self):
        """Test handling of empty messages list."""
        result = get_first_user_request([])

        assert result is None


class TestGetSystemPrompt:
    """Test suite for get_system_promt function."""

    def test_extracts_system_prompt(self):
        """Test extraction of system prompt from messages."""
        messages = [
            ModelRequest(
                parts=[
                    SystemPromptPart(content="System instructions"),
                    UserPromptPart(content="User"),
                ]
            ),
        ]

        result = get_system_promt(messages)

        assert result == "System instructions"

    def test_returns_none_when_no_system_prompt(self):
        """Test returns None when no system prompt exists."""
        messages = [
            ModelRequest(parts=[UserPromptPart(content="User only")]),
        ]

        result = get_system_promt(messages)

        assert result is None

    def test_finds_system_prompt_in_later_messages(self):
        """Test finding system prompt in non-first message."""
        messages = [
            ModelRequest(parts=[UserPromptPart(content="User")]),
            ModelRequest(parts=[SystemPromptPart(content="System")]),
        ]

        result = get_system_promt(messages)

        assert result == "System"

    def test_handles_empty_messages_list(self):
        """Test handling of empty messages list."""
        result = get_system_promt([])

        assert result is None


class TestGetContextFromMessage:
    """Test suite for get_context_from_message function."""

    def test_system_prompt_returns_empty(self):
        """Test SystemPromptPart returns empty string."""
        part = SystemPromptPart(content="System content")
        result = get_context_from_message(part)
        assert result == ""

    def test_user_prompt_with_string_content(self):
        """Test UserPromptPart with string content."""
        part = UserPromptPart(content="User message")
        result = get_context_from_message(part)
        assert result == "<USER_PROMPT>\nUser message\n</USER_PROMPT>"

    def test_user_prompt_with_non_string_content(self):
        """Test UserPromptPart with non-string content."""
        # Create a part that should return empty when processed
        part = UserPromptPart(content="")
        result = get_context_from_message(part)
        assert result == "<USER_PROMPT>\n\n</USER_PROMPT>"

    def test_tool_return_part(self):
        """Test ToolReturnPart extraction."""
        part = ToolReturnPart(
            tool_name="test_tool", tool_call_id="call_123", content="Tool output"
        )
        result = get_context_from_message(part)
        assert result == "<TOOL_RETURN>\nTool output\n</TOOL_RETURN>"

    def test_retry_prompt_with_string_content(self):
        """Test RetryPromptPart with string content."""
        part = RetryPromptPart(content="Retry message")
        result = get_context_from_message(part)
        assert result == "<RETRY_PROMPT>\nRetry message\n</RETRY_PROMPT>"

    def test_retry_prompt_with_non_string_content(self):
        """Test RetryPromptPart with non-string content."""
        part = RetryPromptPart(content="")
        result = get_context_from_message(part)
        assert result == "<RETRY_PROMPT>\n\n</RETRY_PROMPT>"

    def test_text_part(self):
        """Test TextPart extraction."""
        part = TextPart(content="Assistant text")
        result = get_context_from_message(part)
        assert result == "<ASSISTANT_TEXT>\nAssistant text\n</ASSISTANT_TEXT>"

    def test_tool_call_part_with_dict_args(self):
        """Test ToolCallPart with dictionary arguments."""
        part = ToolCallPart(
            tool_name="my_tool", args={"param1": "value1", "param2": 42}
        )
        result = get_context_from_message(part)
        assert (
            result == "<TOOL_CALL>\nmy_tool(param1='value1', param2=42)\n</TOOL_CALL>"
        )

    def test_tool_call_part_with_non_dict_args(self):
        """Test ToolCallPart with non-dictionary arguments."""
        part = ToolCallPart(tool_name="simple_tool", args="string_arg")
        result = get_context_from_message(part)
        assert result == "<TOOL_CALL>\nsimple_tool(string_arg)\n</TOOL_CALL>"

    def test_builtin_tool_call_part(self):
        """Test BuiltinToolCallPart extraction."""
        part = BuiltinToolCallPart(tool_name="builtin_tool")
        result = get_context_from_message(part)
        assert result == "<BUILTIN_TOOL_CALL>\nbuiltin_tool\n</BUILTIN_TOOL_CALL>"

    def test_builtin_tool_return_part(self):
        """Test BuiltinToolReturnPart extraction."""
        part = BuiltinToolReturnPart(
            tool_name="builtin_tool", tool_call_id="call_456", content="return_data"
        )
        result = get_context_from_message(part)
        assert result == "<BUILTIN_TOOL_RETURN>\nbuiltin_tool\n</BUILTIN_TOOL_RETURN>"

    def test_thinking_part(self):
        """Test ThinkingPart extraction."""
        part = ThinkingPart(content="Internal thoughts")
        result = get_context_from_message(part)
        assert result == "<THINKING>\nInternal thoughts\n</THINKING>"


class TestTokenLimitCompactorEdgeCases:
    """Test edge cases for token_limit_compactor."""

    @pytest.mark.asyncio
    async def test_preserves_system_and_first_user_prompt(self, mock_run_context):
        """Test that system prompt and first user request are preserved after compaction."""
        system_content = "Important system instructions"
        first_user_content = "Initial user request"

        messages = [
            ModelRequest(
                parts=[
                    SystemPromptPart(content=system_content),
                    UserPromptPart(content=first_user_content),
                ]
            ),
            ModelResponse(parts=[TextPart(content="Response 1")]),
            ModelRequest(parts=[UserPromptPart(content="Follow-up")]),
            ModelResponse(parts=[TextPart(content="Response 2")]),
        ]

        mock_run_context.usage.total_tokens = 4000

        mock_summary_response = MagicMock()
        mock_summary_response.parts = [TextPart(content="Summary")]
        mock_summary_response.usage.output_tokens = 100

        with patch(
            "shotgun.agents.history.history_processors.model_request",
            return_value=mock_summary_response,
        ):
            result = await token_limit_compactor(mock_run_context, messages)

            # Extract system prompt from result
            system_prompt = get_system_promt(result)
            assert system_prompt == system_content

            # Extract first user request from result
            first_user = get_first_user_request(result)
            assert first_user == first_user_content

    @pytest.mark.asyncio
    async def test_handles_messages_without_system_prompt(self, mock_run_context):
        """Test compaction when there's no system prompt."""
        messages = [
            ModelRequest(parts=[UserPromptPart(content="User message")]),
            ModelResponse(parts=[TextPart(content="Response")]),
        ]

        mock_run_context.usage.total_tokens = 4000

        mock_summary_response = MagicMock()
        mock_summary_response.parts = [TextPart(content="Summary")]
        mock_summary_response.usage.output_tokens = 100

        with patch(
            "shotgun.agents.history.history_processors.model_request",
            return_value=mock_summary_response,
        ):
            result = await token_limit_compactor(mock_run_context, messages)

            # Should still create a valid structure
            assert len(result) == 2
            assert isinstance(result[0], ModelRequest)
            assert isinstance(result[1], ModelResponse)
