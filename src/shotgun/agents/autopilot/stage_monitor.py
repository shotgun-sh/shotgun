"""Stage monitor agent for intelligent autopilot orchestration.

Uses the main model (e.g. Opus 4.5) with read-only file tools to verify
Claude Code's output against actual files on disk and decide what to do next.
"""

import logging
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext

from shotgun.agents.autopilot.models import MonitorDecision
from shotgun.agents.config import get_provider_model
from shotgun.agents.config.models import ModelConfig
from shotgun.agents.usage_manager import get_session_usage_manager

logger = logging.getLogger(__name__)

MONITOR_SYSTEM_PROMPT = """\
You are the autopilot stage monitor. Claude Code just finished a work session on a stage.

Your job:
1. Use your tools to read the tasks file and verify which tasks are actually marked complete.
2. Read the spec/plan files if you need context on what the stage should accomplish.
3. Read source files if you need to verify Claude Code's claims about what was implemented.
4. Compare Claude Code's claims against reality on disk.
5. Decide what action to take next.

Actions you can take:
- CONTINUE: Tasks remain. Craft a specific prompt telling Claude Code exactly what to finish.
- REVIEW: All tasks complete, move to code review phase.
- CREATE_PR: All tasks complete, move to PR creation.
- COMPLETE: Stage is done, all tasks verified as complete on disk.
- ESCALATE: Something is wrong (e.g. Claude Code claims done but tasks aren't checked off, \
or repeated failures). Needs human attention.
- DEFER: Work is genuinely stuck on remaining tasks despite multiple attempts. \
Skip and note for later.

Guidelines:
- If the tasks file shows all checkboxes as [x], the stage is COMPLETE.
- If tasks remain but progress is being made, CONTINUE with a targeted prompt.
- If the recent output history shows repetitive patterns (same output 3+ times, \
no task progress between iterations), consider ESCALATE or DEFER.
- When using CONTINUE, write a specific next_prompt that tells Claude Code exactly \
what to do — not a generic "finish remaining tasks" message.
- When using ESCALATE, explain clearly what went wrong in reasoning.
- Always provide a `status_summary`: a short (under 80 chars) description for the user's UI spinner.
  It should convey which stage is being worked on, what's currently happening, and progress.
  Good: "Auth API — 3/5 tasks done, implementing JWT validation"
  Bad: "Working on tasks" (too vague) or a 200-char paragraph (too long)."""


class MonitorDeps(BaseModel):
    """Dependencies for the stage monitor agent."""

    working_directory: Path = Field(description="Working directory for file access")
    tasks_file_path: str = Field(description="Path to tasks.md relative to working dir")


