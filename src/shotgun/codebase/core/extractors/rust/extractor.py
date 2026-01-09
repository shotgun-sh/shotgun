"""Rust language extractor implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from shotgun.codebase.core.extractors.base import BaseExtractor
from shotgun.codebase.core.extractors.types import SupportedLanguage

if TYPE_CHECKING:
    from tree_sitter import Node


class RustExtractor(BaseExtractor):
    """Extractor for Rust source code."""

    @property
    def language(self) -> SupportedLanguage:
        """The language this extractor handles."""
        return SupportedLanguage.RUST

    def _class_definition_types(self) -> list[str]:
        """Return node types that represent type definitions.

        Rust has structs, enums, traits, and type aliases.
        """
        return ["struct_item", "enum_item", "trait_item", "type_item"]

    def _function_definition_types(self) -> list[str]:
        """Return node types that represent function definitions."""
        return ["function_item", "function_signature_item"]

    def extract_decorators(self, node: Node) -> list[str]:
        """Extract attributes from a function or struct node.

        Rust uses #[attribute] syntax.

        Args:
            node: The AST node

        Returns:
            List of attribute names
        """
        attributes: list[str] = []

        for child in node.children:
            if child.type == "attribute_item":
                for attr_child in child.children:
                    if attr_child.type == "attribute":
                        path = attr_child.child_by_field_name("path")
                        if path and path.text:
                            attributes.append(path.text.decode("utf-8"))

        return attributes

    def extract_docstring(self, node: Node) -> str | None:
        """Extract doc comment from a function or type node.

        Rust uses /// for outer doc comments and //! for inner doc comments.

        Args:
            node: The AST node

        Returns:
            The doc comment, or None if not present
        """
        doc_lines: list[str] = []
        prev_sibling = node.prev_named_sibling

        while prev_sibling and prev_sibling.type == "line_comment":
            comment_text = prev_sibling.text
            if comment_text:
                text = comment_text.decode("utf-8")
                if text.startswith("///"):
                    doc_lines.insert(0, text[3:].strip())
                else:
                    break
            prev_sibling = prev_sibling.prev_named_sibling

        if doc_lines:
            return "\n".join(doc_lines)
        return None

    def extract_inheritance(self, class_node: Node) -> list[str]:
        """Extract trait bounds or supertraits from a type definition.

        For structs, this returns nothing (Rust doesn't have struct inheritance).
        For traits, this returns supertraits.

        Args:
            class_node: The type definition AST node

        Returns:
            List of supertrait names
        """
        supertraits: list[str] = []

        if class_node.type == "trait_item":
            for child in class_node.children:
                if child.type == "trait_bounds":
                    for bound in child.children:
                        if bound.type == "type_identifier" and bound.text:
                            supertraits.append(bound.text.decode("utf-8"))
                        elif bound.type == "generic_type":
                            type_node = bound.child_by_field_name("type")
                            if type_node and type_node.text:
                                supertraits.append(type_node.text.decode("utf-8"))

        return supertraits

    def parse_call_node(self, call_node: Node) -> tuple[str | None, str | None]:
        """Parse a call expression node to extract callee information.

        Args:
            call_node: The call expression AST node

        Returns:
            Tuple of (callee_name, object_name)
        """
        callee_name = None
        object_name = None

        func_node = call_node.child_by_field_name("function")
        if func_node:
            if func_node.type == "identifier" and func_node.text:
                callee_name = func_node.text.decode("utf-8")
            elif func_node.type == "field_expression":
                value = func_node.child_by_field_name("value")
                field = func_node.child_by_field_name("field")
                if value and value.text:
                    object_name = value.text.decode("utf-8")
                if field and field.text:
                    callee_name = field.text.decode("utf-8")
            elif func_node.type == "scoped_identifier":
                name = func_node.child_by_field_name("name")
                if name and name.text:
                    callee_name = name.text.decode("utf-8")

        return callee_name, object_name
