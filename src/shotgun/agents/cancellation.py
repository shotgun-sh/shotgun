"""Cancellation utilities for agent execution.

This module provides utilities for responsive cancellation of agent operations,
particularly for handling ESC key presses during LLM streaming.
"""

import asyncio
from collections.abc import AsyncIterable, AsyncIterator
from typing import TypeVar

from shotgun.logging_config import get_logger

logger = get_logger(__name__)

T = TypeVar("T")

CANCELLATION_CHECK_INTERVAL = 0.5  # Check every 500ms
CANCELLATION_MESSAGE = "Operation cancelled by user"


class CancellableStreamIterator(AsyncIterator[T]):
    """Wraps an async iterable to check for cancellation periodically.

    This allows ESC cancellation to be responsive even when the underlying
    stream (LLM chunks) is slow to produce events. Instead of blocking
    indefinitely on the next chunk, we timeout periodically and check
    if cancellation was requested.

    Example:
        ```python
        cancellation_event = asyncio.Event()

        async def process_stream(stream):
            wrapped = CancellableStreamIterator(stream, cancellation_event)
            async for event in wrapped:
                process(event)

        # In another task, set the event to cancel:
        cancellation_event.set()
        ```
    """

    def __init__(
        self,
        stream: AsyncIterable[T],
        cancellation_event: asyncio.Event | None = None,
        check_interval: float = CANCELLATION_CHECK_INTERVAL,
    ) -> None:
        """Initialize the cancellable stream iterator.

        Args:
            stream: The underlying async iterable to wrap
            cancellation_event: Event that signals cancellation when set
            check_interval: How often to check for cancellation (seconds)
        """
        self._stream = stream
        self._iterator: AsyncIterator[T] | None = None
        self._cancellation_event = cancellation_event
        self._check_interval = check_interval
        self._pending_task: asyncio.Task[T] | None = None

    def __aiter__(self) -> AsyncIterator[T]:
        return self

    async def __anext__(self) -> T:
        if self._iterator is None:
            self._iterator = self._stream.__aiter__()

        # Create a task for the next item if we don't have one pending
        if self._pending_task is None:
            # Capture iterator reference for the coroutine
            iterator = self._iterator

            async def get_next() -> T:
                return await iterator.__anext__()

            self._pending_task = asyncio.create_task(get_next())

        while True:
            # Check if cancellation was requested
            if self._cancellation_event and self._cancellation_event.is_set():
                logger.debug("Cancellation detected in stream iterator")
                # Cancel the pending task and raise
                self._pending_task.cancel()
                self._pending_task = None
                raise asyncio.CancelledError(CANCELLATION_MESSAGE)

            # Wait for the task with a short timeout
            # Using asyncio.wait instead of wait_for to avoid cancelling the task on timeout
            done, _ = await asyncio.wait(
                [self._pending_task],
                timeout=self._check_interval,
                return_when=asyncio.FIRST_COMPLETED,
            )

            if done:
                # Task completed - get result and clear pending task
                task = done.pop()
                self._pending_task = None
                # Re-raise StopAsyncIteration or return the result
                return task.result()

            # Task not done yet, loop and check cancellation again
