"""Unit tests for integrated graph open flow (Stage 1 + Stage 2)."""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from shotgun.agents.config.models import PersistentGraphOpenBehavior
from shotgun.codebase.graph_decision import GraphOpenAction
from shotgun.codebase.graph_open_flow import determine_graph_action_for_codebase
from shotgun.codebase.models import CodebaseGraph, GraphStatus


@pytest.fixture
def mock_graph_manager():
    """Create a mock CodebaseGraphManager."""
    return Mock()


@pytest.fixture
def mock_config_manager():
    """Create a mock ConfigManager."""
    manager = Mock()
    manager.get_persistent_graph_behavior = AsyncMock(
        return_value=PersistentGraphOpenBehavior.ASK
    )
    return manager


@pytest.fixture
def mock_existing_graph():
    """Create a mock existing graph."""
    return CodebaseGraph(
        graph_id="test123graph",
        repo_path="/home/user/my-repo",
        graph_path="/storage/test123graph.kuzu",
        name="My Repo",
        created_at=1234567890.0,
        updated_at=1234567890.0,
        status=GraphStatus.READY,
    )


@pytest.mark.asyncio
async def test_flow_with_no_existing_graph(
    mock_graph_manager, mock_config_manager
):
    """Test flow when no graph exists for the path."""
    with patch(
        "shotgun.codebase.graph_open_flow.resolve_canonical_path"
    ) as mock_resolve, patch(
        "shotgun.codebase.graph_open_flow.lookup_graph_for_path"
    ) as mock_lookup:
        mock_resolve.return_value = "/home/user/my-repo"
        mock_lookup.return_value = None

        decision = await determine_graph_action_for_codebase(
            "/home/user/my-repo",
            mock_graph_manager,
            mock_config_manager,
        )

        assert decision.action == GraphOpenAction.NEW
        assert decision.existing_graph is None
        mock_resolve.assert_called_once()
        mock_lookup.assert_called_once()


@pytest.mark.asyncio
async def test_flow_with_always_reuse_behavior(
    mock_graph_manager, mock_config_manager, mock_existing_graph
):
    """Test flow with ALWAYS_REUSE behavior and existing graph."""
    mock_config_manager.get_persistent_graph_behavior = AsyncMock(
        return_value=PersistentGraphOpenBehavior.ALWAYS_REUSE
    )

    with patch(
        "shotgun.codebase.graph_open_flow.resolve_canonical_path"
    ) as mock_resolve, patch(
        "shotgun.codebase.graph_open_flow.lookup_graph_for_path"
    ) as mock_lookup:
        mock_resolve.return_value = "/home/user/my-repo"
        mock_lookup.return_value = mock_existing_graph

        decision = await determine_graph_action_for_codebase(
            "/home/user/my-repo",
            mock_graph_manager,
            mock_config_manager,
        )

        assert decision.action == GraphOpenAction.REUSE
        assert decision.existing_graph == mock_existing_graph


@pytest.mark.asyncio
async def test_flow_with_always_new_behavior(
    mock_graph_manager, mock_config_manager, mock_existing_graph
):
    """Test flow with ALWAYS_NEW behavior and existing graph."""
    mock_config_manager.get_persistent_graph_behavior = AsyncMock(
        return_value=PersistentGraphOpenBehavior.ALWAYS_NEW
    )

    with patch(
        "shotgun.codebase.graph_open_flow.resolve_canonical_path"
    ) as mock_resolve, patch(
        "shotgun.codebase.graph_open_flow.lookup_graph_for_path"
    ) as mock_lookup:
        mock_resolve.return_value = "/home/user/my-repo"
        mock_lookup.return_value = mock_existing_graph

        decision = await determine_graph_action_for_codebase(
            "/home/user/my-repo",
            mock_graph_manager,
            mock_config_manager,
        )

        assert decision.action == GraphOpenAction.NEW
        assert decision.existing_graph == mock_existing_graph


@pytest.mark.asyncio
async def test_flow_with_ask_behavior(
    mock_graph_manager, mock_config_manager, mock_existing_graph
):
    """Test flow with ASK behavior and existing graph."""
    mock_config_manager.get_persistent_graph_behavior = AsyncMock(
        return_value=PersistentGraphOpenBehavior.ASK
    )

    with patch(
        "shotgun.codebase.graph_open_flow.resolve_canonical_path"
    ) as mock_resolve, patch(
        "shotgun.codebase.graph_open_flow.lookup_graph_for_path"
    ) as mock_lookup:
        mock_resolve.return_value = "/home/user/my-repo"
        mock_lookup.return_value = mock_existing_graph

        decision = await determine_graph_action_for_codebase(
            "/home/user/my-repo",
            mock_graph_manager,
            mock_config_manager,
        )

        assert decision.action == GraphOpenAction.ASK
        assert decision.existing_graph == mock_existing_graph


