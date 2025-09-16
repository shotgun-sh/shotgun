"""Shared fixtures for codebase tools tests."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic_ai import RunContext

from shotgun.agents.config.models import ModelConfig, ProviderType
from shotgun.agents.models import AgentDeps, AgentRuntimeOptions
from shotgun.codebase.models import CodebaseGraph, GraphStatus


@pytest.fixture
def mock_codebase_service():
    """Create a mock codebase service."""
    service = MagicMock()
    service.list_graphs = AsyncMock()
    service.execute_query = AsyncMock()
    service.manager = MagicMock()
    service.manager._execute_query = AsyncMock()
    return service


@pytest.fixture
def mock_graph():
    """Create a mock codebase graph."""
    return CodebaseGraph(
        graph_id="test-graph-id",
        repo_path="/tmp/test-repo",  # noqa: S108
        graph_path="/tmp/test-graph.db",  # noqa: S108
        name="Test Graph",
        created_at=1234567890.0,
        updated_at=1234567890.0,
        status=GraphStatus.READY,
    )


@pytest.fixture
def mock_agent_deps(mock_codebase_service):
    """Create mock agent dependencies."""
    runtime_options = AgentRuntimeOptions()

    # Create a real ModelConfig instead of a mock
    model_config = ModelConfig(
        name="test-model",
        provider=ProviderType.OPENAI,
        max_input_tokens=4096,
        max_output_tokens=2048,
    )

    # Use model_construct to bypass validation entirely for the mock
    deps = AgentDeps.model_construct(
        **runtime_options.model_dump(),
        llm_model=model_config,
        codebase_service=mock_codebase_service,
    )
    return deps


@pytest.fixture
def mock_run_context(mock_agent_deps):
    """Create mock run context."""
    return MagicMock(spec=RunContext, deps=mock_agent_deps)
