"""User interaction tools for Pydantic AI agents."""

import sys

from shotgun.logging_config import setup_logger

logger = setup_logger(__name__)


def ask_user(question: str) -> str:
    """Ask the human a question and return the answer.

    Args:
        question: The question to ask the user

    Returns:
        The user's response as a string
    """
    try:
        logger.info("\n👉 %s\n", question)
        response = sys.stdin.readline().strip()
        logger.info(" Thanks!\n")
        logger.debug("User response received: %s", response)
        return response
    except (EOFError, KeyboardInterrupt):
        logger.warning("User input interrupted or unavailable")
        return "User input not available or interrupted"
