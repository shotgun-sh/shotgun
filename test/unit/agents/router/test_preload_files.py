"""Tests for .shotgun/ file preloading on sub-agent delegation."""

from asyncio import Queue
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai.agent import AgentRunResult
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    ToolReturnPart,
)

from shotgun.agents.config.models import KeyProvider, ModelConfig, ProviderType
from shotgun.agents.models import (
    AgentResponse,
    AgentType,
    FileOperationTracker,
)
from shotgun.agents.router.models import (
    DelegationInput,
    DelegationResult,
    RouterDeps,
    RouterMode,
)
from shotgun.agents.router.tools.delegation_tools import (
    _run_sub_agent,
    build_preloaded_history,
    delegate_to_specification,
)

# =============================================================================
# Tests for build_preloaded_history
# =============================================================================


@pytest.mark.asyncio
async def test_build_preloaded_history_empty_list():
    """Empty preload_files list returns empty history and paths."""
    messages, loaded = await build_preloaded_history([])
    assert messages == []
    assert loaded == []


@pytest.mark.asyncio
async def test_build_preloaded_history_single_file(tmp_path):
    """Single file creates correct read_file call/return pair."""
    # Create a test file
    shotgun_dir = tmp_path / ".shotgun"
    shotgun_dir.mkdir()
    test_file = shotgun_dir / "research.md"
    test_file.write_text("# Research\nSome findings here.")

    with patch(
        "shotgun.agents.router.tools.delegation_tools.get_shotgun_base_path",
        return_value=shotgun_dir,
    ):
        messages, loaded = await build_preloaded_history(["research.md"])

    assert loaded == ["research.md"]
    assert len(messages) == 2

    # First message: ModelResponse with ToolCallPart
    call_msg = messages[0]
    assert isinstance(call_msg, ModelResponse)
    assert len(call_msg.parts) == 1
    call_part = call_msg.parts[0]
    assert isinstance(call_part, ToolCallPart)
    assert call_part.tool_name == "read_file"
    assert call_part.args == {
        "filename": "research.md",
        "reason": "Preloaded by router",
    }
    assert call_part.tool_call_id is not None
    assert call_part.tool_call_id.startswith("preload-")

    # Second message: ModelRequest with ToolReturnPart
    return_msg = messages[1]
    assert isinstance(return_msg, ModelRequest)
    assert len(return_msg.parts) == 1
    return_part = return_msg.parts[0]
    assert isinstance(return_part, ToolReturnPart)
    assert return_part.tool_name == "read_file"
    assert return_part.content == "# Research\nSome findings here."
    assert return_part.tool_call_id == call_part.tool_call_id


@pytest.mark.asyncio
async def test_build_preloaded_history_multiple_files(tmp_path):
    """Multiple files each get their own call/return pair."""
    shotgun_dir = tmp_path / ".shotgun"
    shotgun_dir.mkdir()
    (shotgun_dir / "research.md").write_text("Research content")
    (shotgun_dir / "specification.md").write_text("Spec content")

    with patch(
        "shotgun.agents.router.tools.delegation_tools.get_shotgun_base_path",
        return_value=shotgun_dir,
    ):
        messages, loaded = await build_preloaded_history(
            ["research.md", "specification.md"]
        )

    assert loaded == ["research.md", "specification.md"]
    assert len(messages) == 4  # 2 pairs

    # Check second pair has spec content
    return_part = messages[3].parts[0]
    assert isinstance(return_part, ToolReturnPart)
    assert return_part.content == "Spec content"


@pytest.mark.asyncio
async def test_build_preloaded_history_nonexistent_file_skipped(tmp_path):
    """Non-existent files are silently skipped."""
    shotgun_dir = tmp_path / ".shotgun"
    shotgun_dir.mkdir()
    (shotgun_dir / "research.md").write_text("Research content")

    with patch(
        "shotgun.agents.router.tools.delegation_tools.get_shotgun_base_path",
        return_value=shotgun_dir,
    ):
        messages, loaded = await build_preloaded_history(
            ["research.md", "nonexistent.md"]
        )

    assert loaded == ["research.md"]
    assert len(messages) == 2  # Only 1 pair for existing file


