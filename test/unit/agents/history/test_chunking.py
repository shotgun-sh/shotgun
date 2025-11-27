"""Unit tests for chunking module."""

# type: ignore

from unittest.mock import AsyncMock, patch

import pytest
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
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
from shotgun.agents.conversation.history.chunking import (
    Chunk,
    MessageGroup,
    chunk_messages_for_compaction,
    create_chunks,
    identify_message_groups,
)


@pytest.fixture
def mock_model_config() -> ModelConfig:
    """Create a mock ModelConfig for testing."""
    return ModelConfig(
        name=ModelName.GPT_5,
        provider=ProviderType.OPENAI,
        key_provider=KeyProvider.BYOK,
        max_input_tokens=10000,
        max_output_tokens=4096,
        api_key="test-api-key",
    )


@pytest.fixture
def simple_user_message() -> ModelRequest:
    """Create a simple user message."""
    return ModelRequest(parts=[UserPromptPart(content="Hello")])


@pytest.fixture
def simple_assistant_response() -> ModelResponse:
    """Create a simple assistant response (text only)."""
    return ModelResponse(parts=[TextPart(content="Hi there!")])


@pytest.fixture
def tool_call_response() -> ModelResponse:
    """Create an assistant response with a tool call."""
    return ModelResponse(
        parts=[
            ToolCallPart(
                tool_name="file_read",
                args={"path": "/test.txt"},
                tool_call_id="call_123",
            )
        ]
    )


@pytest.fixture
def tool_return_request() -> ModelRequest:
    """Create a request with a tool return."""
    return ModelRequest(
        parts=[
            ToolReturnPart(
                tool_name="file_read",
                tool_call_id="call_123",
                content="File contents here",
            )
        ]
    )


