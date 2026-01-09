"""Worker module for parallel file parsing.

This module provides the ParserWorker class and process_batch function
for parallel execution of file parsing across multiple processes.
"""

from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path
from typing import Any

from tree_sitter import Node, Parser, Query, QueryCursor

from shotgun.codebase.core.metrics_types import (
    FileParseMetrics,
    FileParseResult,
    FileParseTask,
    InheritanceData,
    NodeData,
    RawCallData,
    RelationshipData,
    WorkBatch,
)
from shotgun.codebase.core.parser_loader import load_parsers
from shotgun.logging_config import get_logger

logger = get_logger(__name__)

# Module-level lazy parser initialization (once per worker process)
_parsers: dict[str, Parser] | None = None
_queries: dict[str, dict[str, Query]] | None = None


def _ensure_parsers() -> tuple[dict[str, Parser], dict[str, Any]]:
    """Initialize parsers lazily in worker process.

    This ensures parsers are only loaded once per worker process,
    not once per file.

    Returns:
        Tuple of (parsers dict, queries dict)
    """
    global _parsers, _queries
    if _parsers is None:
        logger.debug("Initializing tree-sitter parsers in worker process")
        _parsers, _queries = load_parsers()
    return _parsers, _queries or {}


class ParserWorker:
    """Handles file parsing in a worker process.

    This class extracts all necessary data from source files:
    - Node definitions (Module, Class, Function, Method)
    - Direct relationships (DEFINES, DEFINES_METHOD, DEFINES_FUNC)
    - Raw call data for later resolution
    - Raw inheritance data for later resolution
    - Registry entries for aggregation

    The extracted data is returned without any database access,
    allowing the main process to aggregate and write to the database.
    """

    def __init__(self, worker_id: int = 0) -> None:
        """Initialize the worker.

        Args:
            worker_id: Unique identifier for this worker (for metrics)
        """
        self.worker_id = worker_id
        self.parsers, self.queries = _ensure_parsers()

    def process_file(self, task: FileParseTask) -> FileParseResult:
        """Parse a single file and extract all data.

        Args:
            task: File parsing task with path and metadata

        Returns:
            FileParseResult containing all extracted data
        """
        start_time = time.perf_counter()
        relative_path_str = str(task.relative_path).replace(os.sep, "/")

        # Initialize collections
        nodes: list[NodeData] = []
        relationships: list[RelationshipData] = []
        function_registry: dict[str, str] = {}
        simple_name_lookup: dict[str, list[str]] = {}
        raw_calls: list[RawCallData] = []
        inheritance_data: list[InheritanceData] = []
        ast_nodes_count = 0

        try:
            # Read file content
            with open(task.file_path, "rb") as f:
                content = f.read()

            # Calculate hash and mtime
            file_hash = hashlib.sha256(content).hexdigest()
            mtime = int(task.file_path.stat().st_mtime)
            file_size = len(content)

            # Check for empty files
            if not content.strip():
                return FileParseResult(
                    task=task,
                    success=True,
                    error=None,
                    nodes=nodes,
                    relationships=relationships,
                    function_registry_entries=function_registry,
                    simple_name_entries=simple_name_lookup,
                    raw_calls=raw_calls,
                    inheritance_data=inheritance_data,
                    file_hash=file_hash,
                    mtime=mtime,
                    metrics=FileParseMetrics(
                        file_path=relative_path_str,
                        language=task.language,
                        file_size_bytes=file_size,
                        parse_time_ms=(time.perf_counter() - start_time) * 1000,
                        ast_nodes=0,
                        definitions_extracted=0,
                        relationships_found=0,
                        worker_id=self.worker_id,
                    ),
                )

            # Parse file
            if task.language not in self.parsers:
                return FileParseResult(
                    task=task,
                    success=False,
                    error=f"No parser for language: {task.language}",
                    nodes=nodes,
                    relationships=relationships,
                    function_registry_entries=function_registry,
                    simple_name_entries=simple_name_lookup,
                    raw_calls=raw_calls,
                    inheritance_data=inheritance_data,
                    file_hash=file_hash,
                    mtime=mtime,
                    metrics=FileParseMetrics(
                        file_path=relative_path_str,
                        language=task.language,
                        file_size_bytes=file_size,
                        parse_time_ms=(time.perf_counter() - start_time) * 1000,
                        ast_nodes=0,
                        definitions_extracted=0,
                        relationships_found=0,
                        worker_id=self.worker_id,
                    ),
                )

            parser = self.parsers[task.language]
            tree = parser.parse(content)
            root_node = tree.root_node
            ast_nodes_count = self._count_ast_nodes(root_node)

            # Create File node
            nodes.append(
                NodeData(
                    label="File",
                    properties={
                        "path": relative_path_str,
                        "name": task.file_path.name,
                        "extension": task.file_path.suffix,
                    },
                )
            )

            # Create File containment relationship
            parent_rel_path = task.relative_path.parent
            if parent_rel_path == Path("."):
                # File in project root - will be linked to Project in main process
                pass  # Project relationship handled in main process
            else:
                relationships.append(
                    RelationshipData(
                        from_label="Folder",
                        from_key="path",
                        from_value=str(parent_rel_path).replace(os.sep, "/"),
                        rel_type="CONTAINS_FILE",
                        to_label="File",
                        to_key="path",
                        to_value=relative_path_str,
                    )
                )

            # Create Module node
            current_time = int(time.time())
            nodes.append(
                NodeData(
                    label="Module",
                    properties={
                        "qualified_name": task.module_qn,
                        "name": task.file_path.stem,
                        "path": relative_path_str,
                        "created_at": current_time,
                        "updated_at": current_time,
                    },
                )
            )

            # Create Module containment relationship
            if task.container_qn:
                relationships.append(
                    RelationshipData(
                        from_label="Package",
                        from_key="qualified_name",
                        from_value=task.container_qn,
                        rel_type="CONTAINS_MODULE",
                        to_label="Module",
                        to_key="qualified_name",
                        to_value=task.module_qn,
                    )
                )

            # Extract definitions
            self._extract_definitions(
                root_node=root_node,
                module_qn=task.module_qn,
                language=task.language,
                relative_path_str=relative_path_str,
                nodes=nodes,
                relationships=relationships,
                function_registry=function_registry,
                simple_name_lookup=simple_name_lookup,
                inheritance_data=inheritance_data,
            )

            # Extract raw calls for later resolution
            self._extract_calls(
                root_node=root_node,
                module_qn=task.module_qn,
                language=task.language,
                function_registry=function_registry,
                raw_calls=raw_calls,
            )

            parse_time_ms = (time.perf_counter() - start_time) * 1000
            definitions_count = sum(
                1 for n in nodes if n.label in ["Class", "Function", "Method"]
            )

            return FileParseResult(
                task=task,
                success=True,
                error=None,
                nodes=nodes,
                relationships=relationships,
                function_registry_entries=function_registry,
                simple_name_entries=simple_name_lookup,
                raw_calls=raw_calls,
                inheritance_data=inheritance_data,
                file_hash=file_hash,
                mtime=mtime,
                metrics=FileParseMetrics(
                    file_path=relative_path_str,
                    language=task.language,
                    file_size_bytes=file_size,
                    parse_time_ms=parse_time_ms,
                    ast_nodes=ast_nodes_count,
                    definitions_extracted=definitions_count,
                    relationships_found=len(relationships) + len(raw_calls),
                    worker_id=self.worker_id,
                ),
            )

        except Exception as e:
            logger.error(f"Failed to process {task.file_path}: {e}")
            parse_time_ms = (time.perf_counter() - start_time) * 1000

            return FileParseResult(
                task=task,
                success=False,
                error=str(e),
                nodes=nodes,
                relationships=relationships,
                function_registry_entries=function_registry,
                simple_name_entries=simple_name_lookup,
                raw_calls=raw_calls,
                inheritance_data=inheritance_data,
                file_hash="",
                mtime=0,
                metrics=FileParseMetrics(
                    file_path=relative_path_str,
                    language=task.language,
                    file_size_bytes=0,
                    parse_time_ms=parse_time_ms,
                    ast_nodes=ast_nodes_count,
                    definitions_extracted=0,
                    relationships_found=0,
                    worker_id=self.worker_id,
                ),
            )

    def process_batch(self, batch: WorkBatch) -> list[FileParseResult]:
        """Process all files in a batch.

        Args:
            batch: Work batch containing file tasks

        Returns:
            List of results for each file in the batch
        """
        results: list[FileParseResult] = []

        for task in batch.tasks:
            result = self.process_file(task)
            results.append(result)

        return results

    def _count_ast_nodes(self, node: Node) -> int:
        """Count total AST nodes for metrics."""
        count = 1
        for child in node.children:
            count += self._count_ast_nodes(child)
        return count

    def _extract_definitions(
        self,
        root_node: Node,
        module_qn: str,
        language: str,
        relative_path_str: str,
        nodes: list[NodeData],
        relationships: list[RelationshipData],
        function_registry: dict[str, str],
        simple_name_lookup: dict[str, list[str]],
        inheritance_data: list[InheritanceData],
    ) -> None:
        """Extract class and function definitions from AST."""
        lang_queries = self.queries.get(language, {})

        # Extract classes
        if "class_query" in lang_queries:
            self._extract_classes(
                root_node=root_node,
                module_qn=module_qn,
                language=language,
                relative_path_str=relative_path_str,
                class_query=lang_queries["class_query"],
                nodes=nodes,
                relationships=relationships,
                function_registry=function_registry,
                simple_name_lookup=simple_name_lookup,
                inheritance_data=inheritance_data,
            )

        # Extract functions
        if "function_query" in lang_queries:
            self._extract_functions(
                root_node=root_node,
                module_qn=module_qn,
                language=language,
                relative_path_str=relative_path_str,
                function_query=lang_queries["function_query"],
                nodes=nodes,
                relationships=relationships,
                function_registry=function_registry,
                simple_name_lookup=simple_name_lookup,
            )

    def _extract_classes(
        self,
        root_node: Node,
        module_qn: str,
        language: str,
        relative_path_str: str,
        class_query: Query,
        nodes: list[NodeData],
        relationships: list[RelationshipData],
        function_registry: dict[str, str],
        simple_name_lookup: dict[str, list[str]],
        inheritance_data: list[InheritanceData],
    ) -> None:
        """Extract class definitions."""
        cursor = QueryCursor(class_query)

        for match in cursor.matches(root_node):
            class_node = None
            class_name = None

            captures = match[1]
            for capture_name, capture_nodes in captures.items():
                for node in capture_nodes:
                    if capture_name in ["class", "interface", "type_alias"]:
                        class_node = node
                    elif capture_name == "class_name" and node.text:
                        class_name = node.text.decode("utf-8")

            if class_node and class_name:
                class_qn = f"{module_qn}.{class_name}"

                # Extract decorators
                decorators = self._extract_decorators(class_node, language)

                # Extract docstring
                docstring = self._extract_docstring(class_node, language)

                current_time = int(time.time())
                nodes.append(
                    NodeData(
                        label="Class",
                        properties={
                            "qualified_name": class_qn,
                            "name": class_name,
                            "decorators": decorators,
                            "line_start": class_node.start_point.row + 1,
                            "line_end": class_node.end_point.row + 1,
                            "created_at": current_time,
                            "updated_at": current_time,
                            "docstring": docstring,
                        },
                    )
                )

                # Create DEFINES relationship
                relationships.append(
                    RelationshipData(
                        from_label="Module",
                        from_key="qualified_name",
                        from_value=module_qn,
                        rel_type="DEFINES",
                        to_label="Class",
                        to_key="qualified_name",
                        to_value=class_qn,
                    )
                )

                # Create TRACKS relationship
                relationships.append(
                    RelationshipData(
                        from_label="FileMetadata",
                        from_key="path",
                        from_value=relative_path_str,
                        rel_type="TRACKS",
                        to_label="Class",
                        to_key="qualified_name",
                        to_value=class_qn,
                    )
                )

                # Register for lookup
                function_registry[class_qn] = "Class"
                if class_name not in simple_name_lookup:
                    simple_name_lookup[class_name] = []
                simple_name_lookup[class_name].append(class_qn)

                # Extract inheritance
                parent_names = self._extract_inheritance(class_node, language)
                if parent_names:
                    inheritance_data.append(
                        InheritanceData(
                            child_class_qn=class_qn,
                            parent_simple_names=parent_names,
                        )
                    )

    def _extract_functions(
        self,
        root_node: Node,
        module_qn: str,
        language: str,
        relative_path_str: str,
        function_query: Query,
        nodes: list[NodeData],
        relationships: list[RelationshipData],
        function_registry: dict[str, str],
        simple_name_lookup: dict[str, list[str]],
    ) -> None:
        """Extract function and method definitions."""
        cursor = QueryCursor(function_query)
        matches = list(cursor.matches(root_node))

        for match in matches:
            func_node = None
            func_name = None

            captures = match[1]
            for capture_name, capture_nodes in captures.items():
                for node in capture_nodes:
                    if capture_name == "function":
                        func_node = node
                    elif capture_name == "function_name" and node.text:
                        func_name = node.text.decode("utf-8")

            if func_node and func_name:
                # Check if this is a method inside a class
                parent_class = self._find_parent_class(func_node, module_qn)

                if parent_class:
                    # This is a method
                    method_qn = f"{parent_class}.{func_name}"
                    decorators = self._extract_decorators(func_node, language)
                    docstring = self._extract_docstring(func_node, language)

                    current_time = int(time.time())
                    nodes.append(
                        NodeData(
                            label="Method",
                            properties={
                                "qualified_name": method_qn,
                                "name": func_name,
                                "decorators": decorators,
                                "line_start": func_node.start_point.row + 1,
                                "line_end": func_node.end_point.row + 1,
                                "created_at": current_time,
                                "updated_at": current_time,
                                "docstring": docstring,
                            },
                        )
                    )

                    # Create DEFINES_METHOD relationship
                    relationships.append(
                        RelationshipData(
                            from_label="Class",
                            from_key="qualified_name",
                            from_value=parent_class,
                            rel_type="DEFINES_METHOD",
                            to_label="Method",
                            to_key="qualified_name",
                            to_value=method_qn,
                        )
                    )

                    # Create TRACKS relationship
                    relationships.append(
                        RelationshipData(
                            from_label="FileMetadata",
                            from_key="path",
                            from_value=relative_path_str,
                            rel_type="TRACKS",
                            to_label="Method",
                            to_key="qualified_name",
                            to_value=method_qn,
                        )
                    )

                    # Register for lookup
                    function_registry[method_qn] = "Method"
                    if func_name not in simple_name_lookup:
                        simple_name_lookup[func_name] = []
                    simple_name_lookup[func_name].append(method_qn)
                else:
                    # This is a standalone function
                    func_qn = f"{module_qn}.{func_name}"
                    decorators = self._extract_decorators(func_node, language)
                    docstring = self._extract_docstring(func_node, language)

                    current_time = int(time.time())
                    nodes.append(
                        NodeData(
                            label="Function",
                            properties={
                                "qualified_name": func_qn,
                                "name": func_name,
                                "decorators": decorators,
                                "line_start": func_node.start_point.row + 1,
                                "line_end": func_node.end_point.row + 1,
                                "created_at": current_time,
                                "updated_at": current_time,
                                "docstring": docstring,
                            },
                        )
                    )

                    # Create DEFINES_FUNC relationship
                    relationships.append(
                        RelationshipData(
                            from_label="Module",
                            from_key="qualified_name",
                            from_value=module_qn,
                            rel_type="DEFINES_FUNC",
                            to_label="Function",
                            to_key="qualified_name",
                            to_value=func_qn,
                        )
                    )

                    # Create TRACKS relationship
                    relationships.append(
                        RelationshipData(
                            from_label="FileMetadata",
                            from_key="path",
                            from_value=relative_path_str,
                            rel_type="TRACKS",
                            to_label="Function",
                            to_key="qualified_name",
                            to_value=func_qn,
                        )
                    )

                    # Register for lookup
                    function_registry[func_qn] = "Function"
                    if func_name not in simple_name_lookup:
                        simple_name_lookup[func_name] = []
                    simple_name_lookup[func_name].append(func_qn)

    def _extract_calls(
        self,
        root_node: Node,
        module_qn: str,
        language: str,
        function_registry: dict[str, str],
        raw_calls: list[RawCallData],
    ) -> None:
        """Extract raw call data for later resolution."""
        lang_queries = self.queries.get(language, {})

        if "call_query" not in lang_queries:
            return

        cursor = QueryCursor(lang_queries["call_query"])
        matches = list(cursor.matches(root_node))

        for match in matches:
            call_node = None

            captures = match[1]
            for capture_name, capture_nodes in captures.items():
                for node in capture_nodes:
                    if capture_name == "call":
                        call_node = node
                        break

            if call_node:
                self._extract_single_call(
                    call_node=call_node,
                    module_qn=module_qn,
                    language=language,
                    function_registry=function_registry,
                    raw_calls=raw_calls,
                )

    def _extract_single_call(
        self,
        call_node: Node,
        module_qn: str,
        language: str,
        function_registry: dict[str, str],
        raw_calls: list[RawCallData],
    ) -> None:
        """Extract data from a single call expression."""
        callee_name = None
        object_name = None

        if language in ["python", "javascript", "typescript"]:
            for child in call_node.children:
                if child.type == "identifier" and child.text:
                    callee_name = child.text.decode("utf-8")
                    break
                elif child.type == "attribute":
                    obj_node = child.child_by_field_name("object")
                    attr_node = child.child_by_field_name("attribute")
                    if obj_node and obj_node.text:
                        object_name = obj_node.text.decode("utf-8")
                    if attr_node and attr_node.text:
                        callee_name = attr_node.text.decode("utf-8")
                        break

        if not callee_name:
            return

        # Find caller function
        caller_qn = self._find_containing_function(call_node, module_qn)
        if not caller_qn:
            return

        # Only record if caller is in our registry (we know about it)
        if caller_qn not in function_registry:
            return

        raw_calls.append(
            RawCallData(
                caller_qn=caller_qn,
                callee_name=callee_name,
                object_name=object_name,
                line_number=call_node.start_point.row + 1,
                module_qn=module_qn,
            )
        )

    def _extract_decorators(self, node: Node, language: str) -> list[str]:
        """Extract decorators from a function/class node."""
        decorators = []

        if language == "python":
            for child in node.children:
                if child.type == "decorator":
                    for grandchild in child.children:
                        if grandchild.type == "identifier" and grandchild.text:
                            decorators.append(grandchild.text.decode("utf-8"))
                            break
                        elif grandchild.type == "attribute":
                            attr_node = grandchild.child_by_field_name("attribute")
                            if attr_node and attr_node.text:
                                decorators.append(attr_node.text.decode("utf-8"))
                                break

        return decorators

    def _extract_docstring(self, node: Node, language: str) -> str | None:
        """Extract docstring from function/class node."""
        if language == "python":
            body_node = node.child_by_field_name("body")
            if not body_node or not body_node.children:
                return None

            first_statement = body_node.children[0]
            if first_statement.type == "expression_statement":
                for child in first_statement.children:
                    if child.type == "string" and child.text:
                        docstring = child.text.decode("utf-8")
                        docstring = docstring.strip()
                        if (
                            docstring.startswith('"""')
                            and docstring.endswith('"""')
                            or docstring.startswith("'''")
                            and docstring.endswith("'''")
                        ):
                            docstring = docstring[3:-3]
                        elif (
                            docstring.startswith('"')
                            and docstring.endswith('"')
                            or docstring.startswith("'")
                            and docstring.endswith("'")
                        ):
                            docstring = docstring[1:-1]
                        return docstring.strip()
        return None

    def _extract_inheritance(self, class_node: Node, language: str) -> list[str]:
        """Extract parent class names from class definition."""
        parent_names = []

        if language == "python":
            for child in class_node.children:
                if child.type == "argument_list":
                    for arg in child.children:
                        if arg.type == "identifier" and arg.text:
                            parent_names.append(arg.text.decode("utf-8"))
                        elif arg.type == "attribute":
                            full_name_parts: list[str] = []
                            self._extract_full_name(arg, full_name_parts)
                            if full_name_parts:
                                parent_names.append(".".join(full_name_parts))

        return parent_names

    def _extract_full_name(self, node: Node, parts: list[str]) -> None:
        """Recursively extract full qualified name from attribute access."""
        if node.type == "identifier" and node.text:
            parts.insert(0, node.text.decode("utf-8"))
        elif node.type == "attribute":
            attr_node = node.child_by_field_name("attribute")
            if attr_node and attr_node.text:
                parts.insert(0, attr_node.text.decode("utf-8"))

            obj_node = node.child_by_field_name("object")
            if obj_node:
                self._extract_full_name(obj_node, parts)

    def _find_parent_class(self, func_node: Node, module_qn: str) -> str | None:
        """Find the parent class of a function node."""
        current = func_node.parent

        while current:
            if current.type in ["class_definition", "class_declaration"]:
                for child in current.children:
                    if child.type == "identifier" and child.text:
                        class_name = child.text.decode("utf-8")
                        return f"{module_qn}.{class_name}"

            current = current.parent

        return None

    def _find_containing_function(self, node: Node, module_qn: str) -> str | None:
        """Find the containing function/method of a node."""
        current = node.parent

        while current:
            if current.type in [
                "function_definition",
                "method_definition",
                "arrow_function",
            ]:
                for child in current.children:
                    if child.type == "identifier" and child.text:
                        func_name = child.text.decode("utf-8")

                        parent_class = self._find_parent_class(current, module_qn)
                        if parent_class:
                            return f"{parent_class}.{func_name}"
                        else:
                            return f"{module_qn}.{func_name}"

            current = current.parent

        return None


def process_batch(batch: WorkBatch, worker_id: int = 0) -> list[FileParseResult]:
    """Entry point for worker processes.

    This is the top-level function called by ProcessPoolExecutor.

    Args:
        batch: Work batch to process
        worker_id: Worker identifier for metrics

    Returns:
        List of parse results for all files in the batch
    """
    worker = ParserWorker(worker_id=worker_id)
    return worker.process_batch(batch)
