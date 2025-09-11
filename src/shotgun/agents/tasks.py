"""Tasks agent using Pydantic AI with file-based memory."""

import time

from pydantic_ai import Agent, UsageLimitExceeded, UsageLimits

from shotgun.logging_config import setup_logger
from shotgun.utils import ensure_shotgun_directory_exists

from .tools import append_file, ask_user, read_file, write_file

logger = setup_logger(__name__)


class TasksAgent:
    """Tasks agent that creates and updates task lists based on research and plans."""

    def __init__(self, non_interactive: bool = False) -> None:
        """Initialize the tasks agent with file-based memory.

        Args:
            non_interactive: If True, disables user interaction tools (for CI/CD)
        """
        logger.debug("Initializing tasks agent (non_interactive=%s)", non_interactive)
        ensure_shotgun_directory_exists()
        self._non_interactive = non_interactive

        # Create agent with ChatGPT-5 and file management capabilities
        interactive_note = (
            ""
            if not non_interactive
            else """
IMPORTANT: USER INTERACTION IS DISABLED (non-interactive mode).
- You cannot ask clarifying questions using ask_user tool
- Make reasonable assumptions based on best practices
- Use sensible defaults when information is missing
- Focus on creating minimal but functional task lists
"""
        )

        system_prompt = (
            """You are a task management assistant with access to research data and project plans.
"""
            + interactive_note
            + """

Your job is to:
1. FIRST: Load previous research from research.md using read_file("research.md") if available
2. SECOND: Load existing plan from plan.md using read_file("plan.md") if available
3. THIRD: Load existing tasks from tasks.md using read_file("tasks.md") if it exists
4. ANALYZE: Understand the current context, research findings, and plan details
5. DECIDE: Whether to create new tasks or update/refine existing ones
6. RESPOND: Provide a structured, actionable task list
7. UPDATE: Write the new/updated tasks to tasks.md

TASK CREATION/UPDATE STRATEGY:
- If no tasks.md exists: Create comprehensive tasks based on research and plan
- If tasks.md exists: Analyze user's request and determine what they want:
  - "Add more detail" → Break down existing tasks into smaller subtasks
  - "Prioritize" → Reorder tasks by importance/urgency
  - "Update progress" → Mark tasks as completed/in-progress
  - "Refine" → Improve task descriptions and acceptance criteria
  - New requirements → Add or modify tasks to align with changes
  - Similar scope → Enhance and improve existing tasks

TASKS FORMAT:
Structure your task lists with clear organization:
```
# Tasks: [Project/Goal Title]

## Task Overview
[Brief summary of what these tasks accomplish]

## Prerequisites
- [Any setup or foundational work needed before starting]

## High Priority Tasks
### Task 1: [Clear, actionable title]
- **Description**: [What needs to be done]
- **Acceptance Criteria**:
  - [ ] Specific outcome 1
  - [ ] Specific outcome 2
- **Dependencies**: [Other tasks that must be completed first]
- **Estimated Effort**: [Time/complexity estimate]
- **Status**: [Not Started/In Progress/Completed]

### Task 2: [Clear, actionable title]
[Same format as above]

## Medium Priority Tasks
[Same structure as High Priority]

## Low Priority Tasks / Future Enhancements
[Same structure but for nice-to-have features]

## Notes & Considerations
- [Important technical considerations]
- [Potential risks or blockers]
- [Resources or tools needed]
```

TASK QUALITY STANDARDS:
- Each task should be specific and actionable (avoid vague descriptions)
- Include clear acceptance criteria that can be verified
- Break down large tasks into smaller, manageable chunks (2-8 hours of work max)
- Identify dependencies between tasks
- Provide realistic effort estimates
- Consider technical constraints from research
- Align with goals and steps from the plan
- Include both development and testing/validation tasks

"""
            + (
                "USER INTERACTION - ASK CLARIFYING QUESTIONS:"
                if not non_interactive
                else "NON-INTERACTIVE MODE - MAKE REASONABLE ASSUMPTIONS:"
            )
            + """
"""
            + (
                """- ALWAYS ask clarifying questions when the request is vague or ambiguous
- Use ask_user tool to gather specific details about:
  - Specific features or functionality to prioritize
  - Technical constraints or preferences
  - Timeline and resource constraints
  - Definition of "done" for key deliverables
  - Testing and quality requirements
  - Team size and skill levels
  - Integration requirements
- Ask follow-up questions to ensure tasks are properly scoped
- Confirm task priorities and dependencies with the user
- Better to ask 2-3 targeted questions than create generic tasks"""
                if not non_interactive
                else """- Make reasonable assumptions based on industry best practices
- Use sensible defaults for technical constraints and timelines
- Create tasks with standard definitions of "done"
- Assume typical team sizes and skill levels
- Include common testing and quality assurance tasks
- Create tasks that follow standard project management practices"""
            )
            + """

INTEGRATION WITH RESEARCH & PLAN:
- Reference specific findings from research.md when creating tasks
- Align tasks with action steps outlined in plan.md
- Consider technical feasibility based on research
- Include tasks for addressing challenges identified in plan
- Create validation/testing tasks for success criteria from plan
- Break down high-level plan steps into granular, executable tasks

IMPORTANT RULES:
- Make at most 1 tasks file write per request
- Always base tasks on available research and plan when relevant
- Create specific, testable tasks rather than vague objectives
- Consider realistic timelines and team capabilities
- Include both implementation and validation/testing tasks
"""
            + (
                "- When in doubt about any aspect of the requirements, ASK before proceeding"
                if not non_interactive
                else "- When in doubt, make reasonable assumptions and proceed with best practices"
            )
            + """
- Ensure tasks are properly prioritized and sequenced
"""
        )

        logger.debug("🤖 Creating tasks agent with OpenAI GPT-5")
        logger.debug("📝 System prompt length: %d characters", len(system_prompt))

        self._agent = Agent(
            "openai:gpt-5",
            system_prompt=system_prompt,
            instrument=True,
        )

        # Register tools
        logger.debug("📌 Registering tools with tasks agent")
        if not non_interactive:
            self._agent.tool_plain(ask_user)
            logger.debug("📞 User interaction tool registered")
        else:
            logger.debug("🚫 User interaction disabled (non-interactive mode)")
        self._agent.tool_plain(read_file)
        self._agent.tool_plain(write_file)
        self._agent.tool_plain(append_file)
        logger.debug("✅ Tool registration complete")

    async def create_tasks(self, instruction: str) -> str:
        """Create or update tasks based on the given instruction.

        Args:
            instruction: The task creation/update instruction

        Returns:
            Summary of the task creation process and results
        """
        # Run the tasks agent
        result = await self._agent.run(
            f"Create or update tasks based on this instruction: {instruction}"
        )

        # Extract the task creation results
        findings = str(result.output)
        return findings

    def create_tasks_sync(self, instruction: str) -> str:
        """Synchronous version of create_tasks method.

        Args:
            instruction: The task creation/update instruction

        Returns:
            Summary of the task creation process and results
        """
        logger.debug("📋 Starting task creation for instruction: %s", instruction)

        # Ensure tasks.md exists and initialize if empty
        from pathlib import Path

        shotgun_dir = Path.cwd() / ".shotgun"
        tasks_file = shotgun_dir / "tasks.md"

        try:
            if tasks_file.exists():
                current_tasks = tasks_file.read_text(encoding="utf-8")
                if not current_tasks.strip():
                    # File exists but is empty, add header
                    tasks_file.write_text("# Tasks\n\n", encoding="utf-8")
                    current_tasks = "# Tasks\n\n"
            else:
                # File doesn't exist, create it with header
                shotgun_dir.mkdir(exist_ok=True)
                tasks_file.write_text("# Tasks\n\n", encoding="utf-8")
                current_tasks = "# Tasks\n\n"
        except Exception as e:
            logger.error("Failed to initialize tasks.md: %s", str(e))
            current_tasks = "# Tasks\n\n"

        # Load plan.md for context (optional)
        plan_file = shotgun_dir / "plan.md"
        try:
            if plan_file.exists():
                current_plan = plan_file.read_text(encoding="utf-8")
            else:
                current_plan = "No plan available."
        except Exception:
            current_plan = "No plan available."

        # Load research.md for context (optional)
        research_file = shotgun_dir / "research.md"
        try:
            if research_file.exists():
                current_research = research_file.read_text(encoding="utf-8")
            else:
                current_research = "No research available."
        except Exception:
            current_research = "No research available."

        logger.debug(
            "📄 Current tasks.md content loaded (%d chars)", len(current_tasks)
        )
        logger.debug("📄 Plan context loaded (%d chars)", len(current_plan))
        logger.debug("📄 Research context loaded (%d chars)", len(current_research))

        # Prepare the full prompt for the agent
        full_prompt = f"""
Keep tasks.md up to date based on the users instructions, the plan.md and the research.md file contents.
Update the tasks.md file using the write_file tool, ask clarifying questions, or answer the questions based on the Users Input.

The Users Input:{instruction}
"""
        logger.debug(
            "📝 Agent prompt prepared with full context (tasks, plan, research)"
        )
        logger.debug(
            "🚀 Executing agent with available tools: file management, user interaction"
        )

        # Set usage limits to prevent runaway execution
        usage_limits = UsageLimits(request_limit=20, tool_calls_limit=15)
        logger.debug(
            "⚡ Running agent with limits: requests=%d, tool_calls=%d",
            usage_limits.request_limit,
            usage_limits.tool_calls_limit,
        )

        start_time = time.time()

        try:
            result = self._agent.run_sync(full_prompt, usage_limits=usage_limits)
        except UsageLimitExceeded as e:
            logger.warning("⚠️ Usage limit exceeded during task creation: %s", str(e))
            return f"Task creation partially completed - usage limit reached: {str(e)}"
        except Exception as e:
            logger.error("❌ Error during agent execution: %s", str(e))
            if "usage limit" in str(e).lower():
                logger.warning("⚠️ Usage limit reached: %s", str(e))
                return (
                    f"Task creation partially completed - usage limit reached: {str(e)}"
                )
            else:
                raise

        end_time = time.time()
        execution_time = end_time - start_time
        logger.debug("⏱️ Agent execution completed in %.2f seconds", execution_time)

        # Extract the task creation results
        findings = str(result.output)
        logger.debug(
            "📄 Task creation completed, result length: %d characters", len(findings)
        )

        # Log result preview
        if findings:
            preview = findings[:200].replace("\n", " ")
            logger.debug(
                "👀 Result preview: %s%s", preview, "..." if len(findings) > 200 else ""
            )

        logger.debug(
            "🎯 Task creation process completed for instruction: %s", instruction
        )
        return findings

    def get_tasks_history(self) -> str:
        """Get the current tasks from the file."""
        try:
            return read_file("tasks.md")
        except Exception as e:
            logger.debug("Could not load tasks history: %s", str(e))
            return "No tasks available."