class TestIdentifyMessageGroups:
    """Tests for identify_message_groups function."""

    def test_empty_messages_returns_empty_groups(self):
        """Test that empty message list returns empty groups."""
        groups = identify_message_groups([])
        assert groups == []

    def test_single_user_message_creates_one_group(self, simple_user_message):
        """Test that a single user message creates one group."""
        groups = identify_message_groups([simple_user_message])

        assert len(groups) == 1
        assert groups[0].messages == [simple_user_message]
        assert groups[0].is_tool_sequence is False
        assert groups[0].start_index == 0
        assert groups[0].end_index == 0

    def test_single_assistant_response_creates_one_group(
        self, simple_assistant_response
    ):
        """Test that a standalone assistant response creates one group."""
        groups = identify_message_groups([simple_assistant_response])

        assert len(groups) == 1
        assert groups[0].messages == [simple_assistant_response]
        assert groups[0].is_tool_sequence is False

    def test_tool_call_and_return_stay_together(
        self, tool_call_response, tool_return_request
    ):
        """Test that tool calls and their returns are grouped together."""
        messages = [tool_call_response, tool_return_request]
        groups = identify_message_groups(messages)

        # Should create one group with both messages
        assert len(groups) == 1
        assert groups[0].is_tool_sequence is True
        assert len(groups[0].messages) == 2
        assert groups[0].messages[0] == tool_call_response
        assert groups[0].messages[1] == tool_return_request
        assert groups[0].start_index == 0
        assert groups[0].end_index == 1

    def test_multiple_tool_calls_in_one_response(self):
        """Test handling of multiple tool calls in a single response."""
        # Response with two tool calls
        response = ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="file_read",
                    args={"path": "/a.txt"},
                    tool_call_id="call_1",
                ),
                ToolCallPart(
                    tool_name="file_read",
                    args={"path": "/b.txt"},
                    tool_call_id="call_2",
                ),
            ]
        )

        # First return
        return1 = ModelRequest(
            parts=[
                ToolReturnPart(
                    tool_name="file_read",
                    tool_call_id="call_1",
                    content="Content A",
                )
            ]
        )

        # Second return
        return2 = ModelRequest(
            parts=[
                ToolReturnPart(
                    tool_name="file_read",
                    tool_call_id="call_2",
                    content="Content B",
                )
            ]
        )

        messages = [response, return1, return2]
        groups = identify_message_groups(messages)

        # Should create one group containing all three messages
        assert len(groups) == 1
        assert groups[0].is_tool_sequence is True
        assert len(groups[0].messages) == 3

    def test_mixed_messages_create_separate_groups(
        self, simple_user_message, simple_assistant_response
    ):
        """Test that mixed messages create appropriate groups."""
        messages = [
            simple_user_message,
            simple_assistant_response,
            ModelRequest(parts=[UserPromptPart(content="Another question")]),
        ]

        groups = identify_message_groups(messages)

        assert len(groups) == 3
        # All should be non-tool groups
        assert all(not g.is_tool_sequence for g in groups)

    def test_complex_conversation_grouping(self):
        """Test grouping of a complex conversation with mixed content."""
        messages = [
            # User starts conversation
            ModelRequest(parts=[UserPromptPart(content="Search for files")]),
            # Assistant makes a tool call
            ModelResponse(
                parts=[
                    TextPart(content="Let me search..."),
                    ToolCallPart(
                        tool_name="grep",
                        args={"pattern": "test"},
                        tool_call_id="call_grep",
                    ),
                ]
            ),
            # Tool return
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        tool_name="grep",
                        tool_call_id="call_grep",
                        content="Found 5 matches",
                    )
                ]
            ),
            # Assistant responds with text only
            ModelResponse(parts=[TextPart(content="I found 5 matches.")]),
            # User asks follow-up
            ModelRequest(parts=[UserPromptPart(content="Show me the first one")]),
        ]

        groups = identify_message_groups(messages)

        # Should have 4 groups:
        # 1. User message
        # 2. Tool call sequence (response + return)
        # 3. Text-only response
        # 4. User follow-up
        assert len(groups) == 4

        # Check tool sequence
        tool_group = [g for g in groups if g.is_tool_sequence][0]
        assert len(tool_group.messages) == 2

    def test_system_prompt_not_included_in_groups(self):
        """Test that system prompts are not included as separate groups."""
        messages = [
            ModelRequest(
                parts=[
                    SystemPromptPart(content="You are a helpful assistant"),
                    UserPromptPart(content="Hello"),
                ]
            ),
        ]

        groups = identify_message_groups(messages)

        # The system prompt is part of the ModelRequest, but we're only checking
        # for UserPromptPart to create user groups
        assert len(groups) == 1

    def test_orphaned_tool_return_not_crashed(self):
        """Test that orphaned tool returns don't cause crashes."""
        # Tool return without matching call
        orphaned_return = ModelRequest(
            parts=[
                ToolReturnPart(
                    tool_name="unknown",
                    tool_call_id="orphan_call",
                    content="Orphaned",
                )
            ]
        )

        messages = [orphaned_return]
        # Should not raise an exception
        groups = identify_message_groups(messages)
        # Orphaned returns are silently ignored (handled by filter_orphaned_tool_responses)
        assert len(groups) == 0


class TestMessageGroup:
    """Tests for MessageGroup dataclass."""

    @pytest.mark.asyncio
    async def test_get_token_count_caches_result(self, mock_model_config):
        """Test that token count is cached after first calculation."""
        message = ModelRequest(parts=[UserPromptPart(content="Test message")])
        group = MessageGroup(messages=[message], start_index=0, end_index=0)

        with patch(
            "shotgun.agents.conversation.history.chunking.estimate_tokens_from_messages",
            new_callable=AsyncMock,
            return_value=100,
        ) as mock_estimate:
            # First call
            count1 = await group.get_token_count(mock_model_config)
            assert count1 == 100
            assert mock_estimate.call_count == 1

            # Second call should use cache
            count2 = await group.get_token_count(mock_model_config)
            assert count2 == 100
            assert mock_estimate.call_count == 1  # Still 1, not called again


