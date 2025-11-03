"""Service for context analysis with caching and debouncing.

This service wraps the ContextAnalyzer with performance optimizations:
- LRU caching to avoid redundant token calculations
- Debouncing to reduce analysis frequency during rapid updates
"""

import asyncio
import hashlib
import logging
from functools import lru_cache
from typing import TYPE_CHECKING

from pydantic_ai.messages import ModelMessage

from shotgun.agents.context_analyzer import ContextAnalyzer
from shotgun.agents.context_analyzer.models import ContextAnalysis
from shotgun.agents.conversation_history import HintMessage

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def _message_list_hash(messages: list[ModelMessage | HintMessage]) -> str:
    """Create a hash of message list for caching.

    Args:
        messages: List of messages to hash.

    Returns:
        A hash string representing the message list.
    """
    # Create a stable hash from message IDs and content
    content = "".join(str(msg) for msg in messages)
    return hashlib.sha256(content.encode()).hexdigest()


@lru_cache(maxsize=100)
def _cached_context_analysis(
    agent_history_hash: str,
    ui_history_hash: str,
    model_name: str,
) -> ContextAnalysis | None:
    """Cached context analysis - NOTE: actual analysis happens in get_analysis.

    This is a placeholder that stores results. The real caching happens
    at the service level using message hashes.

    Args:
        agent_history_hash: Hash of agent message history.
        ui_history_hash: Hash of UI message history.
        model_name: The model name for analysis.

    Returns:
        Cached analysis result if available.
    """
    # This function is a cache key holder
    # Actual caching is managed by the ContextService
    return None


class ContextService:
    """Service for context analysis with performance optimizations.

    This service provides:
    - Cached context analysis (avoids redundant calculations)
    - Debounced updates (reduces analysis frequency)
    - Async analysis (non-blocking)

    Example:
        service = ContextService(llm_model="claude-sonnet-4")

        # Get analysis (cached if messages unchanged)
        analysis = await service.get_analysis(agent_messages, ui_messages)

        # Clear cache if needed
        service.clear_cache()
    """

    def __init__(self, llm_model: str, debounce_seconds: float = 0.5):
        """Initialize the context service.

        Args:
            llm_model: The LLM model name for token counting.
            debounce_seconds: Time to wait before analyzing (reduces rapid updates).
        """
        self.llm_model = llm_model
        self.debounce_seconds = debounce_seconds
        self._pending_analysis: asyncio.Task | None = None
        self._last_analysis: ContextAnalysis | None = None
        self._last_agent_hash: str | None = None
        self._last_ui_hash: str | None = None

    async def get_analysis(
        self,
        agent_messages: list[ModelMessage],
        ui_messages: list[ModelMessage | HintMessage],
        force: bool = False,
    ) -> ContextAnalysis | None:
        """Get context analysis for message histories.

        This method checks cache first. If messages haven't changed,
        returns cached result. Otherwise, runs analysis.

        Args:
            agent_messages: Agent conversation history.
            ui_messages: UI conversation history (with hints).
            force: If True, bypass cache and force new analysis.

        Returns:
            Context analysis result, or None if analysis fails.
        """
        # Compute hashes for caching
        agent_hash = _message_list_hash(agent_messages)
        ui_hash = _message_list_hash(ui_messages)

        # Check if we have cached result
        if (
            not force
            and self._last_agent_hash == agent_hash
            and self._last_ui_hash == ui_hash
            and self._last_analysis is not None
        ):
            logger.debug("Returning cached context analysis")
            return self._last_analysis

        # Run analysis
        try:
            analyzer = ContextAnalyzer(self.llm_model)
            analysis = await analyzer.analyze_conversation(agent_messages, ui_messages)

            # Cache the result
            self._last_agent_hash = agent_hash
            self._last_ui_hash = ui_hash
            self._last_analysis = analysis

            logger.debug(f"Context analysis completed and cached")
            return analysis
        except Exception as e:
            logger.exception(f"Failed to analyze context: {e}")
            return None

    async def get_analysis_debounced(
        self,
        agent_messages: list[ModelMessage],
        ui_messages: list[ModelMessage | HintMessage],
    ) -> ContextAnalysis | None:
        """Get context analysis with debouncing.

        This method waits for `debounce_seconds` before running analysis.
        If called again during the wait, the previous call is cancelled
        and the timer resets.

        This is useful for reducing analysis frequency during rapid message
        updates (e.g., streaming responses).

        Args:
            agent_messages: Agent conversation history.
            ui_messages: UI conversation history (with hints).

        Returns:
            Context analysis result, or None if cancelled or failed.
        """
        # Cancel any pending analysis
        if self._pending_analysis and not self._pending_analysis.done():
            self._pending_analysis.cancel()
            logger.debug("Cancelled pending context analysis")

        async def delayed_analysis():
            await asyncio.sleep(self.debounce_seconds)
            return await self.get_analysis(agent_messages, ui_messages)

        # Schedule new analysis
        self._pending_analysis = asyncio.create_task(delayed_analysis())

        try:
            return await self._pending_analysis
        except asyncio.CancelledError:
            logger.debug("Context analysis was cancelled (debounced)")
            return self._last_analysis  # Return cached result if available

    def clear_cache(self) -> None:
        """Clear the analysis cache.

        Use this when you want to force fresh analysis on next call,
        or to free memory.
        """
        self._last_agent_hash = None
        self._last_ui_hash = None
        self._last_analysis = None
        logger.debug("Context analysis cache cleared")

    def update_model(self, llm_model: str) -> None:
        """Update the LLM model and clear cache.

        Args:
            llm_model: The new LLM model name.
        """
        if self.llm_model != llm_model:
            self.llm_model = llm_model
            self.clear_cache()
            logger.debug(f"LLM model updated to {llm_model}, cache cleared")
