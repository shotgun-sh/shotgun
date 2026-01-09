"""Tests for the Rust extractor."""

from __future__ import annotations

import pytest

from shotgun.codebase.core.extractors.rust.extractor import RustExtractor
from shotgun.codebase.core.extractors.types import SupportedLanguage
from shotgun.codebase.core.parser_loader import load_parsers


@pytest.fixture
def extractor():
    """Create a Rust extractor."""
    return RustExtractor()


@pytest.fixture
def parsers():
    """Load tree-sitter parsers."""
    parsers, _ = load_parsers()
    return parsers


def test_rust_extractor_has_correct_language(extractor: RustExtractor):
    """Test that RustExtractor reports correct language."""
    assert extractor.language == SupportedLanguage.RUST


def test_class_definition_types(extractor: RustExtractor):
    """Test that class definition types include Rust type definitions."""
    types = extractor._class_definition_types()
    assert "struct_item" in types
    assert "enum_item" in types
    assert "trait_item" in types
    assert "type_item" in types


def test_function_definition_types(extractor: RustExtractor):
    """Test that function definition types include Rust function types."""
    types = extractor._function_definition_types()
    assert "function_item" in types
    assert "function_signature_item" in types


def test_count_ast_nodes(extractor: RustExtractor, parsers: dict):
    """Test counting AST nodes."""
    code = b"""
fn main() {
    let x = 1;
}
"""
    tree = parsers["rust"].parse(code)

    count = extractor.count_ast_nodes(tree.root_node)
    assert count > 0
