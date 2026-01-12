"""Kuzu graph ingestor for building code knowledge graphs."""

from __future__ import annotations

import asyncio
import hashlib
import multiprocessing
import os
import time
import uuid
from collections import defaultdict
from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

import aiofiles
from tree_sitter import Node, Parser, QueryCursor

from shotgun.codebase.core.call_resolution import calculate_callee_confidence
from shotgun.codebase.core.gitignore import GitignoreManager
from shotgun.codebase.core.kuzu_compat import get_kuzu
from shotgun.codebase.core.metrics_collector import MetricsCollector
from shotgun.codebase.core.metrics_types import (
    FileInfo,
    IndexingPhase,
    ParallelExecutionResult,
)
from shotgun.codebase.core.parallel_executor import ParallelExecutor
from shotgun.codebase.core.work_distributor import WorkDistributor, get_worker_count
from shotgun.codebase.models import (
    IgnoreReason,
    IndexingStats,
    IndexProgress,
    NodeLabel,
    ProgressPhase,
    RelationshipType,
)
from shotgun.posthog_telemetry import track_event
from shotgun.settings import settings

if TYPE_CHECKING:
    import real_ladybug as kuzu

from shotgun.codebase.core.language_config import (
    LANGUAGE_CONFIGS,
    get_all_ignore_directories,
    get_language_config,
    is_path_ignored,
    should_ignore_directory,
)
from shotgun.codebase.core.parser_loader import load_parsers
from shotgun.logging_config import get_logger

logger = get_logger(__name__)

# For backwards compatibility, expose IGNORE_PATTERNS from this module
IGNORE_PATTERNS = get_all_ignore_directories()

# Explicit re-exports for type checkers
__all__ = [
    "IGNORE_PATTERNS",
    "LANGUAGE_CONFIGS",
    "Ingestor",
    "SimpleGraphBuilder",
    "get_all_ignore_directories",
    "get_language_config",
    "is_path_ignored",
    "should_ignore_directory",
]


