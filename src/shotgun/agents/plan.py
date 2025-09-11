"""Plan agent using Pydantic AI with file-based memory."""

import time

from pydantic_ai import Agent, UsageLimitExceeded, UsageLimits

from shotgun.logging_config import setup_logger
from shotgun.utils import ensure_shotgun_directory_exists

from .tools import append_file, ask_user, read_file, write_file

logger = setup_logger(__name__)


class PlanAgent:
    """Plan agent that creates and updates plans based on research and user goals."""

    def __init__(self, non_interactive: bool = False) -> None:
        """Initialize the plan agent with file-based memory.

        Args:
            non_interactive: If True, disables user interaction tools (for CI/CD)
        """
        logger.debug("Initializing plan agent (non_interactive=%s)", non_interactive)
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
- Focus on creating minimal but functional plans
"""
        )

        system_prompt = (
            """You are a planning assistant with access to research data and existing plans.
"""
            + interactive_note
            + """

Your job is to:
1. FIRST: Load previous research from research.md using read_file("research.md")
2. SECOND: Load existing plan from plan.md using read_file("plan.md") if it exists
3. ANALYZE: Understand the current context and user's goal/request
4. DECIDE: Whether to create a new plan or update/refine the existing one
5. RESPOND: Provide a structured, actionable plan
6. UPDATE: Write the new/updated plan to plan.md

PLAN CREATION/UPDATE STRATEGY:
- If no plan.md exists: Create a new comprehensive plan based on research and user goal
- If plan.md exists: Analyze it and determine what the user wants:
  - "Make it more concise" → Shorten and simplify the existing plan
  - "Add more detail" → Expand with specific implementation steps
  - "Rewrite" or "start over" → Create a completely new plan
  - New goal → Update or replace plan to align with the new objective
  - Similar goal → Refine and improve the existing plan

PLAN FORMAT:
Structure your plans with clear sections:
```
# Plan: [Title/Goal]

## Overview
[Brief summary of the goal and approach]

## Key Insights from Research
[Relevant findings from research.md that inform this plan]

## Action Steps
1. [Step 1 with specific details]
2. [Step 2 with specific details]
   - Sub-task A
   - Sub-task B
3. [Step 3 with specific details]

## Success Criteria
- [Measurable outcome 1]
- [Measurable outcome 2]

## Potential Challenges & Mitigation
- Challenge: [Description] → Solution: [Approach]

## Resources Needed
- [Resource 1]
- [Resource 2]
```

FILE MANAGEMENT:
- Always start by reading both research.md and plan.md (if they exist)
- Use write_file("plan.md", content) to create or completely replace the plan
- Be explicit about whether you're creating new or updating existing content
- Preserve valuable information from existing plans unless specifically asked to remove it

"""
            + (
                "USER INTERACTION - REDUCE UNCERTAINTY:"
                if not non_interactive
                else "NON-INTERACTIVE MODE - MAKE REASONABLE ASSUMPTIONS:"
            )
            + """
"""
            + (
                """- ALWAYS ask clarifying questions when the goal is vague or ambiguous
- Use ask_user tool frequently to gather specific details about:
  - Project scope and boundaries
  - Target timeline and deadlines
  - Available resources and constraints
  - Success criteria and measurable outcomes
  - Technology preferences or requirements
  - Target audience or users
  - Budget considerations
  - Risk tolerance and priorities
- Ask follow-up questions to drill down into specifics
- Don't assume - ask for confirmation of your understanding
- Better to ask 2-3 targeted questions than create a generic plan
- Confirm major changes to existing plans before proceeding"""
                if not non_interactive
                else """- Make reasonable assumptions based on industry best practices
- Use sensible defaults when specific details are not provided
- Focus on creating a practical, actionable plan
- Include common project phases and considerations
- Assume standard timelines and resource allocations"""
            )
            + """

