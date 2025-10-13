"""Ask multiple questions tool for Pydantic AI agents."""

from asyncio import get_running_loop

from pydantic_ai import CallDeferred, RunContext

from shotgun.agents.models import AgentDeps, MultipleUserQuestions
from shotgun.logging_config import get_logger

logger = get_logger(__name__)


async def ask_questions(ctx: RunContext[AgentDeps], questions: list[str]) -> str:
    """Ask the human multiple questions sequentially and return all Q&A pairs.

    This tool will display questions one at a time with progress indicators
    (e.g., "Question 1 of 5") and collect all answers before returning them
    formatted together. This provides a better UX than asking questions one by one,
    as users can see their progress and don't need to use multiline input.

    Do not ask 1 question with multiple parts, or multiple questions inside of it.
    Structure it so each question can be answered independently.

    Args:
        questions: List of questions to ask the user. Each question should be readable,
            clear, and easy to understand. Use Markdown formatting. Make key phrases
            and words stand out. Questions will be asked in the order provided.

    Returns:
        All questions and answers formatted as:
        "Q1: {question1}\\nA1: {answer1}\\n\\nQ2: {question2}\\nA2: {answer2}\\n\\n..."
    """
    tool_call_id = ctx.tool_call_id
    assert tool_call_id is not None  # noqa: S101

    try:
        logger.debug("\n👉 Asking %d questions\n", len(questions))
        future = get_running_loop().create_future()
        await ctx.deps.queue.put(
            MultipleUserQuestions(
                questions=questions,
                tool_call_id=tool_call_id,
                result=future,
            )
        )
        ctx.deps.tasks.append(future)
        # Use first question as deferred message preview
        preview = questions[0] if questions else "No questions"
        raise CallDeferred(
            f"Asking {len(questions)} questions starting with: {preview}"
        )

    except (EOFError, KeyboardInterrupt):
        logger.warning("User input interrupted or unavailable")
        return "User input not available or interrupted"
