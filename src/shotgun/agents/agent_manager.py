"""Agent manager for coordinating multiple AI agents with shared message history."""

import json
import logging
from collections.abc import AsyncIterable, Sequence
from dataclasses import dataclass, field, is_dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import logfire
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

if TYPE_CHECKING:
    from shotgun.agents.conversation_history import ConversationState

from pydantic_ai import (
    Agent,
    RunContext,
    UsageLimits,
)
from pydantic_ai.agent import AgentRunResult
from pydantic_ai.messages import (
    AgentStreamEvent,
    FinalResultEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    ModelMessage,
    ModelRequest,
    ModelRequestPart,
    ModelResponse,
    ModelResponsePart,
    PartDeltaEvent,
    PartStartEvent,
    SystemPromptPart,
    ToolCallPart,
    ToolCallPartDelta,
)
from textual.message import Message
from textual.widget import Widget

from shotgun.agents.common import add_system_prompt_message, add_system_status_message
from shotgun.agents.config.models import KeyProvider
from shotgun.agents.models import AgentResponse, AgentType, FileOperation
from shotgun.posthog_telemetry import track_event
from shotgun.tui.screens.chat_screen.hint_message import HintMessage
from shotgun.utils.source_detection import detect_source

from .export import create_export_agent
from .history.compaction import apply_persistent_compaction
from .messages import AgentSystemPrompt
from .models import AgentDeps, AgentRuntimeOptions
from .plan import create_plan_agent
from .research import create_research_agent
from .specify import create_specify_agent
from .tasks import create_tasks_agent

logger = logging.getLogger(__name__)


def _is_retryable_error(exception: BaseException) -> bool:
    """Check if exception should trigger a retry.

    Args:
        exception: The exception to check.

    Returns:
        True if the exception is a transient error that should be retried.
    """
    # ValueError for truncated/incomplete JSON
    if isinstance(exception, ValueError):
        error_str = str(exception)
        return "EOF while parsing" in error_str or (
            "JSON" in error_str and "parsing" in error_str
        )

    # API errors (overload, rate limits)
    exception_name = type(exception).__name__
    if "APIStatusError" in exception_name:
        error_str = str(exception)
        return "overload" in error_str.lower() or "rate" in error_str.lower()

    # Network errors
    if "ConnectionError" in exception_name or "TimeoutError" in exception_name:
        return True

    return False