class TestChunk:
    """Tests for Chunk dataclass."""

    def test_get_all_messages_flattens_groups(self):
        """Test that get_all_messages flattens all messages from groups."""
        msg1 = ModelRequest(parts=[UserPromptPart(content="Message 1")])
        msg2 = ModelResponse(parts=[TextPart(content="Response 1")])
        msg3 = ModelRequest(parts=[UserPromptPart(content="Message 2")])

        group1 = MessageGroup(messages=[msg1, msg2], start_index=0, end_index=1)
        group2 = MessageGroup(messages=[msg3], start_index=2, end_index=2)

        chunk = Chunk(groups=[group1, group2], chunk_index=0)
        all_messages = chunk.get_all_messages()

        assert len(all_messages) == 3
        assert all_messages[0] == msg1
        assert all_messages[1] == msg2
        assert all_messages[2] == msg3

    def test_empty_chunk_returns_empty_list(self):
        """Test that empty chunk returns empty message list."""
        chunk = Chunk(groups=[], chunk_index=0)
        assert chunk.get_all_messages() == []


class TestCreateChunks:
    """Tests for create_chunks function."""

    @pytest.mark.asyncio
    async def test_too_few_groups_returns_all_as_retained(self, mock_model_config):
        """Test that too few groups returns all messages as retained."""
        msg1 = ModelRequest(parts=[UserPromptPart(content="Msg 1")])
        msg2 = ModelResponse(parts=[TextPart(content="Resp 1")])

        groups = [
            MessageGroup(messages=[msg1], start_index=0, end_index=0),
            MessageGroup(messages=[msg2], start_index=1, end_index=1),
        ]

        # With default retention_window=5, 2 groups is too few
        chunks, retained = await create_chunks(groups, mock_model_config)

        assert len(chunks) == 0
        assert len(retained) == 2

    @pytest.mark.asyncio
    async def test_groups_split_into_chunks_by_token_limit(self, mock_model_config):
        """Test that groups are properly split into chunks based on token limits."""
        # Create 10 groups
        groups = []
        for i in range(10):
            msg = ModelRequest(parts=[UserPromptPart(content=f"Message {i}")])
            group = MessageGroup(
                messages=[msg], start_index=i, end_index=i, _token_count=1000
            )
            groups.append(group)

        # With max_input_tokens=10000 and CHUNK_TARGET_RATIO=0.60, max_chunk_tokens=6000
        # Each group is 1000 tokens, so 6 groups per chunk max
        # 10 groups - 5 retained = 5 to chunk -> 1 chunk of 5

        chunks, retained = await create_chunks(
            groups, mock_model_config, retention_window=5
        )

        assert len(chunks) == 1
        assert len(retained) == 5  # 5 retained groups

    @pytest.mark.asyncio
    async def test_oversized_group_becomes_own_chunk(self, mock_model_config):
        """Test that oversized groups become their own chunks."""
        # Create an oversized group (more than 60% of max_input_tokens)
        big_msg = ModelRequest(parts=[UserPromptPart(content="x" * 50000)])
        oversized_group = MessageGroup(
            messages=[big_msg], start_index=0, end_index=0, _token_count=8000
        )

        # Normal groups
        normal_groups = []
        for i in range(6):
            msg = ModelRequest(parts=[UserPromptPart(content=f"Normal {i}")])
            group = MessageGroup(
                messages=[msg],
                start_index=i + 1,
                end_index=i + 1,
                _token_count=500,
            )
            normal_groups.append(group)

        all_groups = [oversized_group] + normal_groups

        chunks, retained = await create_chunks(
            all_groups, mock_model_config, retention_window=2
        )

        # Oversized group should be its own chunk
        # The rest should be chunked together (minus retention window)
        assert len(chunks) >= 1
        # First chunk should be the oversized one alone
        assert len(chunks[0].groups) == 1
        assert chunks[0].total_token_estimate == 8000

    @pytest.mark.asyncio
    async def test_retention_window_respected(self, mock_model_config):
        """Test that the retention window keeps recent messages out of chunks."""
        groups = []
        for i in range(8):
            msg = ModelRequest(parts=[UserPromptPart(content=f"Msg {i}")])
            group = MessageGroup(
                messages=[msg], start_index=i, end_index=i, _token_count=100
            )
            groups.append(group)

        # Retention window of 3
        chunks, retained = await create_chunks(
            groups, mock_model_config, retention_window=3
        )

        # Should have 5 groups to chunk (8 - 3 = 5)
        # And 3 retained messages
        assert len(retained) == 3

        # Total messages in chunks should be 5
        total_chunked = sum(len(c.get_all_messages()) for c in chunks)
        assert total_chunked == 5

    @pytest.mark.asyncio
    async def test_chunk_indices_are_sequential(self, mock_model_config):
        """Test that chunk indices are sequential starting from 0."""
        groups = []
        for i in range(15):
            msg = ModelRequest(parts=[UserPromptPart(content=f"Msg {i}")])
            group = MessageGroup(
                messages=[msg], start_index=i, end_index=i, _token_count=1000
            )
            groups.append(group)

        chunks, _ = await create_chunks(groups, mock_model_config, retention_window=5)

        # Check indices are sequential
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i


