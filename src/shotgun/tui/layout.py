"""Layout utilities for responsive terminal UI."""

# Height thresholds for responsive layouts
TINY_HEIGHT_THRESHOLD = 25  # Below this: minimal UI, hide most content
COMPACT_HEIGHT_THRESHOLD = 35  # Below this: reduced padding, hide verbose text


def is_tiny_height(height: int) -> bool:
    """Check if terminal height requires tiny/minimal layout."""
    return height < TINY_HEIGHT_THRESHOLD


def is_compact_height(height: int) -> bool:
    """Check if terminal height requires compact layout."""
    return height < COMPACT_HEIGHT_THRESHOLD