class Ingestor:
    """Handles all communication and ingestion with the Kuzu database."""

    def __init__(self, connection: kuzu.Connection):
        self.conn = connection
        self.node_buffer: list[tuple[str, dict[str, Any]]] = []
        self.relationship_buffer: list[
            tuple[str, str, Any, str, str, str, Any, dict[str, Any] | None]
        ] = []
        self.batch_size = 1000
        # Track seen primary keys to avoid O(n²) duplicate checking
        self._seen_node_keys: set[tuple[str, str]] = set()

    def create_schema(self) -> None:
        """Create the graph schema in Kuzu."""
        logger.info("Creating Kuzu schema...")

        # Node tables
        node_schemas = [
            "CREATE NODE TABLE Project(name STRING PRIMARY KEY, repo_path STRING, graph_id STRING, created_at INT64, updated_at INT64, schema_version STRING, build_options STRING, node_count INT64, relationship_count INT64, stats_updated_at INT64, status STRING, current_operation_id STRING, last_operation STRING, indexed_from_cwds STRING)",
            "CREATE NODE TABLE Package(qualified_name STRING PRIMARY KEY, name STRING, path STRING)",
            "CREATE NODE TABLE Folder(path STRING PRIMARY KEY, name STRING)",
            "CREATE NODE TABLE File(path STRING PRIMARY KEY, name STRING, extension STRING)",
            "CREATE NODE TABLE Module(qualified_name STRING PRIMARY KEY, name STRING, path STRING, created_at INT64, updated_at INT64)",
            "CREATE NODE TABLE Class(qualified_name STRING PRIMARY KEY, name STRING, decorators STRING[], line_start INT64, line_end INT64, created_at INT64, updated_at INT64, docstring STRING)",
            "CREATE NODE TABLE Function(qualified_name STRING PRIMARY KEY, name STRING, decorators STRING[], line_start INT64, line_end INT64, created_at INT64, updated_at INT64, docstring STRING)",
            "CREATE NODE TABLE Method(qualified_name STRING PRIMARY KEY, name STRING, decorators STRING[], line_start INT64, line_end INT64, created_at INT64, updated_at INT64, docstring STRING)",
            "CREATE NODE TABLE ExternalPackage(name STRING PRIMARY KEY, version_spec STRING)",
            "CREATE NODE TABLE FileMetadata(filepath STRING PRIMARY KEY, mtime INT64, hash STRING, last_updated INT64)",
            "CREATE NODE TABLE DeletionLog(id STRING PRIMARY KEY, entity_type STRING, entity_qualified_name STRING, deleted_from_file STRING, deleted_at INT64, deletion_reason STRING)",
        ]

        # Relationship tables - need separate tables for each source/target combination
        rel_schemas = [
            # CONTAINS_PACKAGE relationships
            "CREATE REL TABLE CONTAINS_PACKAGE(FROM Project TO Package)",
            "CREATE REL TABLE CONTAINS_PACKAGE_PKG(FROM Package TO Package)",
            "CREATE REL TABLE CONTAINS_PACKAGE_FOLDER(FROM Folder TO Package)",
            # CONTAINS_FOLDER relationships
            "CREATE REL TABLE CONTAINS_FOLDER(FROM Project TO Folder)",
            "CREATE REL TABLE CONTAINS_FOLDER_PKG(FROM Package TO Folder)",
            "CREATE REL TABLE CONTAINS_FOLDER_FOLDER(FROM Folder TO Folder)",
            # CONTAINS_FILE relationships
            "CREATE REL TABLE CONTAINS_FILE(FROM Project TO File)",
            "CREATE REL TABLE CONTAINS_FILE_PKG(FROM Package TO File)",
            "CREATE REL TABLE CONTAINS_FILE_FOLDER(FROM Folder TO File)",
            # CONTAINS_MODULE relationships
            "CREATE REL TABLE CONTAINS_MODULE(FROM Project TO Module)",
            "CREATE REL TABLE CONTAINS_MODULE_PKG(FROM Package TO Module)",
            "CREATE REL TABLE CONTAINS_MODULE_FOLDER(FROM Folder TO Module)",
            # Other relationships
            "CREATE REL TABLE DEFINES(FROM Module TO Class)",
            "CREATE REL TABLE DEFINES_FUNC(FROM Module TO Function)",
            "CREATE REL TABLE DEFINES_METHOD(FROM Class TO Method)",
            "CREATE REL TABLE INHERITS(FROM Class TO Class)",
            "CREATE REL TABLE OVERRIDES(FROM Method TO Method)",
            "CREATE REL TABLE DEPENDS_ON_EXTERNAL(FROM Project TO ExternalPackage)",
            # CALLS relationships (all combinations)
            "CREATE REL TABLE CALLS(FROM Function TO Function)",
            "CREATE REL TABLE CALLS_FM(FROM Function TO Method)",
            "CREATE REL TABLE CALLS_MF(FROM Method TO Function)",
            "CREATE REL TABLE CALLS_MM(FROM Method TO Method)",
            # IMPORTS
            "CREATE REL TABLE IMPORTS(FROM Module TO Module)",
            # TRACKS relationships (FileMetadata to nodes)
            "CREATE REL TABLE TRACKS_Module(FROM FileMetadata TO Module)",
            "CREATE REL TABLE TRACKS_Class(FROM FileMetadata TO Class)",
            "CREATE REL TABLE TRACKS_Function(FROM FileMetadata TO Function)",
            "CREATE REL TABLE TRACKS_Method(FROM FileMetadata TO Method)",
        ]

        # Create all schemas
        for schema in node_schemas + rel_schemas:
            try:
                self.conn.execute(schema)
                logger.debug(f"Created: {schema.split('(')[0]}")
            except Exception as e:
                if "already exists" not in str(e):
                    logger.error(f"Failed to create schema: {schema}, error: {e}")

        logger.info("Schema creation complete.")

    def ensure_node_batch(self, label: str, properties: dict[str, Any]) -> None:
        """Add a node to the buffer for batch insertion."""
        # Check for duplicates based on primary key using O(1) set lookup
        primary_key = self._get_primary_key(label, properties)
        if primary_key:
            key = (label, primary_key)
            if key in self._seen_node_keys:
                return
            self._seen_node_keys.add(key)

        self.node_buffer.append((label, properties))

        if len(self.node_buffer) >= self.batch_size:
            self.flush_nodes()

    def _get_primary_key(self, label: str, properties: dict[str, Any]) -> str | None:
        """Get the primary key value for a node."""
        primary_key_field = self._get_primary_key_field(label)
        return properties.get(primary_key_field) if primary_key_field else None

    def _get_primary_key_field(self, label: str) -> str | None:
        """Get the primary key field name for a node type."""
        if label == NodeLabel.PROJECT:
            return "name"
        elif label in [
            NodeLabel.PACKAGE,
            NodeLabel.MODULE,
            NodeLabel.CLASS,
            NodeLabel.FUNCTION,
            NodeLabel.METHOD,
        ]:
            return "qualified_name"
        elif label in [NodeLabel.FOLDER, NodeLabel.FILE]:
            return "path"
        elif label == NodeLabel.FILE_METADATA:
            return "filepath"
        elif label == NodeLabel.EXTERNAL_PACKAGE:
            return "name"
        elif label == NodeLabel.DELETION_LOG:
            return "id"
        return None

    def flush_nodes(
        self,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> None:
        """Flush pending node insertions to the database.

        Args:
            progress_callback: Optional callback(current, total) for progress reporting
        """
        if not self.node_buffer:
            return

        total_nodes = len(self.node_buffer)
        processed = 0

        # Group nodes by label
        nodes_by_label: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for label, properties in self.node_buffer:
            nodes_by_label[label].append(properties)

        # Insert each group
        for label, nodes in nodes_by_label.items():
            try:
                # Build CREATE query for batch insertion
                for node_props in nodes:
                    # Create individual nodes
                    prop_names = list(node_props.keys())
                    prop_values = [node_props[k] for k in prop_names]

                    # Build query - use MERGE to handle duplicates
                    primary_key_field = self._get_primary_key_field(label)
                    if primary_key_field and primary_key_field in node_props:
                        # Use MERGE for nodes with primary keys
                        merge_props = f"{primary_key_field}: ${primary_key_field}"
                        set_props = ", ".join(
                            [
                                f"n.{k} = ${k}"
                                for k in prop_names
                                if k != primary_key_field
                            ]
                        )
                        query = f"MERGE (n:{label} {{{merge_props}}}) SET {set_props}"
                    else:
                        # Use CREATE for nodes without primary keys
                        props_str = ", ".join([f"{k}: ${k}" for k in prop_names])
                        query = f"CREATE (n:{label} {{{props_str}}})"

                    # Execute with parameters
                    params = dict(zip(prop_names, prop_values, strict=False))
                    self.conn.execute(query, params)

                    # Report progress
                    processed += 1
                    if progress_callback and processed % 10 == 0:
                        progress_callback(processed, total_nodes)

            except Exception as e:
                logger.error(f"Failed to insert {label} nodes: {e}")

        # Final progress report
        if progress_callback:
            progress_callback(total_nodes, total_nodes)

        # Log node counts by type
        node_type_counts: dict[str, int] = {}
        for label, _ in self.node_buffer:
            node_type_counts[label] = node_type_counts.get(label, 0) + 1

        logger.info(f"Flushed {len(self.node_buffer)} nodes:")
        for label, count in sorted(node_type_counts.items()):
            logger.info(f"  {label}: {count}")

        self.node_buffer.clear()
        self._seen_node_keys.clear()

    def ensure_relationship_batch(
        self,
        from_label: str,
        from_key: str,
        from_value: Any,
        rel_type: str,
        to_label: str,
        to_key: str,
        to_value: Any,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Add a relationship to the buffer for batch insertion."""
        self.relationship_buffer.append(
            (
                from_label,
                from_key,
                from_value,
                rel_type,
                to_label,
                to_key,
                to_value,
                properties,
            )
        )

        # Don't auto-flush relationships - wait for explicit flush_all() to ensure nodes exist first

    def flush_relationships(
        self,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> None:
        """Flush pending relationship insertions to the database.

        Args:
            progress_callback: Optional callback(current, total) for progress reporting
        """
        if not self.relationship_buffer:
            return

        total_rels = len(self.relationship_buffer)
        processed = 0

        # Group relationships by type
        rels_by_type: dict[
            str, list[tuple[str, str, Any, str, str, str, Any, dict[str, Any] | None]]
        ] = defaultdict(list)

        for rel_data in self.relationship_buffer:
            (
                from_label,
                from_key,
                from_value,
                rel_type,
                to_label,
                to_key,
                to_value,
                _properties,
            ) = rel_data

            # Determine actual table name
            table_name = self._get_relationship_table_name(
                rel_type, from_label, to_label
            )
            if table_name:
                rels_by_type[table_name].append(rel_data)

        # Insert each group
        relationship_counts = {}
        for table_name, relationships in rels_by_type.items():
            success_count = 0
            try:
                for rel_data in relationships:
                    (
                        from_label,
                        from_key,
                        from_value,
                        _,
                        to_label,
                        to_key,
                        to_value,
                        _properties,
                    ) = rel_data

                    # Build MATCH and MERGE query (use MERGE to avoid duplicate relationships)
                    query = f"""
                    MATCH (a:{from_label} {{{from_key}: $from_val}}),
                          (b:{to_label} {{{to_key}: $to_val}})
                    MERGE (a)-[:{table_name}]->(b)
                    """

                    params = {"from_val": from_value, "to_val": to_value}
                    try:
                        self.conn.execute(query, params)
                        success_count += 1

                        # Report progress
                        processed += 1
                        if progress_callback and processed % 10 == 0:
                            progress_callback(processed, total_rels)
                    except Exception as e:
                        logger.error(
                            f"Failed to create single relationship {table_name}: {from_label}({from_value}) -> {to_label}({to_value})"
                        )
                        logger.error(f"Error: {e}")
                        raise

                relationship_counts[table_name] = success_count
                if table_name == "DEFINES_METHOD":
                    logger.info(
                        f"Successfully created {success_count} DEFINES_METHOD relationships"
                    )

            except Exception as e:
                logger.error(f"Failed to insert {table_name} relationships: {e}")
                logger.error(
                    f"Failed on relationship #{success_count + 1} of {len(relationships)}"
                )
                logger.error(f"Query was: {query}")
                logger.error(f"Params were: {params}")
                # Don't swallow the exception - let it propagate
                raise

        # Final progress report
        if progress_callback:
            progress_callback(total_rels, total_rels)

        # Log summary of flushed relationships
        logger.info(
            f"Flushed {len(self.relationship_buffer)} relationships: {relationship_counts}"
        )
        self.relationship_buffer.clear()

    def _get_relationship_table_name(
        self, rel_type: str, from_label: str, to_label: str
    ) -> str | None:
        """Determine the actual relationship table name based on source and target."""
        # Mapping of relationship types and from_labels to table names
        # Keys use enum values for type-safe comparisons
        table_mapping: dict[str, dict[str, str]] = {
            RelationshipType.CONTAINS_PACKAGE: {
                NodeLabel.PROJECT: "CONTAINS_PACKAGE",
                NodeLabel.PACKAGE: "CONTAINS_PACKAGE_PKG",
                NodeLabel.FOLDER: "CONTAINS_PACKAGE_FOLDER",
            },
            RelationshipType.CONTAINS_FOLDER: {
                NodeLabel.PROJECT: "CONTAINS_FOLDER",
                NodeLabel.PACKAGE: "CONTAINS_FOLDER_PKG",
                NodeLabel.FOLDER: "CONTAINS_FOLDER_FOLDER",
            },
            RelationshipType.CONTAINS_FILE: {
                NodeLabel.PROJECT: "CONTAINS_FILE",
                NodeLabel.PACKAGE: "CONTAINS_FILE_PKG",
                NodeLabel.FOLDER: "CONTAINS_FILE_FOLDER",
            },
            RelationshipType.CONTAINS_MODULE: {
                NodeLabel.PROJECT: "CONTAINS_MODULE",
                NodeLabel.PACKAGE: "CONTAINS_MODULE_PKG",
                NodeLabel.FOLDER: "CONTAINS_MODULE_FOLDER",
            },
        }

        if rel_type in table_mapping:
            return table_mapping[rel_type].get(from_label)
        elif rel_type == RelationshipType.DEFINES:
            if to_label == NodeLabel.FUNCTION:
                return RelationshipType.DEFINES_FUNC
            else:
                return RelationshipType.DEFINES
        elif rel_type == RelationshipType.CALLS:
            if from_label == NodeLabel.FUNCTION and to_label == NodeLabel.FUNCTION:
                return RelationshipType.CALLS
            elif from_label == NodeLabel.FUNCTION and to_label == NodeLabel.METHOD:
                return RelationshipType.CALLS_FM
            elif from_label == NodeLabel.METHOD and to_label == NodeLabel.FUNCTION:
                return RelationshipType.CALLS_MF
            elif from_label == NodeLabel.METHOD and to_label == NodeLabel.METHOD:
                return RelationshipType.CALLS_MM
        elif rel_type.startswith("TRACKS_"):
            # TRACKS relationships already have the correct table name
            return rel_type
        else:
            # Default to the relationship type
            return rel_type
        return None

    def flush_all(self) -> None:
        """Flush all pending operations."""
        logger.info(
            f"Starting flush_all: {len(self.node_buffer)} nodes, {len(self.relationship_buffer)} relationships buffered"
        )

        # IMPORTANT: Flush nodes first to ensure they exist before creating relationships
        self.flush_nodes()

        # Now flush relationships - all nodes should exist
        self.flush_relationships()

        logger.info("flush_all completed successfully")

    def ensure_file_metadata(
        self, filepath: str, mtime: int, hash_value: str, last_updated: int
    ) -> None:
        """Create or update FileMetadata node."""
        self.ensure_node_batch(
            "FileMetadata",
            {
                "filepath": filepath,
                "mtime": mtime,
                "hash": hash_value,
                "last_updated": last_updated,
            },
        )

    def log_deletion(
        self,
        entity_type: str,
        entity_qn: str,
        filepath: str,
        reason: str = "file_modified",
    ) -> None:
        """Log a deletion to the DeletionLog table."""
        deletion_id = str(uuid.uuid4())
        current_time = int(time.time())

        try:
            self.conn.execute(
                """
                CREATE (d:DeletionLog {
                    id: $id,
                    entity_type: $type,
                    entity_qualified_name: $qn,
                    deleted_from_file: $file,
                    deleted_at: $time,
                    deletion_reason: $reason
                })
            """,
                {
                    "id": deletion_id,
                    "type": entity_type,
                    "qn": entity_qn,
                    "file": filepath,
                    "time": current_time,
                    "reason": reason,
                },
            )
        except Exception as e:
            logger.error(f"Failed to log deletion of {entity_qn}: {e}")

    def ensure_tracks_relationship(
        self, filepath: str, node_type: str, node_qn: str
    ) -> None:
        """Create TRACKS relationship between FileMetadata and a node."""
        rel_type = f"TRACKS_{node_type}"
        self.ensure_relationship_batch(
            "FileMetadata",
            "filepath",
            filepath,
            rel_type,
            node_type,
            "qualified_name",
            node_qn,
        )

    def delete_file_nodes(self, filepath: str) -> dict[str, int]:
        """Delete all nodes tracked by a FileMetadata.

        Args:
            filepath: Relative file path

        Returns:
            Statistics of deleted entities
        """
        stats = {"modules": 0, "classes": 0, "functions": 0, "methods": 0}

        # Delete each type of node tracked by this file
        for node_type, rel_type, stat_key in [
            (NodeLabel.MODULE, RelationshipType.TRACKS_MODULE, "modules"),
            (NodeLabel.CLASS, RelationshipType.TRACKS_CLASS, "classes"),
            (NodeLabel.FUNCTION, RelationshipType.TRACKS_FUNCTION, "functions"),
            (NodeLabel.METHOD, RelationshipType.TRACKS_METHOD, "methods"),
        ]:
            try:
                # First get the nodes to delete (for logging)
                result = self.conn.execute(
                    f"""
                    MATCH (f:FileMetadata {{filepath: $path}})-[:{rel_type}]->(n:{node_type})
                    RETURN n.qualified_name
                """,
                    {"path": filepath},
                )

                nodes_to_delete = []
                if hasattr(result, "has_next") and not isinstance(result, list):
                    while result.has_next():
                        row = result.get_next()
                        if isinstance(row, list | tuple) and len(row) > 0:
                            nodes_to_delete.append(row[0])

                # Log deletions
                for node_qn in nodes_to_delete:
                    self.log_deletion(node_type, node_qn, filepath, "file_modified")

                # Delete the nodes and their relationships
                self.conn.execute(
                    f"""
                    MATCH (f:FileMetadata {{filepath: $path}})-[:{rel_type}]->(n:{node_type})
                    DETACH DELETE n
                """,
                    {"path": filepath},
                )

                stats[stat_key] = len(nodes_to_delete)

            except Exception as e:
                logger.error(f"Failed to delete {node_type} nodes for {filepath}: {e}")

        # Delete the FileMetadata node itself
        try:
            self.conn.execute(
                """
                MATCH (f:FileMetadata {filepath: $path})
                DETACH DELETE f
            """,
                {"path": filepath},
            )
        except Exception as e:
            logger.error(f"Failed to delete FileMetadata for {filepath}: {e}")

        return stats


class SimpleGraphBuilder:
    """Simplified version of GraphUpdater for building the code graph."""

    def __init__(
        self,
        ingestor: Ingestor,
        repo_path: Path,
        parsers: dict[str, Parser],
        queries: dict[str, Any],
        exclude_patterns: list[str] | None = None,
        progress_callback: Any | None = None,
        respect_gitignore: bool = True,
        metrics_collector: MetricsCollector | None = None,
        enable_parallel: bool = True,
    ):
        self.ingestor = ingestor
        self.repo_path = repo_path
        self.parsers = parsers
        self.queries = queries
        self.project_name = repo_path.name
        self.ignore_dirs = IGNORE_PATTERNS
        if exclude_patterns:
            self.ignore_dirs = self.ignore_dirs.union(set(exclude_patterns))
        self.progress_callback = progress_callback
        self.metrics_collector = metrics_collector

        # Initialize gitignore support
        self.respect_gitignore = respect_gitignore
        self.gitignore_manager: GitignoreManager | None = None
        if respect_gitignore:
            self.gitignore_manager = GitignoreManager(repo_path)
            if self.gitignore_manager.stats.patterns_loaded > 0:
                logger.info(
                    f"Loaded gitignore patterns - "
                    f"files: {self.gitignore_manager.stats.gitignore_files_loaded}, "
                    f"patterns: {self.gitignore_manager.stats.patterns_loaded}"
                )

        # Generate unique session ID for correlating timing events in PostHog
        self._index_session_id = str(uuid.uuid4())[:8]

        # Statistics for tracking what was indexed vs skipped
        self._index_stats = IndexingStats()

        # Caches
        self.structural_elements: dict[Path, str | None] = {}
        self.ast_cache: dict[Path, tuple[Node, str]] = {}
        self.function_registry: dict[str, str] = {}  # qualified_name -> type
        self.simple_name_lookup: dict[str, set[str]] = defaultdict(set)
        self.class_inheritance: dict[str, list[str]] = {}  # class_qn -> [parent_qns]

        # Parallel execution support
        self.enable_parallel = enable_parallel
        self.parallel_executor: ParallelExecutor | None = None
        self._parallel_mode_active = False  # Track if parallel was used for this run
        self._worker_count = 0
        self._init_parallel_executor()

    def _init_parallel_executor(self) -> None:
        """Initialize parallel executor if conditions are met.

        Conditions for parallel execution:
        1. enable_parallel=True (constructor parameter)
        2. settings.indexing.index_parallel is True
        3. CPU count >= 4
        """
        # Check settings override
        if not settings.indexing.index_parallel:
            logger.info("Parallel indexing disabled via SHOTGUN_INDEX_PARALLEL=false")
            return

        if not self.enable_parallel:
            logger.debug("Parallel indexing disabled via enable_parallel=False")
            return

        cpu_count = multiprocessing.cpu_count()
        if cpu_count < 4:
            logger.info(f"Parallel indexing disabled: CPU count ({cpu_count}) < 4")
            return

        worker_count = get_worker_count()
        self.parallel_executor = ParallelExecutor(
            worker_count=worker_count,
            metrics_collector=self.metrics_collector,
        )
        self._worker_count = worker_count
        logger.info(f"Parallel indexing enabled with {worker_count} workers")

    def _build_file_infos(
        self, files_to_process: list[tuple[Path, str]]
    ) -> list[FileInfo]:
        """Convert files_to_process list to FileInfo objects for parallel execution.

        Args:
            files_to_process: List of (filepath, language) tuples

        Returns:
            List of FileInfo objects ready for WorkDistributor
        """
        file_infos: list[FileInfo] = []

        for filepath, language in files_to_process:
            relative_path = filepath.relative_to(self.repo_path)

            # Compute module_qn (same logic as _process_single_file)
            if filepath.name == "__init__.py":
                module_qn = ".".join(
                    [self.project_name] + list(relative_path.parent.parts)
                )
            else:
                module_qn = ".".join(
                    [self.project_name] + list(relative_path.with_suffix("").parts)
                )

            # Get container qualified name from structural elements
            parent_rel_path = relative_path.parent
            container_qn = self.structural_elements.get(parent_rel_path)

            try:
                file_size = filepath.stat().st_size
            except OSError:
                file_size = 0

            file_infos.append(
                FileInfo(
                    file_path=filepath,
                    relative_path=relative_path,
                    language=language,
                    module_qn=module_qn,
                    container_qn=container_qn,
                    file_size_bytes=file_size,
                )
            )

        return file_infos

    def _merge_parallel_results(self, result: ParallelExecutionResult) -> None:
        """Merge parallel execution results into Ingestor buffers and local caches.

        Args:
            result: ParallelExecutionResult containing all parsed file data
        """
        # Merge nodes and direct relationships from each file
        for file_result in result.results:
            if not file_result.success:
                logger.warning(
                    f"File {file_result.task.file_path} failed: {file_result.error}"
                )
                continue

            # Add nodes to buffer
            for node in file_result.nodes:
                self.ingestor.ensure_node_batch(node.label, node.properties)

            # Add direct relationships to buffer
            for rel in file_result.relationships:
                self.ingestor.ensure_relationship_batch(
                    rel.from_label,
                    rel.from_key,
                    rel.from_value,
                    rel.rel_type,
                    rel.to_label,
                    rel.to_key,
                    rel.to_value,
                    rel.properties,
                )

        # Add resolved relationships (calls, inheritance) from aggregation
        for rel in result.resolved_relationships:
            self.ingestor.ensure_relationship_batch(
                rel.from_label,
                rel.from_key,
                rel.from_value,
                rel.rel_type,
                rel.to_label,
                rel.to_key,
                rel.to_value,
                rel.properties,
            )

        # Merge registries into local caches
        self.function_registry.update(result.function_registry)
        for name, qns in result.simple_name_lookup.items():
            for qn in qns:
                self.simple_name_lookup[name].add(qn)

        # Merge inheritance data for potential future use
        for file_result in result.results:
            if file_result.success:
                for inh in file_result.inheritance_data:
                    self.class_inheritance[inh.child_class_qn] = inh.parent_simple_names

        logger.info(
            f"Merged parallel results: {result.successful_files} files, "
            f"{len(result.function_registry)} registry entries, "
            f"{len(result.resolved_relationships)} resolved relationships"
        )

    def _report_progress(
        self,
        phase: str,
        phase_name: str,
        current: int,
        total: int | None = None,
        phase_complete: bool = False,
    ) -> None:
        """Report progress via callback if available."""
        if not self.progress_callback:
            return

        try:
            progress = IndexProgress(
                phase=ProgressPhase(phase),
                phase_name=phase_name,
                current=current,
                total=total,
                phase_complete=phase_complete,
            )
            self.progress_callback(progress)
        except Exception as e:
            # Don't let progress callback errors crash the build
            logger.debug(f"Progress callback error: {e}")

    def _log_timing(
        self,
        phase: str,
        duration: float,
        items: int,
        extra_props: dict[str, Any] | None = None,
    ) -> None:
        """Log timing data to PostHog for analysis."""
        properties: dict[str, Any] = {
            "session_id": self._index_session_id,
            "phase": phase,
            "duration_seconds": round(duration, 3),
            "item_count": items,
        }
        if extra_props:
            properties.update(extra_props)

        track_event("codebase_index_phase_completed", properties)

    def _log_summary(
        self,
        total_duration: float,
        total_files: int,
        total_nodes: int,
        total_relationships: int,
    ) -> None:
        """Log indexing summary event to PostHog."""
        track_event(
            "codebase_index_completed",
            {
                "session_id": self._index_session_id,
                "total_duration_seconds": round(total_duration, 3),
                "total_files": total_files,
                "total_nodes": total_nodes,
                "total_relationships": total_relationships,
            },
        )

    @contextmanager
    def _track_phase(
        self, phase: IndexingPhase, get_items_count: Callable[[], int]
    ) -> Generator[None, None, None]:
        """Context manager for tracking phase metrics.

        Args:
            phase: The indexing phase to track
            get_items_count: Callable that returns the items processed count
        """
        if self.metrics_collector:
            self.metrics_collector.start_phase(phase)
        try:
            yield
        finally:
            if self.metrics_collector:
                self.metrics_collector.end_phase(phase, get_items_count())

    async def run(self) -> None:
        """Run the three-pass graph building process."""
        logger.info(f"Building graph for project: {self.project_name}")

        # Pass 1: Structure
        logger.info("Pass 1: Identifying packages and folders...")
        t0 = time.time()
        with self._track_phase(
            IndexingPhase.STRUCTURE, lambda: self._index_stats.dirs_scanned
        ):
            self._identify_structure()
        t1 = time.time()
        self._log_timing(
            IndexingPhase.STRUCTURE, t1 - t0, len(self.structural_elements)
        )

        # Pass 2: Definitions
        logger.info("Pass 2: Processing files and extracting definitions...")
        t2 = time.time()
        with self._track_phase(
            IndexingPhase.DEFINITIONS, lambda: self._index_stats.files_processed
        ):
            await self._process_files()
        t3 = time.time()
        self._log_timing(
            IndexingPhase.DEFINITIONS,
            t3 - t2,
            len(self.ast_cache),
            {"file_count": len(self.ast_cache)},
        )

        # Pass 3: Relationships
        logger.info("Pass 3: Processing relationships (calls, imports)...")
        t4 = time.time()
        with self._track_phase(
            IndexingPhase.RELATIONSHIPS, lambda: self._index_stats.files_processed
        ):
            self._process_relationships()
        t5 = time.time()
        self._log_timing(IndexingPhase.RELATIONSHIPS, t5 - t4, len(self.ast_cache))

        # Flush all pending operations
        logger.info("Flushing all data to database...")
        node_count = len(self.ingestor.node_buffer)

        # Create progress callback for flush_nodes
        def node_progress(current: int, total: int) -> None:
            self._report_progress(
                IndexingPhase.FLUSH_NODES, "Flushing nodes to database", current, total
            )

        t6 = time.time()
        with self._track_phase(IndexingPhase.FLUSH_NODES, lambda: node_count):
            self.ingestor.flush_nodes(progress_callback=node_progress)
        t7 = time.time()
        self._report_progress(
            IndexingPhase.FLUSH_NODES,
            "Flushing nodes to database",
            node_count,
            node_count,
            True,
        )
        self._log_timing(
            IndexingPhase.FLUSH_NODES, t7 - t6, node_count, {"node_count": node_count}
        )

        rel_count = len(self.ingestor.relationship_buffer)

        # Create progress callback for flush_relationships
        def rel_progress(current: int, total: int) -> None:
            self._report_progress(
                IndexingPhase.FLUSH_RELATIONSHIPS,
                "Flushing relationships to database",
                current,
                total,
            )

        t8_start = time.time()
        with self._track_phase(IndexingPhase.FLUSH_RELATIONSHIPS, lambda: rel_count):
            self.ingestor.flush_relationships(progress_callback=rel_progress)
        t8 = time.time()
        self._report_progress(
            IndexingPhase.FLUSH_RELATIONSHIPS,
            "Flushing relationships to database",
            rel_count,
            rel_count,
            True,
        )
        self._log_timing(
            IndexingPhase.FLUSH_RELATIONSHIPS,
            t8 - t8_start,
            rel_count,
            {"relationship_count": rel_count},
        )

        # Update metrics collector with totals
        if self.metrics_collector:
            self.metrics_collector.set_totals(node_count, rel_count)

        # Track summary event with totals (no PII - only numeric metadata)
        total_duration = t8 - t0
        self._log_summary(
            total_duration=total_duration,
            total_files=len(self.ast_cache),
            total_nodes=node_count,
            total_relationships=rel_count,
        )

        # Log final indexing statistics
        logger.info("=== Indexing Statistics ===")
        logger.info(f"  Directories scanned: {self._index_stats.dirs_scanned}")
        logger.info(
            f"  Directories ignored (hardcoded patterns): {self._index_stats.dirs_ignored_hardcoded}"
        )
        logger.info(
            f"  Directories ignored (gitignore): {self._index_stats.dirs_ignored_gitignore}"
        )
        logger.info(f"  Files scanned: {self._index_stats.files_scanned}")
        logger.info(
            f"  Files ignored (hardcoded patterns): {self._index_stats.files_ignored_hardcoded}"
        )
        logger.info(
            f"  Files ignored (gitignore): {self._index_stats.files_ignored_gitignore}"
        )
        logger.info(
            f"  Files ignored (no parser): {self._index_stats.files_ignored_no_parser}"
        )
        logger.info(f"  Files processed: {self._index_stats.files_processed}")

        # Log gitignore manager stats if available
        if self.gitignore_manager:
            logger.info(f"  {self.gitignore_manager.get_stats_summary()}")

        logger.info("Graph building complete!")

    def _should_ignore_directory(
        self, dir_path: Path, dir_name: str
    ) -> tuple[bool, IgnoreReason | None]:
        """Check if a directory should be ignored.

        Args:
            dir_path: Full path to the directory
            dir_name: Name of the directory

        Returns:
            Tuple of (should_ignore, reason)
        """
        # Check hardcoded patterns first (fastest)
        if should_ignore_directory(dir_name, self.ignore_dirs):
            return True, IgnoreReason.HARDCODED

        # Check gitignore patterns
        if self.gitignore_manager:
            try:
                relative_path = dir_path.relative_to(self.repo_path)
                if self.gitignore_manager.is_directory_ignored(relative_path):
                    return True, IgnoreReason.GITIGNORE
            except ValueError:
                pass

        return False, None

    def _identify_structure(self) -> None:
        """First pass: Walk directory to find packages and folders."""
        dir_count = 0
        for root_str, dirs, _ in os.walk(self.repo_path, topdown=True):
            # Filter directories - modifying dirs in-place affects os.walk traversal
            filtered_dirs = []
            for d in dirs:
                dir_path = Path(root_str) / d
                should_ignore, reason = self._should_ignore_directory(dir_path, d)
                if should_ignore:
                    if reason == IgnoreReason.HARDCODED:
                        self._index_stats.dirs_ignored_hardcoded += 1
                    elif reason == IgnoreReason.GITIGNORE:
                        self._index_stats.dirs_ignored_gitignore += 1
                else:
                    filtered_dirs.append(d)
                    self._index_stats.dirs_scanned += 1

            dirs[:] = filtered_dirs
            root = Path(root_str)
            relative_root = root.relative_to(self.repo_path)

            # Skip root directory
            if root == self.repo_path:
                continue

            dir_count += 1
            # Report progress every 10 directories
            if dir_count % 10 == 0:
                self._report_progress(
                    "structure", "Identifying packages and folders", dir_count
                )

            parent_rel_path = relative_root.parent
            parent_container_qn = self.structural_elements.get(parent_rel_path)

            # Check if this is a package
            is_package = False
            package_indicators = set()

            # Collect package indicators from all languages
            for lang_name, lang_config in LANGUAGE_CONFIGS.items():
                if lang_name in self.queries:
                    package_indicators.update(lang_config.package_indicators)

            # Check for package indicators
            for indicator in package_indicators:
                if (root / indicator).exists():
                    is_package = True
                    break

            if is_package:
                # Create package
                package_qn = ".".join([self.project_name] + list(relative_root.parts))
                self.ingestor.ensure_node_batch(
                    NodeLabel.PACKAGE,
                    {
                        "qualified_name": package_qn,
                        "name": relative_root.name,
                        "path": str(relative_root).replace(os.sep, "/"),
                    },
                )

                # Create containment relationship
                if parent_container_qn:
                    # Parent is a package
                    self.ingestor.ensure_relationship_batch(
                        NodeLabel.PACKAGE,
                        "qualified_name",
                        parent_container_qn,
                        RelationshipType.CONTAINS_PACKAGE,
                        NodeLabel.PACKAGE,
                        "qualified_name",
                        package_qn,
                    )
                else:
                    # Parent is project root
                    self.ingestor.ensure_relationship_batch(
                        NodeLabel.PROJECT,
                        "name",
                        self.project_name,
                        RelationshipType.CONTAINS_PACKAGE,
                        NodeLabel.PACKAGE,
                        "qualified_name",
                        package_qn,
                    )

                self.structural_elements[relative_root] = package_qn
            else:
                # Create folder
                self.ingestor.ensure_node_batch(
                    NodeLabel.FOLDER,
                    {
                        "path": str(relative_root).replace(os.sep, "/"),
                        "name": relative_root.name,
                    },
                )

                # Create containment relationship
                if parent_container_qn:
                    # Parent is a package
                    self.ingestor.ensure_relationship_batch(
                        NodeLabel.PACKAGE,
                        "qualified_name",
                        parent_container_qn,
                        RelationshipType.CONTAINS_FOLDER,
                        NodeLabel.FOLDER,
                        "path",
                        str(relative_root).replace(os.sep, "/"),
                    )
                elif parent_rel_path == Path("."):
                    # Parent is project root
                    self.ingestor.ensure_relationship_batch(
                        NodeLabel.PROJECT,
                        "name",
                        self.project_name,
                        RelationshipType.CONTAINS_FOLDER,
                        NodeLabel.FOLDER,
                        "path",
                        str(relative_root).replace(os.sep, "/"),
                    )
                else:
                    # Parent is another folder
                    self.ingestor.ensure_relationship_batch(
                        NodeLabel.FOLDER,
                        "path",
                        str(parent_rel_path).replace(os.sep, "/"),
                        RelationshipType.CONTAINS_FOLDER,
                        NodeLabel.FOLDER,
                        "path",
                        str(relative_root).replace(os.sep, "/"),
                    )

                self.structural_elements[relative_root] = None

        # Report phase completion
        self._report_progress(
            "structure",
            "Identifying packages and folders",
            dir_count,
            phase_complete=True,
        )

    def _should_ignore_file(self, filepath: Path) -> tuple[bool, IgnoreReason | None]:
        """Check if a file should be ignored.

        Args:
            filepath: Full path to the file

        Returns:
            Tuple of (should_ignore, reason)
        """
        # Check hardcoded directory patterns in path
        if is_path_ignored(filepath, self.ignore_dirs):
            return True, IgnoreReason.HARDCODED

        # Check gitignore patterns
        if self.gitignore_manager:
            try:
                relative_path = filepath.relative_to(self.repo_path)
                if self.gitignore_manager.is_ignored(relative_path):
                    return True, IgnoreReason.GITIGNORE
            except ValueError:
                pass

        return False, None

    async def _process_files(self) -> None:
        """Second pass: Process files and extract definitions."""
        # First pass: Count total files (respecting all ignore patterns)
        total_files = 0
        files_to_process: list[tuple[Path, str]] = []

        for root_str, dirs, files in os.walk(self.repo_path, topdown=True):
            root = Path(root_str)

            # Filter directories in-place to prevent os.walk from descending
            filtered_dirs = []
            for d in dirs:
                dir_path = root / d
                should_ignore, _ = self._should_ignore_directory(dir_path, d)
                if not should_ignore:
                    filtered_dirs.append(d)
            dirs[:] = filtered_dirs

            for filename in files:
                filepath = root / filename
                self._index_stats.files_scanned += 1

                # Check if file should be ignored
                should_ignore, reason = self._should_ignore_file(filepath)
                if should_ignore:
                    if reason == IgnoreReason.HARDCODED:
                        self._index_stats.files_ignored_hardcoded += 1
                    elif reason == IgnoreReason.GITIGNORE:
                        self._index_stats.files_ignored_gitignore += 1
                    continue

                # Check if this is a supported file
                ext = filepath.suffix
                lang_config = get_language_config(ext)

                if lang_config and lang_config.name in self.parsers:
                    files_to_process.append((filepath, lang_config.name))
                    total_files += 1
                else:
                    self._index_stats.files_ignored_no_parser += 1

        # Log what we're about to process
        logger.info(
            f"Index statistics: "
            f"scanned {self._index_stats.files_scanned} files, "
            f"processing {total_files}, "
            f"skipped {self._index_stats.files_ignored_hardcoded} (hardcoded), "
            f"{self._index_stats.files_ignored_gitignore} (gitignore), "
            f"{self._index_stats.files_ignored_no_parser} (no parser)"
        )

        # Decide on parallel vs sequential execution
        # Use parallel if executor available and enough files to benefit
        if self.parallel_executor and total_files >= 10:
            await self._process_files_parallel(files_to_process, total_files)
        else:
            await self._process_files_sequential(files_to_process, total_files)

    async def _process_files_parallel(
        self, files_to_process: list[tuple[Path, str]], total_files: int
    ) -> None:
        """Process files using parallel execution.

        Args:
            files_to_process: List of (filepath, language) tuples
            total_files: Total number of files to process
        """
        logger.info(f"Using parallel execution with {self._worker_count} workers")
        self._parallel_mode_active = True

        try:
            # Build FileInfo objects for WorkDistributor
            file_infos = self._build_file_infos(files_to_process)

            # Create work batches using WorkDistributor
            distributor = WorkDistributor(worker_count=self._worker_count)
            batches = distributor.create_batches(file_infos)

            logger.info(f"Created {len(batches)} batches for {len(file_infos)} files")

            # Track progress for UI
            files_completed = 0

            def parallel_progress(completed_batches: int, total_batches: int) -> None:
                nonlocal files_completed
                # Estimate files completed based on batch progress
                if total_batches > 0:
                    estimated = int((completed_batches / total_batches) * total_files)
                    files_completed = estimated
                    self._report_progress(
                        "definitions",
                        f"Processing files (Parallel, {self._worker_count} workers)",
                        files_completed,
                        total_files,
                    )

            # Execute in parallel - run blocking executor in thread pool
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self.parallel_executor.execute(batches, parallel_progress),  # type: ignore[union-attr]
            )

            # Merge results into Ingestor buffers and local caches
            self._merge_parallel_results(result)

            # Update stats
            self._index_stats.files_processed = result.successful_files

            # Report phase completion
            self._report_progress(
                "definitions",
                f"Processing files (Parallel, {self._worker_count} workers)",
                result.successful_files,
                total_files,
                phase_complete=True,
            )

            logger.info(
                f"Parallel processing complete: {result.successful_files}/{total_files} "
                f"files, {result.failed_files} failures"
            )

        except Exception as e:
            logger.warning(
                f"Parallel execution failed: {e}. Falling back to sequential."
            )
            self._parallel_mode_active = False
            await self._process_files_sequential(files_to_process, total_files)

    async def _process_files_sequential(
        self, files_to_process: list[tuple[Path, str]], total_files: int
    ) -> None:
        """Process files using sequential execution (original behavior).

        Args:
            files_to_process: List of (filepath, language) tuples
            total_files: Total number of files to process
        """
        logger.info("Using sequential execution")
        self._parallel_mode_active = False

        file_count = 0
        for filepath, language in files_to_process:
            await self._process_single_file(filepath, language)
            file_count += 1
            self._index_stats.files_processed += 1

            # Report progress after each file
            self._report_progress(
                "definitions",
                "Processing files (Sequential)",
                file_count,
                total_files,
            )

            if file_count % 100 == 0:
                logger.info(f"  Processed {file_count}/{total_files} files...")

        logger.info(f"  Total files processed: {file_count}/{total_files}")

        # Report phase completion
        self._report_progress(
            "definitions",
            "Processing files (Sequential)",
            file_count,
            total_files,
            phase_complete=True,
        )

    async def _process_single_file(self, filepath: Path, language: str) -> None:
        """Process a single file."""
        relative_path = filepath.relative_to(self.repo_path)
        relative_path_str = str(relative_path).replace(os.sep, "/")

        # Create File node
        self.ingestor.ensure_node_batch(
            NodeLabel.FILE,
            {
                "path": relative_path_str,
                "name": filepath.name,
                "extension": filepath.suffix,
            },
        )

        # Create containment relationship
        parent_rel_path = relative_path.parent
        if parent_rel_path == Path("."):
            # File in project root
            self.ingestor.ensure_relationship_batch(
                NodeLabel.PROJECT,
                "name",
                self.project_name,
                RelationshipType.CONTAINS_FILE,
                NodeLabel.FILE,
                "path",
                relative_path_str,
            )
        else:
            self.ingestor.ensure_relationship_batch(
                NodeLabel.FOLDER,
                "path",
                str(parent_rel_path).replace(os.sep, "/"),
                RelationshipType.CONTAINS_FILE,
                NodeLabel.FILE,
                "path",
                relative_path_str,
            )

        # Parse file
        try:
            async with aiofiles.open(filepath, "rb") as f:
                content = await f.read()

            parser = self.parsers[language]
            tree = parser.parse(content)
            root_node = tree.root_node

            # Cache AST for later
            self.ast_cache[filepath] = (root_node, language)

            # Create module
            if filepath.name == "__init__.py":
                module_qn = ".".join(
                    [self.project_name] + list(relative_path.parent.parts)
                )
            else:
                module_qn = ".".join(
                    [self.project_name] + list(relative_path.with_suffix("").parts)
                )

            current_time = int(time.time())
            self.ingestor.ensure_node_batch(
                NodeLabel.MODULE,
                {
                    "qualified_name": module_qn,
                    "name": filepath.stem,
                    "path": relative_path_str,
                    "created_at": current_time,
                    "updated_at": current_time,
                },
            )

            # Create module containment
            parent_container = self.structural_elements.get(parent_rel_path)
            if parent_container:
                # Parent is a package
                self.ingestor.ensure_relationship_batch(
                    NodeLabel.PACKAGE,
                    "qualified_name",
                    parent_container,
                    RelationshipType.CONTAINS_MODULE,
                    NodeLabel.MODULE,
                    "qualified_name",
                    module_qn,
                )
            elif parent_rel_path == Path("."):
                # Parent is project root
                self.ingestor.ensure_relationship_batch(
                    NodeLabel.PROJECT,
                    "name",
                    self.project_name,
                    RelationshipType.CONTAINS_MODULE,
                    NodeLabel.MODULE,
                    "qualified_name",
                    module_qn,
                )
            else:
                # Parent is a folder
                self.ingestor.ensure_relationship_batch(
                    NodeLabel.FOLDER,
                    "path",
                    str(parent_rel_path).replace(os.sep, "/"),
                    RelationshipType.CONTAINS_MODULE,
                    NodeLabel.MODULE,
                    "qualified_name",
                    module_qn,
                )

            # Create file metadata
            mtime = int(filepath.stat().st_mtime)
            hash_value = hashlib.sha256(content).hexdigest()
            self.ingestor.ensure_file_metadata(
                relative_path_str, mtime, hash_value, current_time
            )

            # Track module
            self.ingestor.ensure_tracks_relationship(
                relative_path_str, NodeLabel.MODULE, module_qn
            )

            # Extract definitions
            self._extract_definitions(filepath, root_node, module_qn, language)

        except Exception as e:
            logger.error(f"Failed to process {filepath}: {e}")

    def _extract_definitions(
        self, filepath: Path, root_node: Node, module_qn: str, language: str
    ) -> None:
        """Extract function and class definitions from AST."""
        lang_queries = self.queries.get(language, {})
        relative_path_str = str(filepath.relative_to(self.repo_path)).replace(
            os.sep, "/"
        )

        # Extract classes
        if "class_query" in lang_queries:
            cursor = QueryCursor(lang_queries["class_query"])
            for match in cursor.matches(root_node):
                class_node = None
                class_name = None

                captures = match[1]  # Get captures dictionary from tuple
                for capture_name, nodes in captures.items():
                    for node in nodes:
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
                    self.ingestor.ensure_node_batch(
                        NodeLabel.CLASS,
                        {
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

                    # Create DEFINES relationship
                    self.ingestor.ensure_relationship_batch(
                        NodeLabel.MODULE,
                        "qualified_name",
                        module_qn,
                        RelationshipType.DEFINES,
                        NodeLabel.CLASS,
                        "qualified_name",
                        class_qn,
                    )

                    # Track class
                    self.ingestor.ensure_tracks_relationship(
                        relative_path_str, NodeLabel.CLASS, class_qn
                    )

                    # Register for lookup
                    self.function_registry[class_qn] = NodeLabel.CLASS
                    self.simple_name_lookup[class_name].add(class_qn)

                    # Extract inheritance
                    parent_names = self._extract_inheritance(class_node, language)
                    if parent_names:
                        self.class_inheritance[class_qn] = parent_names

        # Extract functions
        if "function_query" in lang_queries:
            cursor = QueryCursor(lang_queries["function_query"])
            matches = list(cursor.matches(root_node))
            for match in matches:
                func_node = None
                func_name = None

                captures = match[1]  # Get captures dictionary from tuple
                for capture_name, nodes in captures.items():
                    for node in nodes:
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

                        # Extract docstring
                        docstring = self._extract_docstring(func_node, language)

                        current_time = int(time.time())
                        self.ingestor.ensure_node_batch(
                            NodeLabel.METHOD,
                            {
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

                        # Create DEFINES_METHOD relationship
                        self.ingestor.ensure_relationship_batch(
                            NodeLabel.CLASS,
                            "qualified_name",
                            parent_class,
                            RelationshipType.DEFINES_METHOD,
                            NodeLabel.METHOD,
                            "qualified_name",
                            method_qn,
                        )

                        # Track method
                        self.ingestor.ensure_tracks_relationship(
                            relative_path_str, NodeLabel.METHOD, method_qn
                        )

                        # Register for lookup
                        self.function_registry[method_qn] = NodeLabel.METHOD
                        self.simple_name_lookup[func_name].add(method_qn)
                    else:
                        # This is a standalone function
                        func_qn = f"{module_qn}.{func_name}"
                        decorators = self._extract_decorators(func_node, language)

                        # Extract docstring
                        docstring = self._extract_docstring(func_node, language)

                        current_time = int(time.time())
                        self.ingestor.ensure_node_batch(
                            NodeLabel.FUNCTION,
                            {
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

                        # Create DEFINES relationship
                        self.ingestor.ensure_relationship_batch(
                            NodeLabel.MODULE,
                            "qualified_name",
                            module_qn,
                            RelationshipType.DEFINES_FUNC,
                            NodeLabel.FUNCTION,
                            "qualified_name",
                            func_qn,
                        )

                        # Track function
                        self.ingestor.ensure_tracks_relationship(
                            relative_path_str, NodeLabel.FUNCTION, func_qn
                        )

                        # Register for lookup
                        self.function_registry[func_qn] = NodeLabel.FUNCTION
                        self.simple_name_lookup[func_name].add(func_qn)

    def _extract_decorators(self, node: Node, language: str) -> list[str]:
        """Extract decorators from a function/class node."""
        decorators = []

        if language == "python":
            # Look for decorator nodes
            for child in node.children:
                if child.type == "decorator":
                    # Extract decorator name
                    for grandchild in child.children:
                        if grandchild.type == "identifier" and grandchild.text:
                            decorators.append(grandchild.text.decode("utf-8"))
                            break
                        elif grandchild.type == "attribute":
                            # Handle @module.decorator
                            attr_node = grandchild.child_by_field_name("attribute")
                            if attr_node and attr_node.text:
                                decorators.append(attr_node.text.decode("utf-8"))
                                break

        return decorators

    def _extract_docstring(self, node: Node, language: str) -> str | None:
        """Extract docstring from function/class node."""
        if language == "python":
            # Get the body node
            body_node = node.child_by_field_name("body")
            if not body_node or not body_node.children:
                return None

            # Check if first statement is a string (docstring)
            first_statement = body_node.children[0]
            if first_statement.type == "expression_statement":
                # Check if it contains a string
                for child in first_statement.children:
                    if child.type == "string" and child.text:
                        # Extract and clean the docstring
                        docstring = child.text.decode("utf-8")
                        # Remove quotes (handle various quote styles)
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
        # Add support for other languages later
        return None

    def _extract_inheritance(self, class_node: Node, language: str) -> list[str]:
        """Extract parent class names from class definition."""
        parent_names = []

        if language == "python":
            # Look for argument_list in class definition
            for child in class_node.children:
                if child.type == "argument_list":
                    # Each argument is a parent class
                    for arg in child.children:
                        if arg.type == "identifier" and arg.text:
                            parent_names.append(arg.text.decode("utf-8"))
                        elif arg.type == "attribute":
                            # Handle module.Class inheritance
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
            # Get attribute name
            attr_node = node.child_by_field_name("attribute")
            if attr_node and attr_node.text:
                parts.insert(0, attr_node.text.decode("utf-8"))

            # Get object name
            obj_node = node.child_by_field_name("object")
            if obj_node:
                self._extract_full_name(obj_node, parts)

    def _find_parent_class(self, func_node: Node, module_qn: str) -> str | None:
        """Find the parent class of a function node."""
        # Walk up the tree to find containing class
        current = func_node.parent

        while current:
            if current.type in ["class_definition", "class_declaration"]:
                # Extract class name
                for child in current.children:
                    if child.type == "identifier" and child.text:
                        class_name = child.text.decode("utf-8")
                        return f"{module_qn}.{class_name}"

            current = current.parent

        return None

    def _process_relationships(self) -> None:
        """Third pass: Process function calls and imports."""
        # If parallel mode was used, relationships are already resolved
        # by ParallelExecutor during the definitions phase
        if self._parallel_mode_active:
            logger.info(
                "Skipping relationship processing "
                "(already resolved during parallel execution)"
            )
            # Report progress as complete for UI consistency
            total = len(self.function_registry)
            self._report_progress(
                "relationships",
                "Relationships resolved during parallel execution",
                total,
                total,
                phase_complete=True,
            )
            return

        # Sequential mode - process relationships normally
        # Process inheritance relationships first
        self._process_inheritance()

        # Then process function calls
        total_files = len(self.ast_cache)
        logger.info(f"Processing function calls for {total_files} files...")
        logger.info(f"Function registry has {len(self.function_registry)} entries")
        logger.info(
            f"Simple name lookup has {len(self.simple_name_lookup)} unique names"
        )

        file_count = 0
        for filepath, (root_node, language) in self.ast_cache.items():
            self._process_calls(filepath, root_node, language)
            # TODO(future): Add import statement processing for IMPORTS relationships

            file_count += 1
            # Report progress after each file
            self._report_progress(
                "relationships",
                "Processing relationships (calls, imports)",
                file_count,
                total_files,
            )

        # Report phase completion
        self._report_progress(
            "relationships",
            "Processing relationships (calls, imports)",
            file_count,
            total_files,
            phase_complete=True,
        )

    def _process_inheritance(self) -> None:
        """Process inheritance relationships between classes."""
        logger.info("Processing inheritance relationships...")

        for child_qn, parent_qns in self.class_inheritance.items():
            for parent_qn in parent_qns:
                # Check if parent exists in our registry
                if parent_qn in self.function_registry:
                    # Create INHERITS relationship
                    self.ingestor.ensure_relationship_batch(
                        NodeLabel.CLASS,
                        "qualified_name",
                        child_qn,
                        RelationshipType.INHERITS,
                        NodeLabel.CLASS,
                        "qualified_name",
                        parent_qn,
                    )
                else:
                    # Try to find parent by simple name lookup
                    parent_simple_name = parent_qn.split(".")[-1]
                    possible_parents = self.simple_name_lookup.get(
                        parent_simple_name, set()
                    )

                    # If we find exactly one match, use it
                    if len(possible_parents) == 1:
                        actual_parent_qn = list(possible_parents)[0]
                        self.ingestor.ensure_relationship_batch(
                            NodeLabel.CLASS,
                            "qualified_name",
                            child_qn,
                            RelationshipType.INHERITS,
                            NodeLabel.CLASS,
                            "qualified_name",
                            actual_parent_qn,
                        )

    def _process_calls(self, filepath: Path, root_node: Node, language: str) -> None:
        """Process function calls in a file."""
        lang_queries = self.queries.get(language, {})

        if "call_query" not in lang_queries:
            return

        # Get the module qualified name
        relative_path = filepath.relative_to(self.repo_path)
        if filepath.name == "__init__.py":
            module_qn = ".".join([self.project_name] + list(relative_path.parent.parts))
        else:
            module_qn = ".".join(
                [self.project_name] + list(relative_path.with_suffix("").parts)
            )

        # Find all call expressions
        cursor = QueryCursor(lang_queries["call_query"])
        matches = list(cursor.matches(root_node))
        for match in matches:
            call_node = None

            captures = match[1]  # Get captures dictionary from tuple
            for capture_name, nodes in captures.items():
                for node in nodes:
                    if capture_name == "call":
                        call_node = node
                        break

            if call_node:
                self._process_single_call(call_node, module_qn, language)

    def _process_single_call(
        self, call_node: Node, module_qn: str, language: str
    ) -> None:
        """Process a single function call with smart resolution."""
        # Extract called function name and context (simplified)
        callee_name = None
        object_name = None  # For method calls like obj.method()

        if language in ["python", "javascript", "typescript"]:
            # Look for function/method name
            for child in call_node.children:
                if child.type == "identifier" and child.text:
                    callee_name = child.text.decode("utf-8")
                    break
                elif child.type == "attribute":
                    # Handle method calls like obj.method()
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

        # Get all possible callees
        possible_callees = self.simple_name_lookup.get(callee_name, set())
        if not possible_callees:
            return

        # Calculate confidence scores for each possible callee
        scored_callees = []
        for possible_qn in possible_callees:
            score = calculate_callee_confidence(
                caller_qn, possible_qn, module_qn, object_name, self.simple_name_lookup
            )
            scored_callees.append((possible_qn, score))

        # Sort by confidence score (highest first)
        scored_callees.sort(key=lambda x: x[1], reverse=True)

        # Use the highest confidence match
        callee_qn, confidence = scored_callees[0]

        # Create CALLS relationship with metadata
        caller_type = self.function_registry.get(caller_qn)
        callee_type = self.function_registry.get(callee_qn)

        if caller_type and callee_type:
            # Create the primary CALLS relationship
            self.ingestor.ensure_relationship_batch(
                caller_type,
                "qualified_name",
                caller_qn,
                "CALLS",
                callee_type,
                "qualified_name",
                callee_qn,
            )

    def _find_containing_function(self, node: Node, module_qn: str) -> str | None:
        """Find the containing function/method of a node."""
        current = node.parent

        while current:
            if current.type in [
                "function_definition",
                "method_definition",
                "arrow_function",
            ]:
                # Extract function name
                for child in current.children:
                    if child.type == "identifier" and child.text:
                        func_name = child.text.decode("utf-8")

                        # Check if this is inside a class
                        parent_class = self._find_parent_class(current, module_qn)
                        if parent_class:
                            return f"{parent_class}.{func_name}"
                        else:
                            return f"{module_qn}.{func_name}"

            current = current.parent

        return None


class CodebaseIngestor:
    """Main ingestor class for building code knowledge graphs."""

    def __init__(
        self,
        db_path: str,
        project_name: str | None = None,
        exclude_patterns: list[str] | None = None,
        progress_callback: Any | None = None,
    ):
        """Initialize the ingestor.

        Args:
            db_path: Path to Kuzu database
            project_name: Optional project name
            exclude_patterns: Patterns to exclude from processing
            progress_callback: Optional callback for progress reporting
        """
        self.db_path = Path(db_path)
        self.project_name = project_name
        self.exclude_patterns = exclude_patterns or []
        self.progress_callback = progress_callback

    def build_graph_from_directory(self, repo_path: str) -> None:
        """Build a code knowledge graph from a directory.

        Args:
            repo_path: Path to repository directory
        """
        repo_path_obj = Path(repo_path)

        # Use directory name as project name if not specified
        if not self.project_name:
            self.project_name = repo_path_obj.name

        try:
            # Create database (lazy import kuzu for Windows compatibility)
            kuzu = get_kuzu()
            logger.info(f"Creating Kuzu database at: {self.db_path}")
            db = kuzu.Database(str(self.db_path))
            conn = kuzu.Connection(db)

            # Initialize ingestor
            ingestor = Ingestor(conn)
            ingestor.create_schema()

            # Load parsers
            logger.info("Loading language parsers...")
            parsers, queries = load_parsers()

            # Build graph
            builder = SimpleGraphBuilder(
                ingestor,
                repo_path_obj,
                parsers,
                queries,
                self.exclude_patterns,
                self.progress_callback,
            )
            if self.project_name:
                builder.project_name = self.project_name
            asyncio.run(builder.run())

            logger.info(f"Graph successfully created at: {self.db_path}")

        except Exception as e:
            logger.error(f"Failed to build graph: {e}")
            raise
