"""Constants for history processing and compaction."""

from enum import Enum

# Summary marker for compacted history
SUMMARY_MARKER = "📌 COMPACTED_HISTORY:"

# Token calculation constants
INPUT_BUFFER_TOKENS = 500
MIN_SUMMARY_TOKENS = 100
TOKEN_LIMIT_RATIO = 0.8


class SummaryType(Enum):
    """Types of summarization requests for logging."""

    INCREMENTAL = "INCREMENTAL"
    FULL = "FULL"
    CONTEXT_EXTRACTION = "CONTEXT_EXTRACTION"
