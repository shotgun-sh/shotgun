"""Research agent using Pydantic AI with file-based memory."""

import time

from pydantic_ai import Agent, UsageLimitExceeded, UsageLimits

from shotgun.logging_config import setup_logger
from shotgun.utils import ensure_shotgun_directory_exists

from .tools import append_file, ask_user, read_file, web_search_tool, write_file

logger = setup_logger(__name__)


class ResearchAgent:
    """Research agent that maintains memory through a research.md file."""

    def __init__(self) -> None:
        """Initialize the research agent with file-based memory."""
        logger.debug("Initializing research agent")
        ensure_shotgun_directory_exists()

        # Create agent with ChatGPT-5 and web search capabilities
        system_prompt = """You are a research assistant with access to web search and file management tools.

Your job is to:
1. FIRST: Load previous research from research.md using read_file("research.md")
2. CHECK: Analyze if the current query matches or is very similar to any existing research
3. DECIDE: Only perform web search if needed (see criteria below)
4. RESPOND: Provide findings from existing research or new search results
5. UPDATE: Add new research entries to research.md only when new searches are performed

WHEN TO USE EXISTING RESEARCH (no web search needed):
- The exact same query has been researched recently
- A very similar query exists with comprehensive results
- The user is asking for information already covered in research.md
- If using existing research, tell the user: "Based on previous research in our knowledge base..."

WHEN TO PERFORM NEW WEB SEARCH:
- The query is completely new/different from existing research
- Existing research on similar topic is incomplete or outdated
- User explicitly asks for "fresh," "updated," or "latest" information
- You need to supplement existing research with additional details

File management instructions:
- Always start by using read_file("research.md") to load previous research
- Only use append_file("research.md", content) when you perform a NEW web search
- Format new entries with timestamp, query, and findings
- Keep the research organized and chronological

Research format for new entries (only when NEW search is performed):
```
## Query: {query}

{your NEW research findings}

---

```

When responding:
- Clearly indicate if you're using existing research vs. new search results
- Provide summary of key findings
- Include relevant details and sources
- Give clear conclusions or next steps

IMPORTANT RULES:
- You must use the ask_user tool if you need clarification from the user
- Make at most 1 web search call per query!
- Don't duplicate research - check existing content first
- Be efficient: reuse existing knowledge when appropriate
"""

        logger.debug("🤖 Creating research agent with OpenAI GPT-5")
        logger.debug("📝 System prompt length: %d characters", len(system_prompt))

        self._agent = Agent(
            "openai:gpt-5",
            system_prompt=system_prompt,
            instrument=True,
        )

        # Register tools
        logger.debug("📌 Registering tools with research agent")
        self._agent.tool_plain(web_search_tool)
        self._agent.tool_plain(ask_user)
        self._agent.tool_plain(read_file)
        self._agent.tool_plain(write_file)
        self._agent.tool_plain(append_file)
        logger.debug("✅ Tool registration complete")

    async def research(self, query: str) -> str:
        """Perform research on the given query and update the research file.

        Args:
            query: The research query to investigate

        Returns:
            Summary of research findings
        """
        # Run the research agent
        result = await self._agent.run(
            f"Research this topic thoroughly and provide comprehensive findings: {query}"
        )

        # Extract the research findings
        findings = str(result.output)
        return findings

    def research_sync(self, query: str) -> str:
        """Synchronous version of research method.

        Args:
            query: The research query to investigate

        Returns:
            Summary of research findings
        """
        logger.debug("🔬 Starting research for query: %s", query)

        # Prepare the full prompt for the agent
        full_prompt = f"Research this topic thoroughly and provide comprehensive findings: {query}"
        logger.debug("📝 Agent prompt: %s", full_prompt)
        logger.debug("🚀 Executing agent with available tools: web_search_tool")

        # Run the research agent synchronously with usage limits

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
            logger.warning("⚠️ Usage limit exceeded during research: %s", str(e))
            return f"Research partially completed - usage limit reached: {str(e)}"
        except Exception as e:
            logger.error("❌ Error during agent execution: %s", str(e))
            if "usage limit" in str(e).lower():
                logger.warning("⚠️ Usage limit reached: %s", str(e))
                return f"Research partially completed - usage limit reached: {str(e)}"
            else:
                raise

        end_time = time.time()
        execution_time = end_time - start_time
        logger.debug("⏱️ Agent execution completed in %.2f seconds", execution_time)

        # Extract the research findings
        findings = str(result.output)
        logger.debug(
            "📄 Research completed, result length: %d characters", len(findings)
        )

        # Log result preview
        if findings:
            preview = findings[:200].replace("\n", " ")
            logger.debug(
                "👀 Result preview: %s%s", preview, "..." if len(findings) > 200 else ""
            )

        logger.debug("🎯 Research process completed for query: %s", query)
        return findings

    def get_research_history(self) -> str:
        """Get the full research history from the file."""
        try:
            return read_file("research.md")
        except Exception as e:
            logger.debug("Could not load research history: %s", str(e))
            return "No research history available."
