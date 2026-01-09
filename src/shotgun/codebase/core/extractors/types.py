"""Type definitions for the extractors module."""

from __future__ import annotations

from enum import StrEnum


class SupportedLanguage(StrEnum):
    """Supported programming languages for AST extraction."""

    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    GO = "go"
    RUST = "rust"