@pytest.mark.asyncio
async def test_build_preloaded_history_directory_skipped(tmp_path):
    """Directories are silently skipped."""
    shotgun_dir = tmp_path / ".shotgun"
    shotgun_dir.mkdir()
    (shotgun_dir / "contracts").mkdir()

    with patch(
        "shotgun.agents.router.tools.delegation_tools.get_shotgun_base_path",
        return_value=shotgun_dir,
    ):
        messages, loaded = await build_preloaded_history(["contracts"])

    assert loaded == []
    assert messages == []


@pytest.mark.asyncio
async def test_build_preloaded_history_tool_call_id_matches():
    """Tool call ID must match between call and return parts."""
    # Already tested in single_file test, but let's be explicit
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        shotgun_dir = Path(tmp) / ".shotgun"
        shotgun_dir.mkdir()
        (shotgun_dir / "plan.md").write_text("Plan content")

        with patch(
            "shotgun.agents.router.tools.delegation_tools.get_shotgun_base_path",
            return_value=shotgun_dir,
        ):
            messages, loaded = await build_preloaded_history(["plan.md"])

    call_part = messages[0].parts[0]
    return_part = messages[1].parts[0]
    assert isinstance(call_part, ToolCallPart)
    assert isinstance(return_part, ToolReturnPart)
    assert call_part.tool_call_id == return_part.tool_call_id


@pytest.mark.asyncio
async def test_build_preloaded_history_subdirectory_files(tmp_path):
    """Files in subdirectories (e.g., contracts/auth.py) work correctly."""
    shotgun_dir = tmp_path / ".shotgun"
    shotgun_dir.mkdir()
    contracts_dir = shotgun_dir / "contracts"
    contracts_dir.mkdir()
    (contracts_dir / "auth.py").write_text("class AuthContract: pass")

    with patch(
        "shotgun.agents.router.tools.delegation_tools.get_shotgun_base_path",
        return_value=shotgun_dir,
    ):
        messages, loaded = await build_preloaded_history(["contracts/auth.py"])

    assert loaded == ["contracts/auth.py"]
    return_part = messages[1].parts[0]
    assert isinstance(return_part, ToolReturnPart)
    assert return_part.content == "class AuthContract: pass"


# =============================================================================
# Tests for DelegationInput backward compatibility
# =============================================================================


def test_delegation_input_default_preload_files():
    """DelegationInput.preload_files defaults to empty list (backward compat)."""
    input_data = DelegationInput(task="Test task")
    assert input_data.preload_files == []


def test_delegation_input_with_preload_files():
    """DelegationInput accepts preload_files."""
    input_data = DelegationInput(
        task="Write spec",
        preload_files=["research.md"],
    )
    assert input_data.preload_files == ["research.md"]


# =============================================================================
# Tests for DelegationResult.files_preloaded
# =============================================================================


def test_delegation_result_default_files_preloaded():
    """DelegationResult.files_preloaded defaults to empty list."""
    result = DelegationResult(success=True, response="Done")
    assert result.files_preloaded == []


def test_delegation_result_with_files_preloaded():
    """DelegationResult accepts files_preloaded."""
    result = DelegationResult(
        success=True,
        response="Done",
        files_preloaded=["research.md", "specification.md"],
    )
    assert result.files_preloaded == ["research.md", "specification.md"]


# =============================================================================
# Tests for _run_sub_agent with preload_files
# =============================================================================


def _create_mock_sub_agent_deps():
    """Helper to create properly configured mock sub-agent deps."""
    mock_sub_deps = MagicMock()
    mock_sub_deps.file_tracker = FileOperationTracker()
    mock_sub_deps.sub_agent_context = None
    return mock_sub_deps


def _create_mock_router_deps():
    """Helper to create mock RouterDeps."""
    deps = MagicMock(spec=RouterDeps)
    deps.router_mode = RouterMode.DRAFTING
    deps.current_plan = None
    deps.file_tracker = FileOperationTracker()
    deps.active_sub_agent = None
    deps.sub_agent_cache = {}
    deps.interactive_mode = True
    deps.working_directory = Path("/test/dir")
    deps.is_tui_context = True
    deps.max_iterations = 100
    deps.queue = Queue()
    deps.tasks = []
    deps.parent_stream_handler = None
    deps.pending_approval = None
    deps.cancellation_event = None
    deps.usage_manager = MagicMock()
    deps.usage_manager.add_usage = AsyncMock()
    deps.sub_agent_tool_calls = {}
    deps.llm_model = ModelConfig(
        name="test-model",
        provider=ProviderType.OPENAI_COMPATIBLE,
        key_provider=KeyProvider.BYOK,
        max_input_tokens=128000,
        max_output_tokens=16000,
        api_key="test-key",
    )
    return deps


