"""Agent manager for coordinating multiple AI agents with shared message history."""

from enum import Enum
from typing import Any

from pydantic_ai import (
    Agent,
    DeferredToolRequests,
    DeferredToolResults,
    UsageLimits,
)
from pydantic_ai.agent import AgentRunResult
from pydantic_ai.messages import ModelMessage, ModelRequest
from textual.message import Message
from textual.widget import Widget

from .history.compaction import apply_persistent_compaction
from .models import AgentDeps, AgentRuntimeOptions, FileOperation
from .plan import create_plan_agent
from .research import create_research_agent
from .tasks import create_tasks_agent


class AgentType(Enum):
    """Enumeration for available agent types (for Python < 3.11)."""

    RESEARCH = "research"
    PLAN = "plan"
    TASKS = "tasks"


class MessageHistoryUpdated(Message):
    """Event posted when the message history is updated."""

    def __init__(
        self,
        messages: list[ModelMessage],
        agent_type: AgentType,
        file_operations: list[FileOperation] | None = None,
    ) -> None:
        """Initialize the message history updated event.

        Args:
            messages: The updated message history.
            agent_type: The type of agent that triggered the update.
            file_operations: List of file operations from this run.
        """
        super().__init__()
        self.messages = messages
        self.agent_type = agent_type
        self.file_operations = file_operations or []


class AgentManager(Widget):
    """Manages multiple agents with shared message history."""

    def __init__(
        self,
        deps: AgentDeps | None = None,
        initial_type: AgentType = AgentType.RESEARCH,
    ) -> None:
        """Initialize the agent manager.

        Args:
            deps: Optional agent dependencies. If not provided, defaults to interactive mode.
        """
        super().__init__()
        # Use provided deps or create default with interactive mode
        self.deps = deps

        if self.deps is None:
            raise ValueError("AgentDeps must be provided to AgentManager")

        # Create AgentRuntimeOptions from deps for agent creation
        agent_runtime_options = AgentRuntimeOptions(
            interactive_mode=self.deps.interactive_mode,
            working_directory=self.deps.working_directory,
            max_iterations=self.deps.max_iterations,
            queue=self.deps.queue,
            tasks=self.deps.tasks,
        )

        # Initialize all agents with the same deps
        self.research_agent, _ = create_research_agent(
            agent_runtime_options=agent_runtime_options
        )
        self.plan_agent, _ = create_plan_agent(
            agent_runtime_options=agent_runtime_options
        )
        self.tasks_agent, _ = create_tasks_agent(
            agent_runtime_options=agent_runtime_options
        )

        # Track current active agent
        self._current_agent_type: AgentType = initial_type

        # Maintain shared message history
        self.ui_message_history: list[ModelMessage] = []
        self.message_history: list[ModelMessage] = []
        self.recently_change_files: list[FileOperation] = []

    @property
    def current_agent(self) -> Agent[AgentDeps, str | DeferredToolRequests]:
        """Get the currently active agent.

        Returns:
            The currently selected agent instance.
        """
        return self._get_agent(self._current_agent_type)

    def _get_agent(
        self, agent_type: AgentType
    ) -> Agent[AgentDeps, str | DeferredToolRequests]:
        """Get agent by type.

        Args:
            agent_type: The type of agent to retrieve.

        Returns:
            The requested agent instance.
        """
        agent_map = {
            AgentType.RESEARCH: self.research_agent,
            AgentType.PLAN: self.plan_agent,
            AgentType.TASKS: self.tasks_agent,
        }
        return agent_map[agent_type]

    def set_agent(self, agent_type: AgentType) -> None:
        """Set the current active agent.

        Args:
            agent_type: The agent type to activate (AgentType enum or string).

        Raises:
            ValueError: If invalid agent type is provided.
        """
        try:
            self._current_agent_type = AgentType(agent_type)
        except ValueError:
            raise ValueError(
                f"Invalid agent type: {agent_type}. Must be one of: {', '.join(e.value for e in AgentType)}"
            ) from None

    async def run(
        self,
        prompt: str | None = None,
        *,
        deps: AgentDeps | None = None,
        usage_limits: UsageLimits | None = None,
        deferred_tool_results: DeferredToolResults | None = None,
        **kwargs: Any,
    ) -> AgentRunResult[str | DeferredToolRequests]:
        """Run the current agent with automatic message history management.

        This method wraps the agent's run method, automatically injecting the
        shared message history and updating it after each run.

        Args:
            prompt: Optional prompt to send to the agent.
            deps: Optional dependencies override (defaults to manager's deps).
            usage_limits: Optional usage limits for the agent run.
            deferred_tool_results: Optional deferred tool results for continuing a conversation.
            **kwargs: Additional keyword arguments to pass to the agent.

        Returns:
            The agent run result.
        """
        # Use manager's deps if not provided
        if deps is None:
            deps = self.deps

        # Ensure deps is not None
        if deps is None:
            raise ValueError("AgentDeps must be provided")

        if prompt:
            self.ui_message_history.append(ModelRequest.user_text_prompt(prompt))
        self._post_messages_updated()

        # Run the agent with the shared message history
        result: AgentRunResult[
            str | DeferredToolRequests
        ] = await self.current_agent.run(
            prompt,
            deps=deps,
            usage_limits=usage_limits,
            message_history=self.message_history,
            deferred_tool_results=deferred_tool_results,
            **kwargs,
        )

        # Update the shared message history with all messages from this run
        self.ui_message_history = self.ui_message_history + [
            mes for mes in result.new_messages() if not isinstance(mes, ModelRequest)
        ]

        # Apply compaction to persistent message history to prevent cascading growth
        self.message_history = await apply_persistent_compaction(
            result.all_messages(), deps
        )

        # Log file operations summary if any files were modified
        self.recently_change_files = deps.file_tracker.operations.copy()

        self._post_messages_updated(self.recently_change_files)

        return result

    def _post_messages_updated(
        self, file_operations: list[FileOperation] | None = None
    ) -> None:
        # Post event to notify listeners of the message history update
        self.post_message(
            MessageHistoryUpdated(
                messages=self.ui_message_history.copy(),
                agent_type=self._current_agent_type,
                file_operations=file_operations,
            )
        )