@pytest.mark.asyncio
async def test_flow_with_behavior_override(
    mock_graph_manager, mock_config_manager, mock_existing_graph
):
    """Test flow with explicit behavior override (doesn't read from config)."""
    with patch(
        "shotgun.codebase.graph_open_flow.resolve_canonical_path"
    ) as mock_resolve, patch(
        "shotgun.codebase.graph_open_flow.lookup_graph_for_path"
    ) as mock_lookup:
        mock_resolve.return_value = "/home/user/my-repo"
        mock_lookup.return_value = mock_existing_graph

        decision = await determine_graph_action_for_codebase(
            "/home/user/my-repo",
            mock_graph_manager,
            mock_config_manager,
            global_behavior=PersistentGraphOpenBehavior.ALWAYS_REUSE,
        )

        assert decision.action == GraphOpenAction.REUSE
        # Config manager should not be called when behavior is provided
        mock_config_manager.get_persistent_graph_behavior.assert_not_called()


@pytest.mark.asyncio
async def test_flow_with_relative_path(mock_graph_manager, mock_config_manager):
    """Test flow with relative path (should be canonicalized)."""
    with patch(
        "shotgun.codebase.graph_open_flow.resolve_canonical_path"
    ) as mock_resolve, patch(
        "shotgun.codebase.graph_open_flow.lookup_graph_for_path"
    ) as mock_lookup:
        mock_resolve.return_value = "/home/user/absolute/path"
        mock_lookup.return_value = None

        decision = await determine_graph_action_for_codebase(
            "./relative/path",
            mock_graph_manager,
            mock_config_manager,
        )

        # Should call resolve with the relative path
        mock_resolve.assert_called_once_with("./relative/path")
        # Should call lookup with the canonicalized path
        mock_lookup.assert_called_once_with(
            "/home/user/absolute/path", mock_graph_manager
        )


@pytest.mark.asyncio
async def test_flow_with_path_object(mock_graph_manager, mock_config_manager):
    """Test flow with Path object instead of string."""
    path = Path("/home/user/my-repo")

    with patch(
        "shotgun.codebase.graph_open_flow.resolve_canonical_path"
    ) as mock_resolve, patch(
        "shotgun.codebase.graph_open_flow.lookup_graph_for_path"
    ) as mock_lookup:
        mock_resolve.return_value = str(path)
        mock_lookup.return_value = None

        decision = await determine_graph_action_for_codebase(
            path,
            mock_graph_manager,
            mock_config_manager,
        )

        assert decision.action == GraphOpenAction.NEW
        mock_resolve.assert_called_once_with(path)


@pytest.mark.asyncio
async def test_flow_without_config_manager(mock_graph_manager):
    """Test flow without providing config manager (uses global singleton)."""
    with patch(
        "shotgun.codebase.graph_open_flow.resolve_canonical_path"
    ) as mock_resolve, patch(
        "shotgun.codebase.graph_open_flow.lookup_graph_for_path"
    ) as mock_lookup, patch(
        "shotgun.agents.config.manager.get_config_manager"
    ) as mock_get_manager:
        mock_resolve.return_value = "/home/user/my-repo"
        mock_lookup.return_value = None

        # Mock the global config manager
        mock_manager = Mock()
        mock_manager.get_persistent_graph_behavior = AsyncMock(
            return_value=PersistentGraphOpenBehavior.ASK
        )
        mock_get_manager.return_value = mock_manager

        decision = await determine_graph_action_for_codebase(
            "/home/user/my-repo",
            mock_graph_manager,
            config_manager=None,  # Force use of global singleton
        )

        assert decision.action == GraphOpenAction.NEW
        # Should have called get_config_manager
        mock_get_manager.assert_called_once()
        mock_manager.get_persistent_graph_behavior.assert_called_once()


@pytest.mark.asyncio
async def test_flow_decision_properties_work(
    mock_graph_manager, mock_config_manager, mock_existing_graph
):
    """Test that decision convenience properties work correctly."""
    # Test REUSE scenario
    mock_config_manager.get_persistent_graph_behavior = AsyncMock(
        return_value=PersistentGraphOpenBehavior.ALWAYS_REUSE
    )

    with patch(
        "shotgun.codebase.graph_open_flow.resolve_canonical_path"
    ) as mock_resolve, patch(
        "shotgun.codebase.graph_open_flow.lookup_graph_for_path"
    ) as mock_lookup:
        mock_resolve.return_value = "/home/user/my-repo"
        mock_lookup.return_value = mock_existing_graph

        decision = await determine_graph_action_for_codebase(
            "/home/user/my-repo",
            mock_graph_manager,
            mock_config_manager,
        )

        # Test convenience properties
        assert decision.should_reuse is True
        assert decision.should_create_new is False
        assert decision.should_ask_user is False


@pytest.mark.asyncio
async def test_flow_is_idempotent(mock_graph_manager, mock_config_manager):
    """Test that multiple calls with same inputs produce same result."""
    with patch(
        "shotgun.codebase.graph_open_flow.resolve_canonical_path"
    ) as mock_resolve, patch(
        "shotgun.codebase.graph_open_flow.lookup_graph_for_path"
    ) as mock_lookup:
        mock_resolve.return_value = "/home/user/my-repo"
        mock_lookup.return_value = None

        decision1 = await determine_graph_action_for_codebase(
            "/home/user/my-repo",
            mock_graph_manager,
            mock_config_manager,
        )

        decision2 = await determine_graph_action_for_codebase(
            "/home/user/my-repo",
            mock_graph_manager,
            mock_config_manager,
        )

        assert decision1.action == decision2.action
        assert decision1.existing_graph == decision2.existing_graph
