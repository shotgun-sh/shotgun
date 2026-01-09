"""JavaScript language extractor implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from shotgun.codebase.core.extractors.base import BaseExtractor
from shotgun.codebase.core.extractors.types import SupportedLanguage

if TYPE_CHECKING:
    from tree_sitter import Node


class JavaScriptExtractor(BaseExtractor):
    """Extractor for JavaScript source code."""

    @property
    def language(self) -> SupportedLanguage:
        """The language this extractor handles."""
        return SupportedLanguage.JAVASCRIPT

    def _class_definition_types(self) -> list[str]:
        """Return node types that represent class definitions."""
        return ["class_declaration", "class"]

    def _function_definition_types(self) -> list[str]:
        """Return node types that represent function definitions."""
        return ["function_declaration", "method_definition", "arrow_function"]

    def extract_decorators(self, node: Node) -> list[str]:
        """Extract decorators from a function or class node.

        JavaScript doesn't have native decorators (they're a proposal).
        Returns empty list.

        Args:
            node: The AST node

        Returns:
            Empty list (JavaScript has no decorators)
        """
        return []

    def extract_docstring(self, node: Node) -> str | None:
        """Extract JSDoc comment from a function or class node.

        Args:
            node: The AST node

        Returns:
            The JSDoc content, or None if not present
        """
        prev_sibling = node.prev_named_sibling
        if prev_sibling and prev_sibling.type == "comment":
            comment_text = prev_sibling.text
            if comment_text:
                text = comment_text.decode("utf-8")
                if text.startswith("/**"):
                    text = text[3:]
                    if text.endswith("*/"):
                        text = text[:-2]
                    return text.strip()
        return None

    def extract_inheritance(self, class_node: Node) -> list[str]:
        """Extract parent class names from a class definition.

        Args:
            class_node: The class definition AST node

        Returns:
            List of parent class names
        """
        parent_names: list[str] = []

        heritage = class_node.child_by_field_name("heritage")
        if heritage:
            for child in heritage.children:
                if child.type == "identifier" and child.text:
                    parent_names.append(child.text.decode("utf-8"))
                elif child.type == "member_expression":
                    parts: list[str] = []
                    self._extract_member_expression(child, parts)
                    if parts:
                        parent_names.append(".".join(parts))

        return parent_names

    def parse_call_node(self, call_node: Node) -> tuple[str | None, str | None]:
        """Parse a call expression node to extract callee information.

        Args:
            call_node: The call expression AST node

        Returns:
            Tuple of (callee_name, object_name)
        """
        callee_name = None
        object_name = None

        for child in call_node.children:
            if child.type == "identifier" and child.text:
                callee_name = child.text.decode("utf-8")
                break
            elif child.type == "member_expression":
                obj_node = child.child_by_field_name("object")
                prop_node = child.child_by_field_name("property")
                if obj_node and obj_node.text:
                    object_name = obj_node.text.decode("utf-8")
                if prop_node and prop_node.text:
                    callee_name = prop_node.text.decode("utf-8")
                    break

        return callee_name, object_name

    def _extract_member_expression(self, node: Node, parts: list[str]) -> None:
        """Recursively extract full name from member expression.

        Args:
            node: The AST node
            parts: List to accumulate name parts (modified in place)
        """
        if node.type == "identifier" and node.text:
            parts.insert(0, node.text.decode("utf-8"))
        elif node.type == "member_expression":
            prop_node = node.child_by_field_name("property")
            if prop_node and prop_node.text:
                parts.insert(0, prop_node.text.decode("utf-8"))

            obj_node = node.child_by_field_name("object")
            if obj_node:
                self._extract_member_expression(obj_node, parts)
