"""Tests for the extractor factory."""

from __future__ import annotations

import pytest

from shotgun.codebase.core.extractors import (
    LanguageExtractor,
    SupportedLanguage,
    get_extractor,
)
from shotgun.codebase.core.extractors.factory import clear_extractor_cache
from shotgun.codebase.core.extractors.go.extractor import GoExtractor
from shotgun.codebase.core.extractors.javascript.extractor import JavaScriptExtractor
from shotgun.codebase.core.extractors.python.extractor import PythonExtractor
from shotgun.codebase.core.extractors.rust.extractor import RustExtractor
from shotgun.codebase.core.extractors.typescript.extractor import TypeScriptExtractor


@pytest.fixture(autouse=True)
def clear_cache_before_each_test():
    """Clear the extractor cache before each test."""
    clear_extractor_cache()


def test_get_extractor_returns_python_extractor():
    """Test that get_extractor returns PythonExtractor for Python."""
    extractor = get_extractor(SupportedLanguage.PYTHON)
    assert isinstance(extractor, PythonExtractor)
    assert extractor.language == SupportedLanguage.PYTHON


def test_get_extractor_returns_javascript_extractor():
    """Test that get_extractor returns JavaScriptExtractor for JavaScript."""
    extractor = get_extractor(SupportedLanguage.JAVASCRIPT)
    assert isinstance(extractor, JavaScriptExtractor)
    assert extractor.language == SupportedLanguage.JAVASCRIPT


def test_get_extractor_returns_typescript_extractor():
    """Test that get_extractor returns TypeScriptExtractor for TypeScript."""
    extractor = get_extractor(SupportedLanguage.TYPESCRIPT)
    assert isinstance(extractor, TypeScriptExtractor)
    assert extractor.language == SupportedLanguage.TYPESCRIPT


def test_get_extractor_returns_go_extractor():
    """Test that get_extractor returns GoExtractor for Go."""
    extractor = get_extractor(SupportedLanguage.GO)
    assert isinstance(extractor, GoExtractor)
    assert extractor.language == SupportedLanguage.GO


def test_get_extractor_returns_rust_extractor():
    """Test that get_extractor returns RustExtractor for Rust."""
    extractor = get_extractor(SupportedLanguage.RUST)
    assert isinstance(extractor, RustExtractor)
    assert extractor.language == SupportedLanguage.RUST


def test_get_extractor_accepts_string():
    """Test that get_extractor accepts string language names."""
    extractor = get_extractor("python")
    assert isinstance(extractor, PythonExtractor)


def test_get_extractor_caches_instances():
    """Test that get_extractor returns the same instance for same language."""
    extractor1 = get_extractor(SupportedLanguage.PYTHON)
    extractor2 = get_extractor(SupportedLanguage.PYTHON)
    assert extractor1 is extractor2


def test_get_extractor_raises_for_invalid_language():
    """Test that get_extractor raises ValueError for invalid language."""
    with pytest.raises(ValueError):
        get_extractor("invalid_language")


def test_all_extractors_satisfy_protocol():
    """Test that all extractors satisfy the LanguageExtractor protocol."""
    for lang in SupportedLanguage:
        extractor = get_extractor(lang)
        assert isinstance(extractor, LanguageExtractor)


def test_supported_language_enum_values():
    """Test that SupportedLanguage has correct string values."""
    assert SupportedLanguage.PYTHON == "python"
    assert SupportedLanguage.JAVASCRIPT == "javascript"
    assert SupportedLanguage.TYPESCRIPT == "typescript"
    assert SupportedLanguage.GO == "go"
    assert SupportedLanguage.RUST == "rust"
