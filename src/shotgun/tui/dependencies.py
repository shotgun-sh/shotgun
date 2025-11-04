"""Dependency creation utilities for TUI components."""

from pydantic_ai import RunContext

from shotgun.agents.config import get_provider_model
from shotgun.agents.models import AgentDeps
from shotgun.tui.filtered_codebase_service import FilteredCodebaseService
from shotgun.utils import get_shotgun_home


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
    model_config = await get_provider_model()
    storage_dir = get_shotgun_home() / "codebases"
    codebase_service = FilteredCodebaseService(storage_dir)

    def _placeholder_system_prompt_fn(ctx: RunContext[AgentDeps]) -> str:
        raise RuntimeError(
            "This should not be called - agents provide their own system_prompt_fn"
        )

    return AgentDeps(
        interactive_mode=True,
        is_tui_context=True,
        llm_model=model_config,
        codebase_service=codebase_service,
        system_prompt_fn=_placeholder_system_prompt_fn,
    )
