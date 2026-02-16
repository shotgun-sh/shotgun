"""Tests for the VerticalTail component."""

from unittest.mock import MagicMock, patch

from textual.geometry import Size

from shotgun.tui.components.vertical_tail import VerticalTail


def _make_vertical_tail(auto_scroll: bool = True) -> VerticalTail:
    """Create a VerticalTail with mocked internals for unit testing."""
    with patch.object(VerticalTail, "__init__", lambda self, *a, **kw: None):
        vt = VerticalTail.__new__(VerticalTail)
        # Set all attributes via __dict__ to bypass Textual descriptors/setters
        vt.__dict__.update(
            _scroll_pending=False,
            id="test",
            _id="test",
            _reactive_auto_scroll=auto_scroll,
        )
        vt.call_later = MagicMock()  # type: ignore[method-assign]
        vt.scroll_end = MagicMock()  # type: ignore[method-assign]
        return vt


def test_watch_virtual_size_queues_scroll_when_auto_scroll_enabled() -> None:
    """Should queue a deferred scroll when auto_scroll is True."""
    vt = _make_vertical_tail(auto_scroll=True)

    vt.watch_virtual_size(Size(100, 200))

    assert vt._scroll_pending is True
    vt.call_later.assert_called_once_with(vt._deferred_scroll_end)  # type: ignore[attr-defined]


def test_watch_virtual_size_skips_scroll_when_auto_scroll_disabled() -> None:
    """Should not queue scroll when auto_scroll is False."""
    vt = _make_vertical_tail(auto_scroll=False)

    vt.watch_virtual_size(Size(100, 200))

    assert vt._scroll_pending is False
    vt.call_later.assert_not_called()  # type: ignore[attr-defined]


def test_watch_virtual_size_coalesces_when_scroll_already_pending() -> None:
    """Should not queue a second scroll if one is already pending."""
    vt = _make_vertical_tail(auto_scroll=True)

    vt.watch_virtual_size(Size(100, 200))
    vt.watch_virtual_size(Size(100, 300))
    vt.watch_virtual_size(Size(100, 400))

    assert vt.call_later.call_count == 1  # type: ignore[attr-defined]


def test_deferred_scroll_end_clears_pending_flag() -> None:
    """_deferred_scroll_end should reset the flag and call scroll_end."""
    vt = _make_vertical_tail(auto_scroll=True)
    vt._scroll_pending = True

    vt._deferred_scroll_end()

    assert vt._scroll_pending is False
    vt.scroll_end.assert_called_once_with(animate=False)  # type: ignore[attr-defined]


def test_scroll_can_be_queued_again_after_deferred_fires() -> None:
    """After _deferred_scroll_end runs, a new scroll can be queued."""
    vt = _make_vertical_tail(auto_scroll=True)

    vt.watch_virtual_size(Size(100, 200))
    assert vt.call_later.call_count == 1  # type: ignore[attr-defined]

    vt._deferred_scroll_end()
    assert vt._scroll_pending is False

    vt.watch_virtual_size(Size(100, 300))
    assert vt.call_later.call_count == 2  # type: ignore[attr-defined]
    assert vt._scroll_pending is True
