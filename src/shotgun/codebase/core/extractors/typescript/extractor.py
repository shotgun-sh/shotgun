"""TypeScript language extractor implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from shotgun.codebase.core.extractors.javascript.extractor import JavaScriptExtractor
from shotgun.codebase.core.extractors.types import SupportedLanguage

if TYPE_CHECKING:
    from tree_sitter import Node


class TypeScriptExtractor(JavaScriptExtractor):
    """Extractor for TypeScript source code.

    TypeScript is a superset of JavaScript, so this extends
    JavaScriptExtractor with TypeScript-specific features.
    """

    @property
    def language(self) -> SupportedLanguage:
        """The language this extractor handles."""
        return SupportedLanguage.TYPESCRIPT

    def _class_definition_types(self) -> list[str]:
        """Return node types that represent class definitions.

        TypeScript adds interface_declaration and type_alias_declaration.
        """
        return [
            "class_declaration",
            "class",
            "interface_declaration",
            "type_alias_declaration",
        ]

    def extract_decorators(self, node: Node) -> list[str]:
        """Extract decorators from a function or class node.

        TypeScript supports decorators (experimental feature).

        Args:
            node: The AST node

        Returns:
            List of decorator names
        """
        decorators: list[str] = []

        for child in node.children:
            if child.type == "decorator":
                for grandchild in child.children:
                    if grandchild.type == "identifier" and grandchild.text:
                        decorators.append(grandchild.text.decode("utf-8"))
                        break
                    elif grandchild.type == "call_expression":
                        for call_child in grandchild.children:
                            if call_child.type == "identifier" and call_child.text:
                                decorators.append(call_child.text.decode("utf-8"))
                                break

        return decorators

    def extract_inheritance(self, class_node: Node) -> list[str]:
        """Extract parent class/interface names from a class or interface.

        TypeScript classes can extend one class and implement multiple interfaces.
        Interfaces can extend multiple interfaces.

        Args:
            class_node: The class/interface definition AST node

        Returns:
            List of parent names
        """
        parent_names: list[str] = []

        for child in class_node.children:
            if child.type in ["extends_clause", "implements_clause"]:
                for type_node in child.children:
                    if type_node.type == "type_identifier" and type_node.text:
                        parent_names.append(type_node.text.decode("utf-8"))
                    elif type_node.type == "generic_type":
                        name_node = type_node.child_by_field_name("name")
                        if name_node and name_node.text:
                            parent_names.append(name_node.text.decode("utf-8"))

        if not parent_names:
            parent_names = super().extract_inheritance(class_node)

        return parent_names
