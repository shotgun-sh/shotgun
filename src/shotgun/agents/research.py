"""Research agent factory and functions using Pydantic AI with file-based memory."""

from pydantic_ai import Agent, RunContext

from shotgun.logging_config import setup_logger

from .common import (
    create_base_agent,
    ensure_file_exists,
    get_file_history,
    get_interactive_note,
)
from .models import AgentDeps
from .tools import web_search_tool

logger = setup_logger(__name__)


def _build_research_agent_system_prompt(ctx: RunContext[AgentDeps]) -> str:
    """Build the system prompt for the research agent.

    Args:
        ctx: RunContext containing AgentDeps with interactive_mode and other settings

    Returns:
        The complete system prompt string for the research agent
    """
    interactive_note = get_interactive_note(
        ctx.deps.interactive_mode, "research output"
    )

    return (
        """
You are an experienced Software Architect tasked with researching topics thoroughly and keeping the research.md file up to date.
"""
        + interactive_note
        + """

Your job is to:
1. FIRST: Load previous research from research.md using read_file("research.md") if available
2. ANALYZE: Understand what research has already been done
3. SEARCH: If needed, use web search to find additional information on the query
4. SYNTHESIZE: Combine existing research with new findings
5. UPDATE: Write comprehensive, organized research to research.md using write_file("research.md", content)
6. FOCUS: Provide actionable insights relevant to software architecture decisions

IMPORTANT RESEARCH PRINCIPLES:
- Build on existing research rather than starting from scratch
- Use web search strategically for gaps in current knowledge
- Organize findings by topic/category for easy reference
- Include specific examples, tools, and implementation details
- Cite sources when possible for credibility
- Keep research.md as the single source of truth
- Focus on practical, actionable information over theoretical concepts

RESEARCH METHODOLOGY:
- Start broad, then narrow focus based on specific needs
- Look for recent developments and best practices
- Consider multiple perspectives and trade-offs
- Validate information from multiple sources
- Document assumptions and limitations

Always ensure research.md contains well-structured, comprehensive information that can guide technical decisions.
"""
    )


def create_research_agent(deps: AgentDeps | None = None) -> Agent[AgentDeps, str]:
    """Create a research agent with web search capabilities.

    Args:
        deps: Optional agent dependencies for conditional tool registration

    Returns:
        Configured Pydantic AI agent for research tasks
    """
    logger.debug("Initializing research agent")
    return create_base_agent(
        _build_research_agent_system_prompt, [web_search_tool], deps
    )


async def run_research_agent(
    agent: Agent[AgentDeps, str], query: str, deps: AgentDeps
) -> str:
    """Perform research on the given query and update the research file.

    Args:
        agent: The configured research agent
        query: The research query to investigate
        deps: Agent dependencies

    Returns:
        Summary of research findings
    """
    logger.debug("🔬 Starting research for query: %s", query)

    # Ensure research.md exists
    ensure_file_exists("research.md", "# Research")

    # Let the agent use its tools to read existing research
    full_prompt = (
        f"Research this topic thoroughly and provide comprehensive findings: {query}"
    )

    try:
        # Run the agent asynchronously with deps
        result = await agent.run(full_prompt, deps=deps)
        findings = str(result.output)

        logger.debug("✅ Research completed successfully")
        return findings

    except Exception as e:
        logger.error("❌ Research failed: %s", str(e))
        return f"Research failed: {str(e)}"


def get_research_history() -> str:
    """Get the full research history from the file.

    Returns:
        Research history content or fallback message
    """
    return get_file_history("research.md")
