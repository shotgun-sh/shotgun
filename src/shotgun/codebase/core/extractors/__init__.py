"""Language-specific AST extraction framework.

This module provides a Protocol-based architecture for extracting
definitions, relationships, and metadata from source code ASTs.

Usage:
    from shotgun.codebase.core.extractors import get_extractor, SupportedLanguage

    extractor = get_extractor(SupportedLanguage.PYTHON)
    decorators = extractor.extract_decorators(node)
"""

from __future__ import annotations

from .factory import get_extractor
from .protocol import LanguageExtractor
from .types import SupportedLanguage

__all__ = [
    "SupportedLanguage",
    "LanguageExtractor",
    "get_extractor",
]
