"""Tests for the cancellation utilities module."""

import asyncio

import pytest

from shotgun.agents.cancellation import (
    CANCELLATION_CHECK_INTERVAL,
    CANCELLATION_MESSAGE,
    CancellableStreamIterator,
)


async def async_generator(items: list[int], delay: float = 0):
    """Helper async generator for testing."""
    for item in items:
        if delay > 0:
            await asyncio.sleep(delay)
        yield item


@pytest.mark.asyncio
async def test_cancellable_stream_iterator_yields_items_normally():
    """Test that the iterator yields all items when not cancelled."""
    items = [1, 2, 3, 4, 5]
    stream = async_generator(items)
    iterator = CancellableStreamIterator(stream)

    result = [item async for item in iterator]

    assert result == items


@pytest.mark.asyncio
async def test_cancellable_stream_iterator_raises_on_cancellation():
    """Test that the iterator raises CancelledError when event is set."""
    items = [1, 2, 3, 4, 5]
    cancellation_event = asyncio.Event()

    async def slow_generator():
        for item in items:
            await asyncio.sleep(0.1)
            yield item

    iterator = CancellableStreamIterator(
        slow_generator(),
        cancellation_event=cancellation_event,
        check_interval=0.05,  # Short interval for fast test
    )

    result = []
    with pytest.raises(asyncio.CancelledError, match=CANCELLATION_MESSAGE):
        async for item in iterator:
            result.append(item)
            if len(result) == 2:
                # Cancel after receiving 2 items
                cancellation_event.set()

    # Should have received some items before cancellation
    assert len(result) >= 2


@pytest.mark.asyncio
async def test_cancellable_stream_iterator_checks_cancellation_during_slow_stream():
    """Test that cancellation is detected even when stream is slow."""
    cancellation_event = asyncio.Event()

    async def very_slow_generator():
        for i in range(3):
            await asyncio.sleep(10)  # Very slow - 10 seconds per item
            yield i

    iterator = CancellableStreamIterator(
        very_slow_generator(),
        cancellation_event=cancellation_event,
        check_interval=0.05,  # Check every 50ms
    )

    async def cancel_after_delay():
        await asyncio.sleep(0.1)
        cancellation_event.set()

    # Start the cancellation task
    cancel_task = asyncio.create_task(cancel_after_delay())

    start_time = asyncio.get_event_loop().time()
    with pytest.raises(asyncio.CancelledError):
        async for _ in iterator:
            pass  # Should never get here

    elapsed = asyncio.get_event_loop().time() - start_time

    # Should have cancelled quickly (< 1 second), not waited 10 seconds for first item
    assert elapsed < 1.0

    await cancel_task


@pytest.mark.asyncio
async def test_cancellable_stream_iterator_without_event():
    """Test that the iterator works normally without a cancellation event."""
    items = [10, 20, 30]
    stream = async_generator(items)
    iterator = CancellableStreamIterator(stream, cancellation_event=None)

    result = [item async for item in iterator]

    assert result == items


@pytest.mark.asyncio
async def test_cancellable_stream_iterator_handles_stop_iteration():
    """Test that StopAsyncIteration is properly propagated."""
    items = [1, 2]
    stream = async_generator(items)
    iterator = CancellableStreamIterator(stream)

    result = []
    async for item in iterator:
        result.append(item)

    assert result == items


@pytest.mark.asyncio
async def test_cancellable_stream_iterator_custom_check_interval():
    """Test that custom check interval is respected."""
    custom_interval = 0.1
    items = [1]
    stream = async_generator(items)
    iterator = CancellableStreamIterator(stream, check_interval=custom_interval)

    assert iterator._check_interval == custom_interval

    result = [item async for item in iterator]
    assert result == items


@pytest.mark.asyncio
async def test_cancellable_stream_iterator_pre_cancelled():
    """Test immediate cancellation when event is already set."""
    cancellation_event = asyncio.Event()
    cancellation_event.set()  # Set before iteration starts

    items = [1, 2, 3]
    stream = async_generator(items)
    iterator = CancellableStreamIterator(stream, cancellation_event=cancellation_event)

    with pytest.raises(asyncio.CancelledError):
        async for _ in iterator:
            pass


def test_default_cancellation_check_interval():
    """Test that default check interval is 0.5 seconds."""
    assert CANCELLATION_CHECK_INTERVAL == 0.5