@pytest.mark.asyncio
async def test_run_sub_agent_passes_preloaded_history(tmp_path):
    """_run_sub_agent passes preloaded history as message_history."""
    # Set up shotgun directory with a file
    shotgun_dir = tmp_path / ".shotgun"
    shotgun_dir.mkdir()
    (shotgun_dir / "research.md").write_text("Research findings")

    deps = _create_mock_router_deps()
    mock_agent = MagicMock()
    mock_sub_deps = _create_mock_sub_agent_deps()

    mock_result = MagicMock(spec=AgentRunResult)
    mock_result.output = AgentResponse(response="Done")

    captured_kwargs = {}

    async def capture_run_kwargs(*args, **kwargs):
        captured_kwargs.update(kwargs)
        return mock_result

    from pydantic_ai import RunContext

    ctx = MagicMock(spec=RunContext)
    ctx.deps = deps

    with (
        patch.dict(
            "shotgun.agents.router.tools.delegation_tools.AGENT_FACTORIES",
            {
                AgentType.RESEARCH: (
                    AsyncMock(return_value=(mock_agent, mock_sub_deps)),
                    capture_run_kwargs,
                )
            },
        ),
        patch(
            "shotgun.agents.router.tools.delegation_tools.get_shotgun_base_path",
            return_value=shotgun_dir,
        ),
    ):
        result = await _run_sub_agent(
            ctx,
            AgentType.RESEARCH,
            "Test task",
            preload_files=["research.md"],
        )

    assert result.success is True
    assert result.files_preloaded == ["research.md"]
    # Verify the message_history was passed with preloaded content
    assert "message_history" in captured_kwargs
    history = captured_kwargs["message_history"]
    assert len(history) == 2
    assert isinstance(history[0], ModelResponse)
    assert isinstance(history[1], ModelRequest)


@pytest.mark.asyncio
async def test_run_sub_agent_no_preload_files_empty_history():
    """_run_sub_agent with no preload_files passes empty message_history."""
    deps = _create_mock_router_deps()
    mock_agent = MagicMock()
    mock_sub_deps = _create_mock_sub_agent_deps()

    mock_result = MagicMock(spec=AgentRunResult)
    mock_result.output = AgentResponse(response="Done")

    captured_kwargs = {}

    async def capture_run_kwargs(*args, **kwargs):
        captured_kwargs.update(kwargs)
        return mock_result

    from pydantic_ai import RunContext

    ctx = MagicMock(spec=RunContext)
    ctx.deps = deps

    with patch.dict(
        "shotgun.agents.router.tools.delegation_tools.AGENT_FACTORIES",
        {
            AgentType.RESEARCH: (
                AsyncMock(return_value=(mock_agent, mock_sub_deps)),
                capture_run_kwargs,
            )
        },
    ):
        result = await _run_sub_agent(
            ctx,
            AgentType.RESEARCH,
            "Test task",
        )

    assert result.success is True
    assert result.files_preloaded == []
    assert captured_kwargs["message_history"] == []


@pytest.mark.asyncio
async def test_delegate_to_specification_passes_preload_files():
    """delegate_to_specification forwards preload_files to _run_sub_agent."""
    from pydantic_ai import RunContext

    ctx = MagicMock(spec=RunContext)
    ctx.deps = _create_mock_router_deps()

    with patch(
        "shotgun.agents.router.tools.delegation_tools._run_sub_agent",
        new_callable=AsyncMock,
        return_value=DelegationResult(success=True, response="Spec done"),
    ) as mock_run:
        input_data = DelegationInput(
            task="Write auth spec",
            preload_files=["research.md"],
        )
        result = await delegate_to_specification(ctx, input_data)

    mock_run.assert_called_once_with(
        ctx,
        AgentType.SPECIFY,
        "Write auth spec",
        None,
        ["research.md"],
    )
    assert result.success is True
