"""Constants for history processing and compaction."""

from enum import Enum

# Summary marker for compacted history
SUMMARY_MARKER = "📌 COMPACTED_HISTORY:"

# Token calculation constants
INPUT_BUFFER_TOKENS = 500
MIN_SUMMARY_TOKENS = 100
TOKEN_LIMIT_RATIO = 0.8

# Chunked compaction constants
CHUNK_TARGET_RATIO = 0.60  # Target chunk size as % of max_input_tokens
CHUNK_SAFE_RATIO = 0.70  # Max safe ratio before triggering chunked compaction
RETENTION_WINDOW_MESSAGES = 5  # Keep last N message groups outside compaction


class SummaryType(Enum):
    """Types of summarization requests for logging."""

    INCREMENTAL = "INCREMENTAL"
    FULL = "FULL"
    CONTEXT_EXTRACTION = "CONTEXT_EXTRACTION"
