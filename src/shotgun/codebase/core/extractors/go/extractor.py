"""Go language extractor implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from shotgun.codebase.core.extractors.base import BaseExtractor
from shotgun.codebase.core.extractors.types import SupportedLanguage

if TYPE_CHECKING:
    from tree_sitter import Node


class GoExtractor(BaseExtractor):
    """Extractor for Go source code."""

    @property
    def language(self) -> SupportedLanguage:
        """The language this extractor handles."""
        return SupportedLanguage.GO

    def _class_definition_types(self) -> list[str]:
        """Return node types that represent type definitions.

        Go doesn't have classes but has type definitions and interfaces.
        """
        return ["type_declaration", "type_spec"]

    def _function_definition_types(self) -> list[str]:
        """Return node types that represent function definitions."""
        return ["function_declaration", "method_declaration"]

    def extract_decorators(self, node: Node) -> list[str]:
        """Extract decorators from a function node.

        Go doesn't have decorators. Returns empty list.

        Args:
            node: The AST node

        Returns:
            Empty list (Go has no decorators)
        """
        return []

    def extract_docstring(self, node: Node) -> str | None:
        """Extract godoc comment from a function or type node.

        Args:
            node: The AST node

        Returns:
            The godoc comment, or None if not present
        """
        prev_sibling = node.prev_named_sibling
        if prev_sibling and prev_sibling.type == "comment":
            comment_text = prev_sibling.text
            if comment_text:
                text = comment_text.decode("utf-8")
                if text.startswith("//"):
                    return text[2:].strip()
        return None

    def extract_inheritance(self, class_node: Node) -> list[str]:
        """Extract embedded types from a struct or interface.

        Go uses composition instead of inheritance.
        This extracts embedded type names from struct/interface definitions.

        Args:
            class_node: The type definition AST node

        Returns:
            List of embedded type names
        """
        embedded: list[str] = []

        for child in class_node.children:
            if child.type == "struct_type":
                field_list = child.child_by_field_name("fields")
                if field_list:
                    for field in field_list.children:
                        if field.type == "field_declaration":
                            if len(field.named_children) == 1:
                                type_node = field.named_children[0]
                                if (
                                    type_node.type == "type_identifier"
                                    and type_node.text
                                ):
                                    embedded.append(type_node.text.decode("utf-8"))
            elif child.type == "interface_type":
                for iface_child in child.children:
                    if iface_child.type == "type_identifier" and iface_child.text:
                        embedded.append(iface_child.text.decode("utf-8"))

        return embedded

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
            elif func_node.type == "selector_expression":
                operand = func_node.child_by_field_name("operand")
                field = func_node.child_by_field_name("field")
                if operand and operand.text:
                    object_name = operand.text.decode("utf-8")
                if field and field.text:
                    callee_name = field.text.decode("utf-8")

        return callee_name, object_name
