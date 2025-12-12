"""
Router agent execution wrapper for evaluation.

Wraps AgentManager.run() to capture evaluable outputs with Logfire tracing.
"""

import logging
import platform
import time
from pathlib import Path
from typing import Any

import logfire
from pydantic import BaseModel, Field
from pydantic_ai.agent import AgentRunResult
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart

from evals.logfire_utils import (
    TraceRef,
    configure_logfire_or_fail,
    get_current_trace_ref,
)
from evals.models import (
    AgentExecutionOutput,
    FileOperation,
    ShotgunTestCase,
)

logger = logging.getLogger(__name__)


class ExecutionError(Exception):
    """Raised when test case execution fails."""


class ExecutionResult(BaseModel):
    """Result from executing a single test case."""

    test_case_name: str = Field(..., description="Name of the executed test case")
    output: AgentExecutionOutput = Field(
        ..., description="Captured execution output from the agent"
    )
    trace_ref: TraceRef = Field(
        ..., description="Logfire trace reference for debugging"
    )
    error: str | None = Field(
        default=None, description="Error message if execution failed"
    )


class RouterExecutor:
    """
    Executes Router agent test cases with Logfire instrumentation.

    This executor wraps the AgentManager to run test cases and capture
    evaluable outputs with trace references for debugging.
    """

    def __init__(self, working_directory: Path | None = None) -> None:
        """Initialize the RouterExecutor.

        Args:
            working_directory: Working directory for agent execution.
                Defaults to current working directory.
        """
        self._configured = False
        self._working_directory = working_directory or Path.cwd()

    def _ensure_configured(self) -> None:
        """Ensure Logfire is configured. Raises if misconfigured."""
        if not self._configured:
            configure_logfire_or_fail()
            self._configured = True

    async def execute_case(
        self,
        test_case: ShotgunTestCase,
        suite_name: str = "default",
    ) -> ExecutionResult:
        """
        Execute a single test case and capture outputs.

        Creates one Logfire trace per test case.

        Args:
            test_case: The test case to execute
            suite_name: Name of the evaluation suite for trace metadata

        Returns:
            ExecutionResult with captured output and trace reference
        """
        self._ensure_configured()

        with logfire.span(
            "eval.run_case",
            test_case_name=test_case.name,
            suite_name=suite_name,
            agent_type=test_case.inputs.agent_type.value,
        ):
            trace_ref = get_current_trace_ref()

            try:
                output = await self._execute_agent(test_case)
                return ExecutionResult(
                    test_case_name=test_case.name,
                    output=output,
                    trace_ref=trace_ref,
                )
            except Exception as e:
                logfire.exception(
                    "Test case execution failed",
                    test_case_name=test_case.name,
                    error_type=type(e).__name__,
                )
                return ExecutionResult(
                    test_case_name=test_case.name,
                    output=self._empty_output(),
                    trace_ref=trace_ref,
                    error=str(e),
                )

    async def _execute_agent(
        self,
        test_case: ShotgunTestCase,
    ) -> AgentExecutionOutput:
        """Execute the agent and extract outputs.

        Args:
            test_case: The test case containing inputs for agent execution

        Returns:
            AgentExecutionOutput with all captured observations
        """
        # Import here to avoid circular imports and keep evals loosely coupled
        from pydantic_ai import RunContext

        from shotgun.agents.agent_manager import AgentManager
        from shotgun.agents.config import get_provider_model
        from shotgun.agents.models import AgentDeps, AgentResponse, FileOperationTracker
        from shotgun.codebase.service import CodebaseService
        from shotgun.utils import get_shotgun_home

        with logfire.span("eval.execute_agent"):
            # Get model configuration
            model_config = await get_provider_model()

            # Create codebase service
            storage_dir = get_shotgun_home() / "codebases"
            codebase_service = CodebaseService(storage_dir)

            # Create file tracker for this run
            file_tracker = FileOperationTracker()

            # Placeholder system prompt function (agents provide their own)
            def _eval_system_prompt_fn(ctx: RunContext[Any]) -> str:
                raise RuntimeError(
                    "This should not be called - agents provide their own system_prompt_fn"
                )

            # Create AgentDeps
            deps = AgentDeps(
                interactive_mode=False,
                is_tui_context=False,
                llm_model=model_config,
                codebase_service=codebase_service,
                system_prompt_fn=_eval_system_prompt_fn,
                file_tracker=file_tracker,
            )

            # Create agent manager
            manager = AgentManager(deps=deps)

            # Time the execution
            start_time = time.time()

            # Run the agent with the test case prompt
            result: AgentRunResult[AgentResponse] = await manager.run(
                prompt=test_case.inputs.prompt
            )

            duration = time.time() - start_time

        with logfire.span("eval.extract_observations"):
            # Extract response
            response = result.output.response
            clarifying_questions = result.output.clarifying_questions or []

            # Extract tool usage
            tools_used = self._extract_tool_names(result.all_messages())

            # Extract file operations
            file_operations = self._extract_file_operations(file_tracker.operations)

            # Extract token usage
            usage = result.usage()
            token_usage = {
                "prompt_tokens": usage.input_tokens or 0,
                "completion_tokens": usage.output_tokens or 0,
                "total_tokens": (usage.input_tokens or 0) + (usage.output_tokens or 0),
            }

            # Extract router-specific fields
            delegated_sub_agent = self._extract_delegated_agent(result.all_messages())

        return AgentExecutionOutput(
            response=response,
            clarifying_questions=clarifying_questions if clarifying_questions else None,
            file_operations=file_operations,
            tools_used=tools_used,
            duration_seconds=duration,
            token_usage=token_usage,
            delegated_sub_agent=delegated_sub_agent,
            delegation_reasoning=None,  # Could extract from response if needed
        )

    def _extract_tool_names(self, messages: list[ModelMessage]) -> list[str]:
        """Extract unique tool names from message history in order of first use.

        Args:
            messages: List of model messages from the agent run

        Returns:
            List of unique tool names in order of first invocation
        """
        tool_names: list[str] = []
        seen: set[str] = set()

        for msg in messages:
            if isinstance(msg, ModelResponse):
                for part in msg.parts:
                    if isinstance(part, ToolCallPart):
                        if part.tool_name not in seen:
                            tool_names.append(part.tool_name)
                            seen.add(part.tool_name)

        return tool_names

    def _extract_file_operations(
        self,
        operations: list[Any],
    ) -> list[FileOperation]:
        """Convert FileOperationTracker operations to eval FileOperations.

        Args:
            operations: List of file operations from the tracker

        Returns:
            List of FileOperation models with normalized paths
        """
        result: list[FileOperation] = []
        for op in operations:
            # Normalize path relative to working directory
            try:
                rel_path = Path(op.file_path).relative_to(self._working_directory)
                normalized_path = str(rel_path)
            except ValueError:
                normalized_path = op.file_path

            result.append(
                FileOperation(
                    file_path=normalized_path,
                    operation=op.operation.value.upper(),  # CREATED, UPDATED, DELETED
                    content_snippet=None,
                )
            )

        return result

    def _extract_delegated_agent(self, messages: list[ModelMessage]) -> str | None:
        """Extract which sub-agent was delegated to (Router-specific).

        Args:
            messages: List of model messages from the agent run

        Returns:
            Name of the delegated sub-agent or None if no delegation occurred
        """
        # Mapping from delegation tool names to agent names
        delegation_tools = {
            "delegate_to_research": "research",
            "delegate_to_specification": "specify",
            "delegate_to_plan": "plan",
            "delegate_to_tasks": "tasks",
            "delegate_to_export": "export",
        }

        for msg in messages:
            if isinstance(msg, ModelResponse):
                for part in msg.parts:
                    if isinstance(part, ToolCallPart):
                        if part.tool_name in delegation_tools:
                            return delegation_tools[part.tool_name]

        return None

    def _empty_output(self) -> AgentExecutionOutput:
        """Create empty output for error cases.

        Returns:
            AgentExecutionOutput with default/empty values
        """
        return AgentExecutionOutput(
            response="",
            clarifying_questions=None,
            file_operations=[],
            tools_used=[],
            duration_seconds=0.0,
            token_usage={},
            delegated_sub_agent=None,
            delegation_reasoning=None,
        )


def get_environment_metadata() -> dict[str, Any]:
    """Get stable environment metadata for reporting.

    Returns:
        Dictionary with environment info (Python version, platform, etc.)
    """
    return {
        "python_version": platform.python_version(),
        "platform": platform.system(),
        "platform_version": platform.version(),
    }
