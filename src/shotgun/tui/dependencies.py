"""Dependency creation utilities for TUI components."""

from typing import Any

from pydantic_ai import RunContext

from shotgun.agents.config import get_provider_model
from shotgun.agents.config.models import ModelConfig
from shotgun.agents.models import AgentDeps
from shotgun.agents.router.models import RouterDeps, RouterMode
from shotgun.codebase.service import CodebaseService
from shotgun.tui.filtered_codebase_service import FilteredCodebaseService
from shotgun.utils import get_shotgun_home


async def _get_tui_config() -> tuple[ModelConfig, CodebaseService]:
    """Get common TUI configuration components.

    Returns:
        Tuple of (model_config, codebase_service) for TUI deps.
    """
    model_config = await get_provider_model()
    storage_dir = get_shotgun_home() / "codebases"
    codebase_service = FilteredCodebaseService(storage_dir)
    return model_config, codebase_service


def _placeholder_system_prompt_fn(ctx: RunContext[Any]) -> str:
    """Placeholder system prompt that should never be called.

    Agents provide their own system_prompt_fn via their create functions.
    This placeholder exists only to satisfy the AgentDeps requirement.

    Raises:
        RuntimeError: Always, as this should never be invoked.
    """
    raise RuntimeError(
        "This should not be called - agents provide their own system_prompt_fn"
    )


async def create_default_tui_deps() -> AgentDeps:
    """Create default AgentDeps for TUI components.

    This creates a standard AgentDeps configuration suitable for interactive
    TUI usage with:
    - Interactive mode enabled
    - TUI context flag set
    - Filtered codebase service (restricted to CWD)
    - Placeholder system prompt (agents provide their own)

    Returns:
        Configured AgentDeps instance ready for TUI use.
    """
    model_config, codebase_service = await _get_tui_config()

    return AgentDeps(
        interactive_mode=True,
        is_tui_context=True,
        llm_model=model_config,
        codebase_service=codebase_service,
        system_prompt_fn=_placeholder_system_prompt_fn,
    )


async def create_default_router_deps() -> RouterDeps:
    """Create default RouterDeps for TUI components with router mode.

    This creates a RouterDeps configuration suitable for interactive
    TUI usage with:
    - Router mode always starts in PLANNING (not persisted)
    - Interactive mode enabled
    - TUI context flag set
    - Filtered codebase service (restricted to CWD)
    - Placeholder system prompt (router provides its own)

    Returns:
        Configured RouterDeps instance ready for TUI use.
    """
    model_config, codebase_service = await _get_tui_config()

    return RouterDeps(
        interactive_mode=True,
        is_tui_context=True,
        llm_model=model_config,
        codebase_service=codebase_service,
        system_prompt_fn=_placeholder_system_prompt_fn,
        router_mode=RouterMode.PLANNING,
    )
