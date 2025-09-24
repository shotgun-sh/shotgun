"""User interaction tools for Pydantic AI agents."""

from asyncio import get_running_loop

from pydantic_ai import CallDeferred, RunContext

from shotgun.agents.models import AgentDeps, UserQuestion
from shotgun.logging_config import get_logger

logger = get_logger(__name__)


async def ask_user(ctx: RunContext[AgentDeps], question: str) -> str:
    """Ask the human a question and return the answer.


    Args:
        question: The question to ask the user with a clear CTA at the end. Needs to be is readable, clear, and easy to understand. Use Markdown formatting. Make key phrases and words stand out.

    Returns:
        The user's response as a string
    """
    tool_call_id = ctx.tool_call_id
    assert tool_call_id is not None  # noqa: S101

    try:
        logger.debug("\n👉 %s\n", question)
        future = get_running_loop().create_future()
        await ctx.deps.queue.put(
            UserQuestion(question=question, tool_call_id=tool_call_id, result=future)
        )
        ctx.deps.tasks.append(future)
        raise CallDeferred(question)

    except (EOFError, KeyboardInterrupt):
        logger.warning("User input interrupted or unavailable")
        return "User input not available or interrupted"
