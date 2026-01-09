"""Factory for creating language-specific extractors."""

from __future__ import annotations

from .protocol import LanguageExtractor
from .types import SupportedLanguage

# Cache of extractor instances (created lazily)
_extractors: dict[SupportedLanguage, LanguageExtractor] = {}


def get_extractor(language: SupportedLanguage | str) -> LanguageExtractor:
    """Get the extractor for a language.

    Args:
        language: The language as enum or string

    Returns:
        The language extractor instance

    Raises:
        ValueError: If language is not supported
    """
    if isinstance(language, str):
        language = SupportedLanguage(language)

    if language not in _extractors:
        _extractors[language] = _create_extractor(language)

    return _extractors[language]


def _create_extractor(language: SupportedLanguage) -> LanguageExtractor:
    """Create a new extractor instance for the language.

    Uses lazy imports to avoid loading all extractors at once.
    """
    match language:
        case SupportedLanguage.PYTHON:
            from .python.extractor import PythonExtractor

            return PythonExtractor()
        case SupportedLanguage.JAVASCRIPT:
            from .javascript.extractor import JavaScriptExtractor

            return JavaScriptExtractor()
        case SupportedLanguage.TYPESCRIPT:
            from .typescript.extractor import TypeScriptExtractor

            return TypeScriptExtractor()
        case SupportedLanguage.GO:
            from .go.extractor import GoExtractor

            return GoExtractor()
        case SupportedLanguage.RUST:
            from .rust.extractor import RustExtractor

            return RustExtractor()


def clear_extractor_cache() -> None:
    """Clear the extractor cache (useful for testing)."""
    _extractors.clear()