class StageMonitor:
    """Monitors Claude Code output and decides next orchestration action.

    Uses the main model (e.g. Opus 4.5) with read-only file tools to:
    1. Read tasks.md to verify actual task completion state
    2. Read specification.md and plan.md for context
    3. Compare Claude Code's claims against reality
    4. Craft an intelligent next prompt for Claude Code
    """

    def __init__(self, working_directory: Path):
        self._working_directory = working_directory
        self._recent_outputs: list[str] = []
        self._max_history = 3
        self._agent: Agent[MonitorDeps, MonitorDecision] | None = None
        self._model_config: ModelConfig | None = None

    async def _get_agent(self) -> Agent[MonitorDeps, MonitorDecision]:
        """Get or create the monitor agent."""
        if self._agent is not None:
            return self._agent

        # Use main model (not sub-agent) for intelligent monitoring
        model_config = await get_provider_model(for_sub_agent=False)
        self._model_config = model_config
        logger.info("Stage monitor using model: %s", model_config.name)

        agent: Agent[MonitorDeps, MonitorDecision] = Agent(
            model_config.model_instance,
            output_type=MonitorDecision,
            system_prompt=MONITOR_SYSTEM_PROMPT,
            retries=2,
        )

        @agent.tool
        async def read_tasks_file(ctx: RunContext[MonitorDeps]) -> str:
            """Read the tasks.md file to check task completion status."""
            path = ctx.deps.working_directory / ctx.deps.tasks_file_path
            if not path.exists():
                return f"ERROR: Tasks file not found at {ctx.deps.tasks_file_path}"
            return path.read_text(encoding="utf-8")

        @agent.tool
        async def read_spec_file(ctx: RunContext[MonitorDeps]) -> str:
            """Read the specification.md file for stage context."""
            path = ctx.deps.working_directory / ".shotgun" / "specification.md"
            if not path.exists():
                return "No specification.md file found."
            return path.read_text(encoding="utf-8")

        @agent.tool
        async def read_plan_file(ctx: RunContext[MonitorDeps]) -> str:
            """Read the plan.md file for implementation context."""
            path = ctx.deps.working_directory / ".shotgun" / "plan.md"
            if not path.exists():
                return "No plan.md file found."
            return path.read_text(encoding="utf-8")

        @agent.tool
        async def read_file(ctx: RunContext[MonitorDeps], file_path: str) -> str:
            """Read any file in the working directory to verify Claude Code's work.

            Args:
                file_path: Relative path from the working directory.
            """
            # Security: ensure path stays within working directory
            resolved = (ctx.deps.working_directory / file_path).resolve()
            if not str(resolved).startswith(str(ctx.deps.working_directory.resolve())):
                return "ERROR: Path is outside the working directory."
            if not resolved.exists():
                return f"File not found: {file_path}"
            if not resolved.is_file():
                return f"Not a file: {file_path}"
            try:
                content = resolved.read_text(encoding="utf-8")
                # Truncate very large files
                if len(content) > 10000:
                    return content[:10000] + "\n\n... [truncated, file is too large]"
                return content
            except UnicodeDecodeError:
                return f"Cannot read binary file: {file_path}"

        self._agent = agent
        return agent

    def _format_history(self) -> str:
        """Format recent output history for the monitor prompt."""
        if not self._recent_outputs:
            return "No previous iterations."
        parts = []
        for i, output in enumerate(self._recent_outputs, 1):
            parts.append(f"### Iteration {i}\n{output}")
        return "\n\n".join(parts)

    async def evaluate(
        self,
        claude_output_summary: str,
        stage_number: str,
        stage_name: str,
        working_directory: Path,
        tasks_file_path: str,
    ) -> MonitorDecision:
        """Evaluate Claude Code's output and decide what to do next.

        Args:
            claude_output_summary: Summary of Claude Code's text output.
            stage_number: The stage identifier.
            stage_name: The stage name.
            working_directory: Working directory path.
            tasks_file_path: Path to tasks.md relative to working directory.

        Returns:
            MonitorDecision with action and reasoning.
        """
        # Track recent outputs for loop detection
        self._recent_outputs.append(claude_output_summary[:500])
        if len(self._recent_outputs) > self._max_history:
            self._recent_outputs.pop(0)

        prompt = f"""Claude Code just finished working on Stage {stage_number}: {stage_name}.

## Claude Code's Latest Output
{claude_output_summary[:2000]}

## Recent Output History ({len(self._recent_outputs)} iteration(s))
{self._format_history()}

Use your tools to read the tasks file and verify actual progress.
If the recent outputs look repetitive or no progress is being made, consider ESCALATE or DEFER.
Decide what action to take next."""

        agent = await self._get_agent()
        deps = MonitorDeps(
            working_directory=working_directory,
            tasks_file_path=tasks_file_path,
        )

        result = await agent.run(prompt, deps=deps)

        # Track monitor usage
        try:
            if self._model_config and result.usage():
                await get_session_usage_manager().add_usage(
                    result.usage(),
                    model_name=self._model_config.name,
                    provider=self._model_config.provider,
                )
        except Exception:
            logger.debug("Failed to track stage monitor usage")

        logger.info(
            "Monitor decision for Stage %s: action=%s reasoning=%s",
            stage_number,
            result.output.action.value,
            result.output.reasoning[:100],
        )

        return result.output
