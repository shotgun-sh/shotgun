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

from shotgun.codebase.core.extractors import LanguageExtractor, get_extractor
from shotgun.codebase.core.metrics_types import (
    FileParseMetrics,
    FileParseResult,
    FileParseTask,
    InheritanceData,
    NodeData,
    NodeLabel,
    RawCallData,
    RelationshipData,
    RelationshipType,
    WorkBatch,
)
from shotgun.codebase.core.parser_loader import load_parsers
from shotgun.logging_config import get_logger

logger = get_logger(__name__)

# Module-level lazy parser initialization (once per worker process)
_parsers: dict[str, Parser] | None = None
_queries: dict[str, dict[str, Query]] | None = None


def _ensure_parsers() -> tuple[dict[str, Parser], dict[str, Any]]:
    """Initialize parsers lazily in worker process."""
    global _parsers, _queries
    if _parsers is None:
        logger.debug("Initializing tree-sitter parsers in worker process")
        _parsers, _queries = load_parsers()
    return _parsers, _queries or {}


class ParserWorker:
    """Handles file parsing in a worker process.

    Extracts definitions, relationships, and registry data from source files
    without database access, allowing the main process to aggregate results.
    """

    def __init__(self, worker_id: int = 0) -> None:
        """Initialize the worker."""
        self.worker_id = worker_id
        self.parsers, self.queries = _ensure_parsers()

    def process_file(self, task: FileParseTask) -> FileParseResult:
        """Parse a single file and extract all data."""
        start_time = time.perf_counter()
        relative_path_str = str(task.relative_path).replace(os.sep, "/")

        nodes: list[NodeData] = []
        relationships: list[RelationshipData] = []
        function_registry: dict[str, str] = {}
        simple_name_lookup: dict[str, list[str]] = {}
        raw_calls: list[RawCallData] = []
        inheritance_data: list[InheritanceData] = []
        ast_nodes_count = 0

        try:
            content, file_hash, mtime, file_size = self._read_file(task.file_path)

            if not content.strip():
                return self._empty_result(
                    task,
                    nodes,
                    relationships,
                    function_registry,
                    simple_name_lookup,
                    raw_calls,
                    inheritance_data,
                    file_hash,
                    mtime,
                    file_size,
                    start_time,
                    relative_path_str,
                )

            if task.language not in self.parsers:
                return self._error_result(
                    task,
                    f"No parser for language: {task.language}",
                    file_hash,
                    mtime,
                    file_size,
                    start_time,
                    relative_path_str,
                )

            tree = self.parsers[task.language].parse(content)
            root_node = tree.root_node
            extractor = get_extractor(task.language)
            ast_nodes_count = extractor.count_ast_nodes(root_node)

            self._create_file_node(task, relative_path_str, nodes, relationships)
            self._create_module_node(task, relative_path_str, nodes, relationships)
            self._create_file_metadata_node(relative_path_str, file_hash, mtime, nodes)

            self._extract_definitions(
                root_node,
                task.module_qn,
                task.language,
                relative_path_str,
                extractor,
                nodes,
                relationships,
                function_registry,
                simple_name_lookup,
                inheritance_data,
            )

            self._extract_calls(
                root_node,
                task.module_qn,
                task.language,
                extractor,
                function_registry,
                raw_calls,
            )

            return self._success_result(
                task,
                nodes,
                relationships,
                function_registry,
                simple_name_lookup,
                raw_calls,
                inheritance_data,
                file_hash,
                mtime,
                file_size,
                ast_nodes_count,
                start_time,
                relative_path_str,
            )

        except Exception as e:
            logger.error(f"Failed to process {task.file_path}: {e}")
            return self._error_result(
                task, str(e), "", 0, 0, start_time, relative_path_str
            )

    def process_batch(self, batch: WorkBatch) -> list[FileParseResult]:
        """Process all files in a batch."""
        return [self.process_file(task) for task in batch.tasks]

    def _read_file(self, file_path: Path) -> tuple[bytes, str, int, int]:
        """Read file and compute metadata."""
        with open(file_path, "rb") as f:
            content = f.read()
        return (
            content,
            hashlib.sha256(content).hexdigest(),
            int(file_path.stat().st_mtime),
            len(content),
        )

    def _create_file_node(
        self,
        task: FileParseTask,
        relative_path_str: str,
        nodes: list[NodeData],
        relationships: list[RelationshipData],
    ) -> None:
        """Create File node and containment relationship."""
        nodes.append(
            NodeData(
                label=NodeLabel.FILE,
                properties={
                    "path": relative_path_str,
                    "name": task.file_path.name,
                    "extension": task.file_path.suffix,
                },
            )
        )

        parent_rel_path = task.relative_path.parent
        if parent_rel_path != Path("."):
            relationships.append(
                RelationshipData(
                    from_label=NodeLabel.FOLDER,
                    from_key="path",
                    from_value=str(parent_rel_path).replace(os.sep, "/"),
                    rel_type=RelationshipType.CONTAINS_FILE,
                    to_label=NodeLabel.FILE,
                    to_key="path",
                    to_value=relative_path_str,
                )
            )

    def _create_file_metadata_node(
        self,
        relative_path_str: str,
        file_hash: str,
        mtime: int,
        nodes: list[NodeData],
    ) -> None:
        """Create FileMetadata node for tracking file state."""
        current_time = int(time.time())
        nodes.append(
            NodeData(
                label=NodeLabel.FILE_METADATA,
                properties={
                    "filepath": relative_path_str,
                    "mtime": mtime,
                    "hash": file_hash,
                    "last_updated": current_time,
                },
            )
        )

    def _create_module_node(
        self,
        task: FileParseTask,
        relative_path_str: str,
        nodes: list[NodeData],
        relationships: list[RelationshipData],
    ) -> None:
        """Create Module node and containment relationship."""
        current_time = int(time.time())
        nodes.append(
            NodeData(
                label=NodeLabel.MODULE,
                properties={
                    "qualified_name": task.module_qn,
                    "name": task.file_path.stem,
                    "path": relative_path_str,
                    "created_at": current_time,
                    "updated_at": current_time,
                },
            )
        )

        if task.container_qn:
            relationships.append(
                RelationshipData(
                    from_label=NodeLabel.PACKAGE,
                    from_key="qualified_name",
                    from_value=task.container_qn,
                    rel_type=RelationshipType.CONTAINS_MODULE,
                    to_label=NodeLabel.MODULE,
                    to_key="qualified_name",
                    to_value=task.module_qn,
                )
            )

        # Add TRACKS_Module relationship from FileMetadata to Module
        relationships.append(
            RelationshipData(
                from_label=NodeLabel.FILE_METADATA,
                from_key="filepath",
                from_value=relative_path_str,
                rel_type=RelationshipType.TRACKS_MODULE,
                to_label=NodeLabel.MODULE,
                to_key="qualified_name",
                to_value=task.module_qn,
            )
        )

    def _extract_definitions(
        self,
        root_node: Node,
        module_qn: str,
        language: str,
        relative_path_str: str,
        extractor: LanguageExtractor,
        nodes: list[NodeData],
        relationships: list[RelationshipData],
        function_registry: dict[str, str],
        simple_name_lookup: dict[str, list[str]],
        inheritance_data: list[InheritanceData],
    ) -> None:
        """Extract class and function definitions from AST."""
        lang_queries = self.queries.get(language, {})

        if "class_query" in lang_queries:
            self._extract_classes(
                root_node,
                module_qn,
                relative_path_str,
                extractor,
                lang_queries["class_query"],
                nodes,
                relationships,
                function_registry,
                simple_name_lookup,
                inheritance_data,
            )

        if "function_query" in lang_queries:
            self._extract_functions(
                root_node,
                module_qn,
                relative_path_str,
                extractor,
                lang_queries["function_query"],
                nodes,
                relationships,
                function_registry,
                simple_name_lookup,
            )

    def _extract_classes(
        self,
        root_node: Node,
        module_qn: str,
        relative_path_str: str,
        extractor: LanguageExtractor,
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
            class_node, class_name = self._get_class_from_match(match)
            if not class_node or not class_name:
                continue

            class_qn = f"{module_qn}.{class_name}"
            current_time = int(time.time())

            nodes.append(
                NodeData(
                    label=NodeLabel.CLASS,
                    properties={
                        "qualified_name": class_qn,
                        "name": class_name,
                        "decorators": extractor.extract_decorators(class_node),
                        "line_start": class_node.start_point.row + 1,
                        "line_end": class_node.end_point.row + 1,
                        "created_at": current_time,
                        "updated_at": current_time,
                        "docstring": extractor.extract_docstring(class_node),
                    },
                )
            )

            relationships.extend(
                [
                    RelationshipData(
                        from_label=NodeLabel.MODULE,
                        from_key="qualified_name",
                        from_value=module_qn,
                        rel_type=RelationshipType.DEFINES,
                        to_label=NodeLabel.CLASS,
                        to_key="qualified_name",
                        to_value=class_qn,
                    ),
                    RelationshipData(
                        from_label=NodeLabel.FILE_METADATA,
                        from_key="filepath",
                        from_value=relative_path_str,
                        rel_type=RelationshipType.TRACKS_CLASS,
                        to_label=NodeLabel.CLASS,
                        to_key="qualified_name",
                        to_value=class_qn,
                    ),
                ]
            )

            function_registry[class_qn] = NodeLabel.CLASS
            simple_name_lookup.setdefault(class_name, []).append(class_qn)

            parent_names = extractor.extract_inheritance(class_node)
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
        relative_path_str: str,
        extractor: LanguageExtractor,
        function_query: Query,
        nodes: list[NodeData],
        relationships: list[RelationshipData],
        function_registry: dict[str, str],
        simple_name_lookup: dict[str, list[str]],
    ) -> None:
        """Extract function and method definitions."""
        cursor = QueryCursor(function_query)

        for match in cursor.matches(root_node):
            func_node, func_name = self._get_function_from_match(match)
            if not func_node or not func_name:
                continue

            parent_class = extractor.find_parent_class(func_node, module_qn)
            current_time = int(time.time())

            if parent_class:
                self._add_method(
                    func_node,
                    func_name,
                    parent_class,
                    extractor,
                    relative_path_str,
                    current_time,
                    nodes,
                    relationships,
                    function_registry,
                    simple_name_lookup,
                )
            else:
                self._add_function(
                    func_node,
                    func_name,
                    module_qn,
                    extractor,
                    relative_path_str,
                    current_time,
                    nodes,
                    relationships,
                    function_registry,
                    simple_name_lookup,
                )

    def _add_method(
        self,
        func_node: Node,
        func_name: str,
        parent_class: str,
        extractor: LanguageExtractor,
        relative_path_str: str,
        current_time: int,
        nodes: list[NodeData],
        relationships: list[RelationshipData],
        function_registry: dict[str, str],
        simple_name_lookup: dict[str, list[str]],
    ) -> None:
        """Add a method node and relationships."""
        method_qn = f"{parent_class}.{func_name}"

        nodes.append(
            NodeData(
                label=NodeLabel.METHOD,
                properties={
                    "qualified_name": method_qn,
                    "name": func_name,
                    "decorators": extractor.extract_decorators(func_node),
                    "line_start": func_node.start_point.row + 1,
                    "line_end": func_node.end_point.row + 1,
                    "created_at": current_time,
                    "updated_at": current_time,
                    "docstring": extractor.extract_docstring(func_node),
                },
            )
        )

        relationships.extend(
            [
                RelationshipData(
                    from_label=NodeLabel.CLASS,
                    from_key="qualified_name",
                    from_value=parent_class,
                    rel_type=RelationshipType.DEFINES_METHOD,
                    to_label=NodeLabel.METHOD,
                    to_key="qualified_name",
                    to_value=method_qn,
                ),
                RelationshipData(
                    from_label=NodeLabel.FILE_METADATA,
                    from_key="filepath",
                    from_value=relative_path_str,
                    rel_type=RelationshipType.TRACKS_METHOD,
                    to_label=NodeLabel.METHOD,
                    to_key="qualified_name",
                    to_value=method_qn,
                ),
            ]
        )

        function_registry[method_qn] = NodeLabel.METHOD
        simple_name_lookup.setdefault(func_name, []).append(method_qn)

    def _add_function(
        self,
        func_node: Node,
        func_name: str,
        module_qn: str,
        extractor: LanguageExtractor,
        relative_path_str: str,
        current_time: int,
        nodes: list[NodeData],
        relationships: list[RelationshipData],
        function_registry: dict[str, str],
        simple_name_lookup: dict[str, list[str]],
    ) -> None:
        """Add a function node and relationships."""
        func_qn = f"{module_qn}.{func_name}"

        nodes.append(
            NodeData(
                label=NodeLabel.FUNCTION,
                properties={
                    "qualified_name": func_qn,
                    "name": func_name,
                    "decorators": extractor.extract_decorators(func_node),
                    "line_start": func_node.start_point.row + 1,
                    "line_end": func_node.end_point.row + 1,
                    "created_at": current_time,
                    "updated_at": current_time,
                    "docstring": extractor.extract_docstring(func_node),
                },
            )
        )

        relationships.extend(
            [
                RelationshipData(
                    from_label=NodeLabel.MODULE,
                    from_key="qualified_name",
                    from_value=module_qn,
                    rel_type=RelationshipType.DEFINES_FUNC,
                    to_label=NodeLabel.FUNCTION,
                    to_key="qualified_name",
                    to_value=func_qn,
                ),
                RelationshipData(
                    from_label=NodeLabel.FILE_METADATA,
                    from_key="filepath",
                    from_value=relative_path_str,
                    rel_type=RelationshipType.TRACKS_FUNCTION,
                    to_label=NodeLabel.FUNCTION,
                    to_key="qualified_name",
                    to_value=func_qn,
                ),
            ]
        )

        function_registry[func_qn] = NodeLabel.FUNCTION
        simple_name_lookup.setdefault(func_name, []).append(func_qn)

    def _extract_calls(
        self,
        root_node: Node,
        module_qn: str,
        language: str,
        extractor: LanguageExtractor,
        function_registry: dict[str, str],
        raw_calls: list[RawCallData],
    ) -> None:
        """Extract raw call data for later resolution."""
        lang_queries = self.queries.get(language, {})
        if "call_query" not in lang_queries:
            return

        cursor = QueryCursor(lang_queries["call_query"])

        for match in cursor.matches(root_node):
            call_node = self._get_call_from_match(match)
            if call_node:
                self._extract_single_call(
                    call_node, module_qn, extractor, function_registry, raw_calls
                )

    def _extract_single_call(
        self,
        call_node: Node,
        module_qn: str,
        extractor: LanguageExtractor,
        function_registry: dict[str, str],
        raw_calls: list[RawCallData],
    ) -> None:
        """Extract data from a single call expression."""
        callee_name, object_name = extractor.parse_call_node(call_node)
        if not callee_name:
            return

        caller_qn = extractor.find_containing_function(call_node, module_qn)
        if not caller_qn or caller_qn not in function_registry:
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

    def _get_class_from_match(
        self, match: tuple[int, dict[str, list[Node]]]
    ) -> tuple[Node | None, str | None]:
        """Extract class node and name from query match."""
        class_node = None
        class_name = None

        for capture_name, capture_nodes in match[1].items():
            for node in capture_nodes:
                if capture_name in ["class", "interface", "type_alias"]:
                    class_node = node
                elif capture_name == "class_name" and node.text:
                    class_name = node.text.decode("utf-8")

        return class_node, class_name

    def _get_function_from_match(
        self, match: tuple[int, dict[str, list[Node]]]
    ) -> tuple[Node | None, str | None]:
        """Extract function node and name from query match."""
        func_node = None
        func_name = None

        for capture_name, capture_nodes in match[1].items():
            for node in capture_nodes:
                if capture_name == "function":
                    func_node = node
                elif capture_name == "function_name" and node.text:
                    func_name = node.text.decode("utf-8")

        return func_node, func_name

    def _get_call_from_match(
        self, match: tuple[int, dict[str, list[Node]]]
    ) -> Node | None:
        """Extract call node from query match."""
        for capture_name, capture_nodes in match[1].items():
            for node in capture_nodes:
                if capture_name == "call":
                    return node
        return None

    def _empty_result(
        self,
        task: FileParseTask,
        nodes: list[NodeData],
        relationships: list[RelationshipData],
        function_registry: dict[str, str],
        simple_name_lookup: dict[str, list[str]],
        raw_calls: list[RawCallData],
        inheritance_data: list[InheritanceData],
        file_hash: str,
        mtime: int,
        file_size: int,
        start_time: float,
        relative_path_str: str,
    ) -> FileParseResult:
        """Create result for empty file."""
        return FileParseResult(
            task=task,
            success=True,
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

    def _error_result(
        self,
        task: FileParseTask,
        error: str,
        file_hash: str,
        mtime: int,
        file_size: int,
        start_time: float,
        relative_path_str: str,
    ) -> FileParseResult:
        """Create result for error case."""
        return FileParseResult(
            task=task,
            success=False,
            error=error,
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

    def _success_result(
        self,
        task: FileParseTask,
        nodes: list[NodeData],
        relationships: list[RelationshipData],
        function_registry: dict[str, str],
        simple_name_lookup: dict[str, list[str]],
        raw_calls: list[RawCallData],
        inheritance_data: list[InheritanceData],
        file_hash: str,
        mtime: int,
        file_size: int,
        ast_nodes_count: int,
        start_time: float,
        relative_path_str: str,
    ) -> FileParseResult:
        """Create successful result."""
        definitions_count = sum(
            1
            for n in nodes
            if n.label in [NodeLabel.CLASS, NodeLabel.FUNCTION, NodeLabel.METHOD]
        )

        return FileParseResult(
            task=task,
            success=True,
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
                ast_nodes=ast_nodes_count,
                definitions_extracted=definitions_count,
                relationships_found=len(relationships) + len(raw_calls),
                worker_id=self.worker_id,
            ),
        )


def process_batch(batch: WorkBatch, worker_id: int = 0) -> list[FileParseResult]:
    """Entry point for worker processes."""
    worker = ParserWorker(worker_id=worker_id)
    return worker.process_batch(batch)