class MessageHistoryUpdated(Message):
    """Event posted when the message history is updated."""

    def __init__(
        self,
        messages: list[ModelMessage | HintMessage],
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


class PartialResponseMessage(Message):
    """Event posted when a partial response is received."""

    def __init__(
        self,
        message: ModelResponse | None,
        messages: list[ModelMessage],
        is_last: bool,
    ) -> None:
        """Initialize the partial response message."""
        super().__init__()
        self.message = message
        self.messages = messages
        self.is_last = is_last


class ClarifyingQuestionsMessage(Message):
    """Event posted when agent returns clarifying questions."""

    def __init__(
        self,
        questions: list[str],
        response_text: str,
    ) -> None:
        """Initialize the clarifying questions message.

        Args:
            questions: List of clarifying questions from the agent
            response_text: The agent's response text before asking questions
        """
        super().__init__()
        self.questions = questions
        self.response_text = response_text


@dataclass(slots=True)
class _PartialStreamState:
    """Tracks streamed messages while handling a single agent run."""

    messages: list[ModelRequest | ModelResponse] = field(default_factory=list)
    current_response: ModelResponse | None = None


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
        self.display = False

        if deps is None:
            raise ValueError("AgentDeps must be provided to AgentManager")

        # Use provided deps or create default with interactive mode
        self.deps = deps

        # Create AgentRuntimeOptions from deps for agent creation
        agent_runtime_options = AgentRuntimeOptions(
            interactive_mode=self.deps.interactive_mode,
            working_directory=self.deps.working_directory,
            is_tui_context=self.deps.is_tui_context,
            max_iterations=self.deps.max_iterations,
            queue=self.deps.queue,
            tasks=self.deps.tasks,
        )

        # Initialize all agents and store their specific deps
        self.research_agent, self.research_deps = create_research_agent(
            agent_runtime_options=agent_runtime_options
        )
        self.plan_agent, self.plan_deps = create_plan_agent(
            agent_runtime_options=agent_runtime_options
        )
        self.tasks_agent, self.tasks_deps = create_tasks_agent(
            agent_runtime_options=agent_runtime_options
        )
        self.specify_agent, self.specify_deps = create_specify_agent(
            agent_runtime_options=agent_runtime_options
        )
        self.export_agent, self.export_deps = create_export_agent(
            agent_runtime_options=agent_runtime_options
        )

        # Track current active agent
        self._current_agent_type: AgentType = initial_type

        # Maintain shared message history
        self.ui_message_history: list[ModelMessage | HintMessage] = []
        self.message_history: list[ModelMessage] = []
        self.recently_change_files: list[FileOperation] = []
        self._stream_state: _PartialStreamState | None = None

        # Q&A mode state for structured output questions
        self._qa_questions: list[str] | None = None
        self._qa_mode_active: bool = False

    @property
    def current_agent(self) -> Agent[AgentDeps, AgentResponse]:
        """Get the currently active agent.

        Returns:
            The currently selected agent instance.
        """
        return self._get_agent(self._current_agent_type)

    def _get_agent(self, agent_type: AgentType) -> Agent[AgentDeps, AgentResponse]:
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
            AgentType.SPECIFY: self.specify_agent,
            AgentType.EXPORT: self.export_agent,
        }
        return agent_map[agent_type]

    def _get_agent_deps(self, agent_type: AgentType) -> AgentDeps:
        """Get agent-specific deps by type.

        Args:
            agent_type: The type of agent to retrieve deps for.

        Returns:
            The agent-specific dependencies.
        """
        deps_map = {
            AgentType.RESEARCH: self.research_deps,
            AgentType.PLAN: self.plan_deps,
            AgentType.TASKS: self.tasks_deps,
            AgentType.SPECIFY: self.specify_deps,
            AgentType.EXPORT: self.export_deps,
        }
        return deps_map[agent_type]

    def _create_merged_deps(self, agent_type: AgentType) -> AgentDeps:
        """Create merged dependencies combining shared and agent-specific deps.

        This preserves the agent's system_prompt_fn while using shared runtime state.

        Args:
            agent_type: The type of agent to create merged deps for.

        Returns:
            Merged AgentDeps with agent-specific system_prompt_fn.
        """
        agent_deps = self._get_agent_deps(agent_type)

        # Ensure shared deps is not None (should be guaranteed by __init__)
        if self.deps is None:
            raise ValueError("Shared deps is None - this should not happen")

        # Create new deps with shared runtime state but agent's system_prompt_fn
        # Use a copy of the shared deps and update the system_prompt_fn
        merged_deps = self.deps.model_copy(
            update={"system_prompt_fn": agent_deps.system_prompt_fn}
        )

        return merged_deps

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

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception(_is_retryable_error),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def _run_agent_with_retry(
        self,
        agent: Agent[AgentDeps, AgentResponse],
        prompt: str | None,
        deps: AgentDeps,
        usage_limits: UsageLimits | None,
        message_history: list[ModelMessage],
        event_stream_handler: Any,
        **kwargs: Any,
    ) -> AgentRunResult[AgentResponse]:
        """Run agent with automatic retry on transient errors.

        Args:
            agent: The agent to run.
            prompt: Optional prompt to send to the agent.
            deps: Agent dependencies.
            usage_limits: Optional usage limits.
            message_history: Message history to provide to agent.
            event_stream_handler: Event handler for streaming.
            **kwargs: Additional keyword arguments.

        Returns:
            The agent run result.

        Raises:
            Various exceptions if all retries fail.
        """
        return await agent.run(
            prompt,
            deps=deps,
            usage_limits=usage_limits,
            message_history=message_history,
            event_stream_handler=event_stream_handler,
            **kwargs,
        )

    async def run(
        self,
        prompt: str | None = None,
        *,
        deps: AgentDeps | None = None,
        usage_limits: UsageLimits | None = None,
        **kwargs: Any,
    ) -> AgentRunResult[AgentResponse]:
        """Run the current agent with automatic message history management.

        This method wraps the agent's run method, automatically injecting the
        shared message history and updating it after each run.

        Args:
            prompt: Optional prompt to send to the agent.
            deps: Optional dependencies override (defaults to manager's deps).
            usage_limits: Optional usage limits for the agent run.
            **kwargs: Additional keyword arguments to pass to the agent.

        Returns:
            The agent run result.
        """
        logger.info(f"Running agent {self._current_agent_type.value}")
        # Use merged deps (shared state + agent-specific system prompt) if not provided
        if deps is None:
            deps = self._create_merged_deps(self._current_agent_type)

        # Ensure deps is not None
        if deps is None:
            raise ValueError("AgentDeps must be provided")

        # Clear file tracker before each run to track only this run's operations
        deps.file_tracker.clear()
        # preprocess messages; maybe we need to include the user answer in the message history

        original_messages = self.ui_message_history.copy()

        if prompt:
            self.ui_message_history.append(ModelRequest.user_text_prompt(prompt))
        self._post_messages_updated()

        # Start with persistent message history
        message_history = self.message_history

        deps.agent_mode = self._current_agent_type

        # Filter out system prompts from other agent types
        from pydantic_ai.messages import ModelRequestPart

        filtered_history: list[ModelMessage] = []
        for message in message_history:
            # Keep all non-ModelRequest messages as-is
            if not isinstance(message, ModelRequest):
                filtered_history.append(message)
                continue

            # Filter out AgentSystemPrompts from other agent types
            filtered_parts: list[ModelRequestPart] = []
            for part in message.parts:
                # Keep non-AgentSystemPrompt parts
                if not isinstance(part, AgentSystemPrompt):
                    filtered_parts.append(part)
                    continue

                # Only keep system prompts from the same agent type
                if part.agent_mode == deps.agent_mode:
                    filtered_parts.append(part)

            # Only add the message if it has parts remaining
            if filtered_parts:
                filtered_history.append(ModelRequest(parts=filtered_parts))

        message_history = filtered_history

        # Add a system status message so the agent knows whats going on
        message_history = await add_system_status_message(deps, message_history)

        # Check if the message history already has a system prompt from the same agent type
        has_system_prompt = False
        for message in message_history:
            if not isinstance(message, ModelRequest):
                continue

            for part in message.parts:
                if not isinstance(part, AgentSystemPrompt):
                    continue

                # Check if it's from the same agent type
                if part.agent_mode == deps.agent_mode:
                    has_system_prompt = True
                    break

        # Always ensure we have a system prompt for the agent
        # (compaction may remove it from persistent history, but agent needs it)
        if not has_system_prompt:
            message_history = await add_system_prompt_message(deps, message_history)

        # Run the agent with streaming support (from origin/main)
        self._stream_state = _PartialStreamState()

        model_name = ""
        if hasattr(deps, "llm_model") and deps.llm_model is not None:
            model_name = deps.llm_model.name

        # Check if it's a Shotgun account
        is_shotgun_account = (
            hasattr(deps, "llm_model")
            and deps.llm_model is not None
            and deps.llm_model.key_provider == KeyProvider.SHOTGUN
        )

        # Only disable streaming for GPT-5 if NOT a Shotgun account
        # Shotgun accounts support streaming for GPT-5
        is_gpt5_byok = "gpt-5" in model_name.lower() and not is_shotgun_account

        # Track message send event
        event_name = f"message_send_{self._current_agent_type.value}"
        track_event(
            event_name,
            {
                "has_prompt": prompt is not None,
                "model_name": model_name,
            },
        )

        try:
            result: AgentRunResult[AgentResponse] = await self._run_agent_with_retry(
                agent=self.current_agent,
                prompt=prompt,
                deps=deps,
                usage_limits=usage_limits,
                message_history=message_history,
                event_stream_handler=self._handle_event_stream
                if not is_gpt5_byok
                else None,
                **kwargs,
            )
        except ValueError as e:
            # Handle truncated/incomplete JSON in tool calls specifically
            error_str = str(e)
            if "EOF while parsing" in error_str or (
                "JSON" in error_str and "parsing" in error_str
            ):
                logger.error(
                    "Tool call with truncated/incomplete JSON arguments detected",
                    extra={
                        "agent_mode": self._current_agent_type.value,
                        "model_name": model_name,
                        "error": error_str,
                    },
                )
                logfire.error(
                    "Tool call with truncated JSON arguments",
                    agent_mode=self._current_agent_type.value,
                    model_name=model_name,
                    error=error_str,
                )
                # Add helpful hint message for the user
                self.ui_message_history.append(
                    HintMessage(
                        message="⚠️ The agent attempted an operation with arguments that were too large (truncated JSON). "
                        "Try breaking your request into smaller steps or more focused contracts."
                    )
                )
                self._post_messages_updated()
            # Re-raise to maintain error visibility
            raise
        except Exception as e:
            # Log the error with full stack trace to shotgun.log and Logfire
            logger.exception(
                "Agent execution failed",
                extra={
                    "agent_mode": self._current_agent_type.value,
                    "model_name": model_name,
                    "error_type": type(e).__name__,
                },
            )
            logfire.exception(
                "Agent execution failed",
                agent_mode=self._current_agent_type.value,
                model_name=model_name,
                error_type=type(e).__name__,
            )
            # Re-raise to let TUI handle user messaging
            raise
        finally:
            self._stream_state = None

        # Agent ALWAYS returns AgentResponse with structured output
        agent_response = result.output
        logger.debug(
            "Agent returned structured AgentResponse",
            extra={
                "has_response": agent_response.response is not None,
                "response_length": len(agent_response.response)
                if agent_response.response
                else 0,
                "response_preview": agent_response.response[:100] + "..."
                if agent_response.response and len(agent_response.response) > 100
                else agent_response.response or "(empty)",
                "has_clarifying_questions": bool(agent_response.clarifying_questions),
                "num_clarifying_questions": len(agent_response.clarifying_questions)
                if agent_response.clarifying_questions
                else 0,
            },
        )

        # Always add the agent's response messages to maintain conversation history
        self.ui_message_history = original_messages + cast(
            list[ModelRequest | ModelResponse | HintMessage], result.new_messages()
        )

        # Get file operations early so we can use them for contextual messages
        file_operations = deps.file_tracker.operations.copy()
        self.recently_change_files = file_operations

        logger.debug(
            "File operations tracked",
            extra={
                "num_file_operations": len(file_operations),
                "operation_files": [Path(op.file_path).name for op in file_operations],
            },
        )

        # Check if there are clarifying questions
        if agent_response.clarifying_questions:
            logger.info(
                f"Agent has {len(agent_response.clarifying_questions)} clarifying questions"
            )

            # Add agent's response first if present
            if agent_response.response:
                self.ui_message_history.append(
                    HintMessage(message=agent_response.response)
                )

            if len(agent_response.clarifying_questions) == 1:
                # Single question - treat as non-blocking suggestion, DON'T enter Q&A mode
                self.ui_message_history.append(
                    HintMessage(message=f"💡 {agent_response.clarifying_questions[0]}")
                )
            else:
                # Multiple questions (2+) - enter Q&A mode
                self._qa_questions = agent_response.clarifying_questions
                self._qa_mode_active = True

                # Show intro with list, then first question
                questions_list_with_intro = (
                    f"I have {len(agent_response.clarifying_questions)} questions:\n\n"
                    + "\n".join(
                        f"{i + 1}. {q}"
                        for i, q in enumerate(agent_response.clarifying_questions)
                    )
                )
                self.ui_message_history.append(
                    HintMessage(message=questions_list_with_intro)
                )
                self.ui_message_history.append(
                    HintMessage(
                        message=f"**Q1:** {agent_response.clarifying_questions[0]}"
                    )
                )

                # Post event to TUI to update Q&A mode state (only for multiple questions)
                self.post_message(
                    ClarifyingQuestionsMessage(
                        questions=agent_response.clarifying_questions,
                        response_text=agent_response.response,
                    )
                )

            # Post UI update with hint messages and file operations
            logger.debug(
                "Posting UI update for Q&A mode with hint messages and file operations"
            )
            self._post_messages_updated(file_operations)
        else:
            # No clarifying questions - show the response or a default success message
            if agent_response.response and agent_response.response.strip():
                logger.debug(
                    "Adding agent response as hint",
                    extra={
                        "response_preview": agent_response.response[:100] + "..."
                        if len(agent_response.response) > 100
                        else agent_response.response,
                        "has_file_operations": len(file_operations) > 0,
                    },
                )
                self.ui_message_history.append(
                    HintMessage(message=agent_response.response)
                )
            else:
                # Fallback: response is empty or whitespace
                logger.debug(
                    "Agent response was empty, using fallback completion message",
                    extra={"has_file_operations": len(file_operations) > 0},
                )
                # Show contextual message based on whether files were modified
                if file_operations:
                    self.ui_message_history.append(
                        HintMessage(
                            message="✅ Task completed - files have been modified"
                        )
                    )
                else:
                    self.ui_message_history.append(
                        HintMessage(message="✅ Task completed")
                    )

            # Post UI update immediately so user sees the response without delay
            logger.debug(
                "Posting immediate UI update with hint message and file operations"
            )
            self._post_messages_updated(file_operations)

        # Apply compaction to persistent message history to prevent cascading growth
        all_messages = result.all_messages()
        try:
            logger.debug(
                "Starting message history compaction",
                extra={"message_count": len(all_messages)},
            )
            self.message_history = await apply_persistent_compaction(all_messages, deps)
            logger.debug(
                "Completed message history compaction",
                extra={
                    "original_count": len(all_messages),
                    "compacted_count": len(self.message_history),
                },
            )
        except Exception as e:
            # If compaction fails, log full error with stack trace and use uncompacted messages
            logger.error(
                "Failed to compact message history - using uncompacted messages",
                exc_info=True,
                extra={
                    "error": str(e),
                    "message_count": len(all_messages),
                    "agent_mode": self._current_agent_type.value,
                },
            )
            # Fallback: use uncompacted messages to prevent data loss
            self.message_history = all_messages

        usage = result.usage()
        if hasattr(deps, "llm_model") and deps.llm_model is not None:
            deps.usage_manager.add_usage(
                usage, model_name=deps.llm_model.name, provider=deps.llm_model.provider
            )
        else:
            logger.warning(
                "llm_model is None, skipping usage tracking",
                extra={"agent_mode": self._current_agent_type.value},
            )

        # UI updates are now posted immediately in each branch (Q&A or non-Q&A)
        # before compaction, so no duplicate posting needed here

        return result

    async def _handle_event_stream(
        self,
        _ctx: RunContext[AgentDeps],
        stream: AsyncIterable[AgentStreamEvent],
    ) -> None:
        """Process streamed events and forward partial updates to the UI."""

        state = self._stream_state
        if state is None:
            state = self._stream_state = _PartialStreamState()

        if state.current_response is not None:
            partial_parts: list[ModelResponsePart | ToolCallPartDelta] = list(
                state.current_response.parts
                # cast(Sequence[ModelResponsePart], state.current_response.parts)
            )
        else:
            partial_parts = []

        async for event in stream:
            try:
                if isinstance(event, PartStartEvent):
                    index = event.index
                    if index < len(partial_parts):
                        partial_parts[index] = event.part
                    elif index == len(partial_parts):
                        partial_parts.append(event.part)
                    else:
                        logger.warning(
                            "Received PartStartEvent with out-of-bounds index",
                            extra={"index": index, "current_len": len(partial_parts)},
                        )
                        partial_parts.append(event.part)

                    partial_message = self._build_partial_response(partial_parts)
                    if partial_message is not None:
                        state.current_response = partial_message
                        self._post_partial_message(False)

                elif isinstance(event, PartDeltaEvent):
                    index = event.index
                    if index >= len(partial_parts):
                        logger.warning(
                            "Received PartDeltaEvent before corresponding start event",
                            extra={"index": index, "current_len": len(partial_parts)},
                        )
                        continue

                    try:
                        updated_part = event.delta.apply(
                            cast(ModelResponsePart, partial_parts[index])
                        )
                    except Exception:  # pragma: no cover - defensive logging
                        logger.exception(
                            "Failed to apply part delta", extra={"event": event}
                        )
                        continue

                    partial_parts[index] = updated_part

                    partial_message = self._build_partial_response(partial_parts)
                    if partial_message is not None:
                        state.current_response = partial_message
                        self._post_partial_message(False)

                elif isinstance(event, FunctionToolCallEvent):
                    # Track tool call event

                    # Detect source from call stack
                    source = detect_source()

                    # Log if tool call has incomplete args (for debugging truncated JSON)
                    if isinstance(event.part.args, str):
                        try:
                            json.loads(event.part.args)
                        except (json.JSONDecodeError, ValueError):
                            args_preview = (
                                event.part.args[:100] + "..."
                                if len(event.part.args) > 100
                                else event.part.args
                            )
                            logger.warning(
                                "FunctionToolCallEvent received with incomplete JSON args",
                                extra={
                                    "tool_name": event.part.tool_name,
                                    "tool_call_id": event.part.tool_call_id,
                                    "args_preview": args_preview,
                                    "args_length": len(event.part.args)
                                    if event.part.args
                                    else 0,
                                    "agent_mode": self._current_agent_type.value,
                                },
                            )
                            logfire.warn(
                                "FunctionToolCallEvent received with incomplete JSON args",
                                tool_name=event.part.tool_name,
                                tool_call_id=event.part.tool_call_id,
                                args_preview=args_preview,
                                args_length=len(event.part.args)
                                if event.part.args
                                else 0,
                                agent_mode=self._current_agent_type.value,
                            )

                    track_event(
                        "tool_called",
                        {
                            "tool_name": event.part.tool_name,
                            "agent_mode": self._current_agent_type.value
                            if self._current_agent_type
                            else "unknown",
                            "source": source,
                        },
                    )

                    existing_call_idx = next(
                        (
                            i
                            for i, part in enumerate(partial_parts)
                            if isinstance(part, ToolCallPart)
                            and part.tool_call_id == event.part.tool_call_id
                        ),
                        None,
                    )

                    if existing_call_idx is not None:
                        partial_parts[existing_call_idx] = event.part
                    elif state.messages:
                        existing_call_idx = next(
                            (
                                i
                                for i, part in enumerate(state.messages[-1].parts)
                                if isinstance(part, ToolCallPart)
                                and part.tool_call_id == event.part.tool_call_id
                            ),
                            None,
                        )
                    else:
                        partial_parts.append(event.part)
                    partial_message = self._build_partial_response(partial_parts)
                    if partial_message is not None:
                        state.current_response = partial_message
                        self._post_partial_message(False)
                elif isinstance(event, FunctionToolResultEvent):
                    # Track tool completion event

                    # Detect source from call stack
                    source = detect_source()

                    track_event(
                        "tool_completed",
                        {
                            "tool_name": event.result.tool_name
                            if hasattr(event.result, "tool_name")
                            else "unknown",
                            "agent_mode": self._current_agent_type.value
                            if self._current_agent_type
                            else "unknown",
                            "source": source,
                        },
                    )

                    request_message = ModelRequest(parts=[event.result])
                    state.messages.append(request_message)
                    ## this is what the user responded with
                    self._post_partial_message(is_last=False)

                elif isinstance(event, FinalResultEvent):
                    pass
            except Exception:  # pragma: no cover - defensive logging
                logger.exception(
                    "Error while handling agent stream event", extra={"event": event}
                )

        final_message = state.current_response or self._build_partial_response(
            partial_parts
        )
        if final_message is not None:
            state.current_response = final_message
            if final_message not in state.messages:
                state.messages.append(final_message)
            state.current_response = None
            self._post_partial_message(True)
        state.current_response = None

    def _build_partial_response(
        self, parts: list[ModelResponsePart | ToolCallPartDelta]
    ) -> ModelResponse | None:
        """Create a `ModelResponse` from the currently streamed parts."""

        completed_parts = [
            part for part in parts if not isinstance(part, ToolCallPartDelta)
        ]
        if not completed_parts:
            return None
        return ModelResponse(parts=list(completed_parts))

    def _post_partial_message(self, is_last: bool) -> None:
        """Post a partial message to the UI."""
        if self._stream_state is None:
            return
        self.post_message(
            PartialResponseMessage(
                self._stream_state.current_response
                if self._stream_state.current_response
                not in self._stream_state.messages
                else None,
                self._stream_state.messages,
                is_last,
            )
        )

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

    def _filter_system_prompts(
        self, messages: list[ModelMessage | HintMessage]
    ) -> list[ModelMessage | HintMessage]:
        """Filter out system prompts from messages for UI display.

        Args:
            messages: List of messages that may contain system prompts

        Returns:
            List of messages without system prompt parts
        """
        filtered_messages: list[ModelMessage | HintMessage] = []
        for msg in messages:
            if isinstance(msg, HintMessage):
                filtered_messages.append(msg)
                continue

            parts: Sequence[ModelRequestPart] | Sequence[ModelResponsePart] | None = (
                msg.parts if hasattr(msg, "parts") else None
            )
            if not parts:
                filtered_messages.append(msg)
                continue

            non_system_parts = [
                part for part in parts if not isinstance(part, SystemPromptPart)
            ]

            if not non_system_parts:
                # Skip messages made up entirely of system prompt parts (e.g. system message)
                continue

            if len(non_system_parts) == len(parts):
                # Nothing was filtered – keep original message
                filtered_messages.append(msg)
                continue

            if is_dataclass(msg):
                filtered_messages.append(
                    # ignore types because of the convoluted Request | Response types
                    replace(msg, parts=cast(Any, non_system_parts))
                )
            else:
                filtered_messages.append(msg)
        return filtered_messages

    def get_usage_hint(self) -> str | None:
        return self.deps.usage_manager.build_usage_hint()

    def get_conversation_state(self) -> "ConversationState":
        """Get the current conversation state.

        Returns:
            ConversationState object containing UI and agent messages and current type
        """
        from shotgun.agents.conversation_history import ConversationState

        return ConversationState(
            agent_messages=self.message_history.copy(),
            ui_messages=self.ui_message_history.copy(),
            agent_type=self._current_agent_type.value,
        )

    def restore_conversation_state(self, state: "ConversationState") -> None:
        """Restore conversation state from a saved state.

        Args:
            state: ConversationState object to restore
        """
        # Restore message history for agents (includes system prompts)
        non_hint_messages = [
            msg for msg in state.agent_messages if not isinstance(msg, HintMessage)
        ]
        self.message_history = non_hint_messages

        # Filter out system prompts for UI display while keeping hints
        ui_source = state.ui_messages or cast(
            list[ModelMessage | HintMessage], state.agent_messages
        )
        self.ui_message_history = self._filter_system_prompts(ui_source)

        # Restore agent type
        self._current_agent_type = AgentType(state.agent_type)

        # Notify listeners about the restored messages
        self._post_messages_updated()

    def add_hint_message(self, message: HintMessage) -> None:
        self.ui_message_history.append(message)
        self._post_messages_updated()


# Re-export AgentType for backward compatibility
__all__ = [
    "AgentManager",
    "AgentType",
    "MessageHistoryUpdated",
    "PartialResponseMessage",
    "ClarifyingQuestionsMessage",
]
