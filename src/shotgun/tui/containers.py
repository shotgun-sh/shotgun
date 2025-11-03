"""Dependency injection container for TUI components."""

from typing import TYPE_CHECKING

from dependency_injector import containers, providers
from pydantic_ai import RunContext

from shotgun.agents.agent_manager import AgentManager
from shotgun.agents.config import get_provider_model
from shotgun.agents.conversation_manager import ConversationManager
from shotgun.agents.models import AgentDeps, AgentType
from shotgun.sdk.codebase import CodebaseSDK
from shotgun.tui.commands import CommandHandler
from shotgun.tui.filtered_codebase_service import FilteredCodebaseService
from shotgun.tui.services.conversation_service import ConversationService
from shotgun.tui.state.processing_state import ProcessingStateManager
from shotgun.tui.utils.mode_progress import PlaceholderHints
from shotgun.tui.widgets.widget_coordinator import WidgetCoordinator
from shotgun.utils import get_shotgun_home

if TYPE_CHECKING:
    pass


# Placeholder system prompt function (agents provide their own)
# Using Object provider to pass the function itself, not call it
def _placeholder_system_prompt(ctx: "RunContext[AgentDeps]") -> str:
    raise RuntimeError(
        "This should not be called - agents provide their own system_prompt_fn"
    )


class TUIContainer(containers.DeclarativeContainer):
    """Dependency injection container for TUI components.

    This container manages the lifecycle and dependencies of all TUI components,
    ensuring consistent configuration and facilitating testing.
    """

    # Configuration
    config = providers.Configuration()

    # Core dependencies
    model_config = providers.Singleton(get_provider_model)

    storage_dir = providers.Singleton(lambda: get_shotgun_home() / "codebases")

    codebase_service = providers.Singleton(
        FilteredCodebaseService, storage_dir=storage_dir
    )

    system_prompt_fn = providers.Object(_placeholder_system_prompt)

    # AgentDeps singleton
    agent_deps = providers.Singleton(
        AgentDeps,
        interactive_mode=True,
        is_tui_context=True,
        llm_model=model_config,
        codebase_service=codebase_service,
        system_prompt_fn=system_prompt_fn,
    )

    # Service singletons
    codebase_sdk = providers.Singleton(CodebaseSDK)

    command_handler = providers.Singleton(CommandHandler)

    placeholder_hints = providers.Singleton(PlaceholderHints)

    conversation_manager = providers.Singleton(ConversationManager)

    conversation_service = providers.Factory(
        ConversationService, conversation_manager=conversation_manager
    )

    # Factory for AgentManager (needs agent_type parameter)
    agent_manager_factory = providers.Factory(
        AgentManager, deps=agent_deps, initial_type=providers.Object(AgentType.RESEARCH)
    )

    # Factory for ProcessingStateManager (needs ChatScreen reference)
    processing_state_factory = providers.Factory(
        ProcessingStateManager,
        screen=providers.Object(None),  # Will be overridden when creating ChatScreen
        telemetry_context=providers.Object({}),  # Will be overridden when creating
    )

    # Factory for WidgetCoordinator (needs ChatScreen reference)
    widget_coordinator_factory = providers.Factory(
        WidgetCoordinator,
        screen=providers.Object(None),  # Will be overridden when creating ChatScreen
    )