IMPORTANT RULES:
- Make at most 1 plan file write per request
- Always base plans on available research when relevant
- Create actionable, specific steps rather than vague suggestions
- Consider feasibility and prioritize high-impact actions
- Be concise but comprehensive
"""
            + (
                "- When in doubt about any aspect of the goal, ASK before proceeding"
                if not non_interactive
                else "- When in doubt, make reasonable assumptions and proceed with best practices"
            )
        )

        logger.debug("🤖 Creating plan agent with OpenAI GPT-5")
        logger.debug("📝 System prompt length: %d characters", len(system_prompt))

        self._agent = Agent(
            "openai:gpt-5",
            system_prompt=system_prompt,
            instrument=True,
        )

        # Register tools
        logger.debug("📌 Registering tools with plan agent")
        if not non_interactive:
            self._agent.tool_plain(ask_user)
            logger.debug("📞 User interaction tool registered")
        else:
            logger.debug("🚫 User interaction disabled (non-interactive mode)")
        self._agent.tool_plain(read_file)
        self._agent.tool_plain(write_file)
        self._agent.tool_plain(append_file)
        logger.debug("✅ Tool registration complete")

    async def plan(self, goal: str) -> str:
        """Create or update a plan based on the given goal.

        Args:
            goal: The planning goal or instruction

        Returns:
            Summary of the planning process and results
        """
        # Run the plan agent
        result = await self._agent.run(
            f"Create or update a plan based on this goal/instruction: {goal}"
        )

        # Extract the planning results
        findings = str(result.output)
        return findings

    def plan_sync(self, goal: str) -> str:
        """Synchronous version of plan method.

        Args:
            goal: The planning goal or instruction

        Returns:
            Summary of the planning process and results
        """
        logger.debug("📋 Starting planning for goal: %s", goal)

        # Ensure plan.md exists and initialize if empty
        from pathlib import Path

        shotgun_dir = Path.cwd() / ".shotgun"
        plan_file = shotgun_dir / "plan.md"

        try:
            if plan_file.exists():
                current_plan = plan_file.read_text(encoding="utf-8")
                if not current_plan.strip():
                    # File exists but is empty, add header
                    plan_file.write_text("# Plan\n\n", encoding="utf-8")
                    current_plan = "# Plan\n\n"
            else:
                # File doesn't exist, create it with header
                shotgun_dir.mkdir(exist_ok=True)
                plan_file.write_text("# Plan\n\n", encoding="utf-8")
                current_plan = "# Plan\n\n"
        except Exception as e:
            logger.error("Failed to initialize plan.md: %s", str(e))
            current_plan = "# Plan\n\n"

        # Try to load research.md for context (optional)
        research_file = shotgun_dir / "research.md"
        try:
            if research_file.exists():
                current_research = research_file.read_text(encoding="utf-8")
            else:
                current_research = "No research available."
        except Exception:
            current_research = "No research available."

        logger.debug("📄 Current plan.md content loaded (%d chars)", len(current_plan))
        logger.debug("📄 Research context loaded (%d chars)", len(current_research))

        # Prepare the full prompt for the agent
        full_prompt = f"""
Based on the plan.md and research.md file contents, create or update the plan for the Users Input.
Determine if you need to create a new plan or update the existing one.
Remember to write the updated plan to plan.md using the write_file tool.

The Users Input: {goal}"""
        logger.debug("📝 Agent prompt prepared with plan and research context")
        logger.debug(
            "🚀 Executing agent with available tools: file management, user interaction"
        )

        # Set usage limits to prevent runaway execution
        usage_limits = UsageLimits(request_limit=20, tool_calls_limit=10)
        logger.debug(
            "⚡ Running agent with limits: requests=%d, tool_calls=%d",
            usage_limits.request_limit,
            usage_limits.tool_calls_limit,
        )

        start_time = time.time()

        try:
            result = self._agent.run_sync(full_prompt, usage_limits=usage_limits)
        except UsageLimitExceeded as e:
            logger.warning("⚠️ Usage limit exceeded during planning: %s", str(e))
            return f"Planning partially completed - usage limit reached: {str(e)}"
        except Exception as e:
            logger.error("❌ Error during agent execution: %s", str(e))
            if "usage limit" in str(e).lower():
                logger.warning("⚠️ Usage limit reached: %s", str(e))
                return f"Planning partially completed - usage limit reached: {str(e)}"
            else:
                raise

        end_time = time.time()
        execution_time = end_time - start_time
        logger.debug("⏱️ Agent execution completed in %.2f seconds", execution_time)

        # Extract the planning results
        findings = str(result.output)
        logger.debug(
            "📄 Planning completed, result length: %d characters", len(findings)
        )

        # Log result preview
        if findings:
            preview = findings[:200].replace("\n", " ")
            logger.debug(
                "👀 Result preview: %s%s", preview, "..." if len(findings) > 200 else ""
            )

        logger.debug("🎯 Planning process completed for goal: %s", goal)
        return findings

    def get_plan_history(self) -> str:
        """Get the current plan from the file."""
        try:
            return read_file("plan.md")
        except Exception as e:
            logger.debug("Could not load plan history: %s", str(e))
            return "No plan available."