class TestChunkMessagesForCompaction:
    """Tests for the main entry point function."""

    @pytest.mark.asyncio
    async def test_integration_simple_conversation(self, mock_model_config):
        """Test chunking a simple conversation end-to-end."""
        messages = [
            ModelRequest(parts=[UserPromptPart(content=f"Question {i}")])
            for i in range(10)
        ]

        with patch(
            "shotgun.agents.conversation.history.chunking.estimate_tokens_from_messages",
            new_callable=AsyncMock,
            return_value=100,
        ):
            chunks, retained = await chunk_messages_for_compaction(
                messages, mock_model_config
            )

        # With 10 messages as 10 groups, 5 retained, 5 to chunk
        assert len(retained) == 5
        # Total messages in chunks should be 5
        total_in_chunks = sum(len(c.get_all_messages()) for c in chunks)
        assert total_in_chunks == 5

    @pytest.mark.asyncio
    async def test_integration_with_tool_sequences(self, mock_model_config):
        """Test chunking preserves tool call sequences."""
        messages = [
            # User
            ModelRequest(parts=[UserPromptPart(content="Read file")]),
            # Tool call
            ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="file_read",
                        args={"path": "/test.txt"},
                        tool_call_id="call_1",
                    )
                ]
            ),
            # Tool return
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        tool_name="file_read",
                        tool_call_id="call_1",
                        content="File content",
                    )
                ]
            ),
            # Text response
            ModelResponse(parts=[TextPart(content="Here's the file content")]),
            # More user messages to ensure we have enough groups
            ModelRequest(parts=[UserPromptPart(content="User 2")]),
            ModelRequest(parts=[UserPromptPart(content="User 3")]),
            ModelRequest(parts=[UserPromptPart(content="User 4")]),
            ModelRequest(parts=[UserPromptPart(content="User 5")]),
            ModelRequest(parts=[UserPromptPart(content="User 6")]),
            ModelRequest(parts=[UserPromptPart(content="User 7")]),
        ]

        with patch(
            "shotgun.agents.conversation.history.chunking.estimate_tokens_from_messages",
            new_callable=AsyncMock,
            return_value=100,
        ):
            chunks, retained = await chunk_messages_for_compaction(
                messages, mock_model_config
            )

        # Verify tool sequence stays together in chunks
        for chunk in chunks:
            all_msgs = chunk.get_all_messages()
            # Check if any tool calls exist in this chunk
            for msg in all_msgs:
                if isinstance(msg, ModelResponse):
                    tool_calls = [p for p in msg.parts if isinstance(p, ToolCallPart)]
                    if tool_calls:
                        # This chunk should also contain the tool returns
                        tool_call_ids = {tc.tool_call_id for tc in tool_calls}
                        # Find tool returns in chunk
                        found_returns = set()
                        for m in all_msgs:
                            if isinstance(m, ModelRequest):
                                for p in m.parts:
                                    if isinstance(p, ToolReturnPart):
                                        found_returns.add(p.tool_call_id)
                        # All tool calls should have returns in same chunk
                        assert tool_call_ids.issubset(found_returns), (
                            "Tool calls and returns should be in same chunk"
                        )

    @pytest.mark.asyncio
    async def test_empty_messages_returns_empty(self, mock_model_config):
        """Test that empty message list returns empty results."""
        chunks, retained = await chunk_messages_for_compaction([], mock_model_config)

        assert chunks == []
        assert retained == []
