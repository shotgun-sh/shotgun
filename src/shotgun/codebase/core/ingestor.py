"""Kuzu graph ingestor for building code knowledge graphs."""

import hashlib
import os
import time
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any

import kuzu
from tree_sitter import Node, Parser, QueryCursor

from shotgun.codebase.core.language_config import LANGUAGE_CONFIGS, get_language_config
from shotgun.codebase.core.parser_loader import load_parsers
from shotgun.logging_config import get_logger

logger = get_logger(__name__)


# Default ignore patterns
IGNORE_PATTERNS = {
    ".git",
    "venv",
    ".venv",
    "__pycache__",
    "node_modules",
    "build",
    "dist",
    ".eggs",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".claude",
    ".idea",
    ".vscode",
}


class Ingestor:
    """Handles all communication and ingestion with the Kuzu database."""

    def __init__(self, connection: kuzu.Connection):
        self.conn = connection
        self.node_buffer: list[tuple[str, dict[str, Any]]] = []
        self.relationship_buffer: list[
            tuple[str, str, Any, str, str, str, Any, dict[str, Any] | None]
        ] = []
        self.batch_size = 1000

    def create_schema(self) -> None:
        """Create the graph schema in Kuzu."""
        logger.info("Creating Kuzu schema...")

        # Node tables
        node_schemas = [
            "CREATE NODE TABLE Project(name STRING PRIMARY KEY, repo_path STRING, graph_id STRING, created_at INT64, updated_at INT64, schema_version STRING, build_options STRING, node_count INT64, relationship_count INT64, stats_updated_at INT64, status STRING, current_operation_id STRING, last_operation STRING)",
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
        # Check for duplicates based on primary key
        primary_key = self._get_primary_key(label, properties)
        if primary_key and self._is_duplicate_node(label, primary_key):
            return

        self.node_buffer.append((label, properties))

        if len(self.node_buffer) >= self.batch_size:
            self.flush_nodes()

    def _get_primary_key(self, label: str, properties: dict[str, Any]) -> str | None:
        """Get the primary key value for a node."""
        primary_key_field = self._get_primary_key_field(label)
        return properties.get(primary_key_field) if primary_key_field else None

    def _get_primary_key_field(self, label: str) -> str | None:
        """Get the primary key field name for a node type."""
        if label == "Project":
            return "name"
        elif label in ["Package", "Module", "Class", "Function", "Method"]:
            return "qualified_name"
        elif label in ["Folder", "File"]:
            return "path"
        elif label == "FileMetadata":
            return "filepath"
        elif label == "ExternalPackage":
            return "name"
        elif label == "DeletionLog":
            return "id"
        return None

    def _is_duplicate_node(self, label: str, primary_key: str) -> bool:
        """Check if a node with the given primary key already exists in the buffer."""
        for buffered_label, buffered_props in self.node_buffer:
            if buffered_label == label:
                buffered_key = self._get_primary_key(buffered_label, buffered_props)
                if buffered_key == primary_key:
                    return True
        return False

    def flush_nodes(self) -> None:
        """Flush pending node insertions to the database."""
        if not self.node_buffer:
            return

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

            except Exception as e:
                logger.error(f"Failed to insert {label} nodes: {e}")

        # Log node counts by type
        node_type_counts: dict[str, int] = {}
        for label, _ in self.node_buffer:
            node_type_counts[label] = node_type_counts.get(label, 0) + 1

        logger.info(f"Flushed {len(self.node_buffer)} nodes:")
        for label, count in sorted(node_type_counts.items()):
            logger.info(f"  {label}: {count}")

        self.node_buffer.clear()

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

    def flush_relationships(self) -> None:
        """Flush pending relationship insertions to the database."""
        if not self.relationship_buffer:
            return

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
                properties,
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
                        properties,
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
        table_mapping = {
            "CONTAINS_PACKAGE": {
                "Project": "CONTAINS_PACKAGE",
                "Package": "CONTAINS_PACKAGE_PKG",
                "Folder": "CONTAINS_PACKAGE_FOLDER",
            },
            "CONTAINS_FOLDER": {
                "Project": "CONTAINS_FOLDER",
                "Package": "CONTAINS_FOLDER_PKG",
                "Folder": "CONTAINS_FOLDER_FOLDER",
            },
            "CONTAINS_FILE": {
                "Project": "CONTAINS_FILE",
                "Package": "CONTAINS_FILE_PKG",
                "Folder": "CONTAINS_FILE_FOLDER",
            },
            "CONTAINS_MODULE": {
                "Project": "CONTAINS_MODULE",
                "Package": "CONTAINS_MODULE_PKG",
                "Folder": "CONTAINS_MODULE_FOLDER",
            },
        }

        if rel_type in table_mapping:
            return table_mapping[rel_type].get(from_label)
        elif rel_type == "DEFINES":
            if to_label == "Function":
                return "DEFINES_FUNC"
            else:
                return "DEFINES"
        elif rel_type == "CALLS":
            if from_label == "Function" and to_label == "Function":
                return "CALLS"
            elif from_label == "Function" and to_label == "Method":
                return "CALLS_FM"
            elif from_label == "Method" and to_label == "Function":
                return "CALLS_MF"
            elif from_label == "Method" and to_label == "Method":
                return "CALLS_MM"
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
            ("Module", "TRACKS_Module", "modules"),
            ("Class", "TRACKS_Class", "classes"),
            ("Function", "TRACKS_Function", "functions"),
            ("Method", "TRACKS_Method", "methods"),
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
    ):
        self.ingestor = ingestor
        self.repo_path = repo_path
        self.parsers = parsers
        self.queries = queries
        self.project_name = repo_path.name
        self.ignore_dirs = IGNORE_PATTERNS
        if exclude_patterns:
            self.ignore_dirs = self.ignore_dirs.union(set(exclude_patterns))

        # Caches
        self.structural_elements: dict[Path, str | None] = {}
        self.ast_cache: dict[Path, tuple[Node, str]] = {}
        self.function_registry: dict[str, str] = {}  # qualified_name -> type
        self.simple_name_lookup: dict[str, set[str]] = defaultdict(set)
        self.class_inheritance: dict[str, list[str]] = {}  # class_qn -> [parent_qns]

    def run(self) -> None:
        """Run the three-pass graph building process."""
        logger.info(f"Building graph for project: {self.project_name}")

        # Pass 1: Structure
        logger.info("Pass 1: Identifying packages and folders...")
        self._identify_structure()

        # Pass 2: Definitions
        logger.info("Pass 2: Processing files and extracting definitions...")
        self._process_files()

        # Pass 3: Relationships
        logger.info("Pass 3: Processing relationships (calls, imports)...")
        self._process_relationships()

        # Flush all pending operations
        logger.info("Flushing all data to database...")
        self.ingestor.flush_all()
        logger.info("Graph building complete!")

    def _identify_structure(self) -> None:
        """First pass: Walk directory to find packages and folders."""
        for root_str, dirs, _ in os.walk(self.repo_path, topdown=True):
            dirs[:] = [d for d in dirs if d not in self.ignore_dirs]
            root = Path(root_str)
            relative_root = root.relative_to(self.repo_path)

            # Skip root directory
            if root == self.repo_path:
                continue

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
                    "Package",
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
                        "Package",
                        "qualified_name",
                        parent_container_qn,
                        "CONTAINS_PACKAGE",
                        "Package",
                        "qualified_name",
                        package_qn,
                    )
                else:
                    # Parent is project root
                    self.ingestor.ensure_relationship_batch(
                        "Project",
                        "name",
                        self.project_name,
                        "CONTAINS_PACKAGE",
                        "Package",
                        "qualified_name",
                        package_qn,
                    )

                self.structural_elements[relative_root] = package_qn
            else:
                # Create folder
                self.ingestor.ensure_node_batch(
                    "Folder",
                    {
                        "path": str(relative_root).replace(os.sep, "/"),
                        "name": relative_root.name,
                    },
                )

                # Create containment relationship
                if parent_container_qn:
                    # Parent is a package
                    self.ingestor.ensure_relationship_batch(
                        "Package",
                        "qualified_name",
                        parent_container_qn,
                        "CONTAINS_FOLDER",
                        "Folder",
                        "path",
                        str(relative_root).replace(os.sep, "/"),
                    )
                elif parent_rel_path == Path("."):
                    # Parent is project root
                    self.ingestor.ensure_relationship_batch(
                        "Project",
                        "name",
                        self.project_name,
                        "CONTAINS_FOLDER",
                        "Folder",
                        "path",
                        str(relative_root).replace(os.sep, "/"),
                    )
                else:
                    # Parent is another folder
                    self.ingestor.ensure_relationship_batch(
                        "Folder",
                        "path",
                        str(parent_rel_path).replace(os.sep, "/"),
                        "CONTAINS_FOLDER",
                        "Folder",
                        "path",
                        str(relative_root).replace(os.sep, "/"),
                    )

                self.structural_elements[relative_root] = None

    def _process_files(self) -> None:
        """Second pass: Process files and extract definitions."""
        file_count = 0
        for root_str, _, files in os.walk(self.repo_path):
            root = Path(root_str)

            # Skip ignored directories
            if any(part in self.ignore_dirs for part in root.parts):
                continue

            for filename in files:
                filepath = root / filename

                # Check if this is a supported file
                ext = filepath.suffix
                lang_config = get_language_config(ext)

                if lang_config and lang_config.name in self.parsers:
                    self._process_single_file(filepath, lang_config.name)
                    file_count += 1

                    if file_count % 100 == 0:
                        logger.info(f"  Processed {file_count} files...")

        logger.info(f"  Total files processed: {file_count}")

    def _process_single_file(self, filepath: Path, language: str) -> None:
        """Process a single file."""
        relative_path = filepath.relative_to(self.repo_path)
        relative_path_str = str(relative_path).replace(os.sep, "/")

        # Create File node
        self.ingestor.ensure_node_batch(
            "File",
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
                "Project",
                "name",
                self.project_name,
                "CONTAINS_FILE",
                "File",
                "path",
                relative_path_str,
            )
        else:
            self.ingestor.ensure_relationship_batch(
                "Folder",
                "path",
                str(parent_rel_path).replace(os.sep, "/"),
                "CONTAINS_FILE",
                "File",
                "path",
                relative_path_str,
            )

        # Parse file
        try:
            with open(filepath, "rb") as f:
                content = f.read()

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
                "Module",
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
                    "Package",
                    "qualified_name",
                    parent_container,
                    "CONTAINS_MODULE",
                    "Module",
                    "qualified_name",
                    module_qn,
                )
            elif parent_rel_path == Path("."):
                # Parent is project root
                self.ingestor.ensure_relationship_batch(
                    "Project",
                    "name",
                    self.project_name,
                    "CONTAINS_MODULE",
                    "Module",
                    "qualified_name",
                    module_qn,
                )
            else:
                # Parent is a folder
                self.ingestor.ensure_relationship_batch(
                    "Folder",
                    "path",
                    str(parent_rel_path).replace(os.sep, "/"),
                    "CONTAINS_MODULE",
                    "Module",
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
                relative_path_str, "Module", module_qn
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
                        "Class",
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
                    logger.debug(
                        f"Creating DEFINES relationship: Module({module_qn}) -> Class({class_qn})"
                    )
                    self.ingestor.ensure_relationship_batch(
                        "Module",
                        "qualified_name",
                        module_qn,
                        "DEFINES",
                        "Class",
                        "qualified_name",
                        class_qn,
                    )

                    # Track class
                    self.ingestor.ensure_tracks_relationship(
                        relative_path_str, "Class", class_qn
                    )

                    # Register for lookup
                    self.function_registry[class_qn] = "Class"
                    self.simple_name_lookup[class_name].add(class_qn)

                    # Extract inheritance
                    parent_names = self._extract_inheritance(class_node, language)
                    if parent_names:
                        self.class_inheritance[class_qn] = parent_names

        # Extract functions
        if "function_query" in lang_queries:
            cursor = QueryCursor(lang_queries["function_query"])
            matches = list(cursor.matches(root_node))
            logger.debug(f"Found {len(matches)} function matches in {filepath}")
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
                    # Log what we found
                    logger.debug(
                        f"Found function: {func_name} at line {func_node.start_point.row + 1}"
                    )

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
                            "Method",
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
                            "Class",
                            "qualified_name",
                            parent_class,
                            "DEFINES_METHOD",
                            "Method",
                            "qualified_name",
                            method_qn,
                        )

                        # Track method
                        self.ingestor.ensure_tracks_relationship(
                            relative_path_str, "Method", method_qn
                        )

                        # Register for lookup
                        self.function_registry[method_qn] = "Method"
                        self.simple_name_lookup[func_name].add(method_qn)
                    else:
                        # This is a standalone function
                        func_qn = f"{module_qn}.{func_name}"
                        decorators = self._extract_decorators(func_node, language)

                        # Extract docstring
                        docstring = self._extract_docstring(func_node, language)

                        current_time = int(time.time())
                        self.ingestor.ensure_node_batch(
                            "Function",
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
                            "Module",
                            "qualified_name",
                            module_qn,
                            "DEFINES_FUNC",
                            "Function",
                            "qualified_name",
                            func_qn,
                        )

                        # Track function
                        self.ingestor.ensure_tracks_relationship(
                            relative_path_str, "Function", func_qn
                        )

                        # Register for lookup
                        self.function_registry[func_qn] = "Function"
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
        # Process inheritance relationships first
        self._process_inheritance()

        # Then process function calls
        logger.info(f"Processing function calls for {len(self.ast_cache)} files...")
        logger.info(f"Function registry has {len(self.function_registry)} entries")
        logger.info(
            f"Simple name lookup has {len(self.simple_name_lookup)} unique names"
        )

        # Log some examples from simple_name_lookup
        if self.simple_name_lookup:
            example_names = list(self.simple_name_lookup.keys())[:5]
            for name in example_names:
                logger.debug(
                    f"  Example: '{name}' -> {list(self.simple_name_lookup[name])[:3]}"
                )

        for filepath, (root_node, language) in self.ast_cache.items():
            self._process_calls(filepath, root_node, language)
            # NOTE: Add import processing. wtf does this mean?

    def _process_inheritance(self) -> None:
        """Process inheritance relationships between classes."""
        logger.info("Processing inheritance relationships...")

        for child_qn, parent_qns in self.class_inheritance.items():
            for parent_qn in parent_qns:
                # Check if parent exists in our registry
                if parent_qn in self.function_registry:
                    # Create INHERITS relationship
                    self.ingestor.ensure_relationship_batch(
                        "Class",
                        "qualified_name",
                        child_qn,
                        "INHERITS",
                        "Class",
                        "qualified_name",
                        parent_qn,
                    )
                    logger.debug(
                        f"  Created inheritance: {child_qn} INHERITS {parent_qn}"
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
                            "Class",
                            "qualified_name",
                            child_qn,
                            "INHERITS",
                            "Class",
                            "qualified_name",
                            actual_parent_qn,
                        )
                        logger.debug(
                            f"  Created inheritance: {child_qn} INHERITS {actual_parent_qn}"
                        )
                    else:
                        logger.debug(
                            f"  Could not resolve parent class: {parent_qn} for {child_qn}"
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
        logger.debug(f"Found {len(matches)} call matches in {filepath}")
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
            logger.debug(
                f"  Could not extract callee name from call at line {call_node.start_point[0]}"
            )
            return

        logger.debug(f"  Processing call to {callee_name} (object: {object_name})")

        # Find caller function
        caller_qn = self._find_containing_function(call_node, module_qn)
        if not caller_qn:
            logger.debug(
                f"  Could not find containing function for call at line {call_node.start_point[0]}"
            )
            return

        # Get all possible callees
        possible_callees = self.simple_name_lookup.get(callee_name, set())
        if not possible_callees:
            logger.debug(f"  No functions found with name: {callee_name}")
            return

        logger.debug(
            f"  Found {len(possible_callees)} possible callees for {callee_name}"
        )

        # Calculate confidence scores for each possible callee
        scored_callees = []
        for possible_qn in possible_callees:
            score = self._calculate_callee_confidence(
                caller_qn, possible_qn, module_qn, object_name
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

            # Log with confidence information
            alternatives = len(scored_callees) - 1
            logger.info(
                f"  Created CALLS relationship: {caller_qn} -> {callee_qn} (confidence: {confidence:.2f}, alternatives: {alternatives})"
            )

            # If multiple alternatives exist with similar confidence, log them
            if alternatives > 0 and confidence < 1.0:
                similar_alternatives = [
                    qn for qn, score in scored_callees[1:4] if score >= confidence * 0.8
                ]  # Top 3 alternatives  # Within 80% of best score
                if similar_alternatives:
                    logger.debug(
                        f"    Alternative matches: {', '.join(similar_alternatives)}"
                    )
        else:
            logger.warning(
                f"  Failed to create CALLS relationship - caller_type: {caller_type}, callee_type: {callee_type}"
            )

    def _calculate_callee_confidence(
        self, caller_qn: str, callee_qn: str, module_qn: str, object_name: str | None
    ) -> float:
        """Calculate confidence score for a potential callee match.

        Args:
            caller_qn: Qualified name of the calling function
            callee_qn: Qualified name of the potential callee
            module_qn: Qualified name of the current module
            object_name: Object name for method calls (e.g., 'obj' in obj.method())

        Returns:
            Confidence score between 0.0 and 1.0
        """
        score = 0.0

        # 1. Module locality - functions in the same module are most likely
        if callee_qn.startswith(module_qn + "."):
            score += 0.5

            # Even higher if in the same class
            caller_parts = caller_qn.split(".")
            callee_parts = callee_qn.split(".")
            if len(caller_parts) >= 3 and len(callee_parts) >= 3:
                if caller_parts[:-1] == callee_parts[:-1]:  # Same class
                    score += 0.2

        # 2. Package locality - functions in the same package hierarchy
        elif "." in module_qn:
            package = module_qn.rsplit(".", 1)[0]
            if callee_qn.startswith(package + "."):
                score += 0.3

        # 3. Object/class match for method calls
        if object_name:
            # Check if callee is a method of a class matching the object name
            callee_parts = callee_qn.split(".")
            if len(callee_parts) >= 2:
                # Simple heuristic: check if class name matches object name
                # (In reality, we'd need type inference for accuracy)
                class_name = callee_parts[-2]
                if class_name.lower() == object_name.lower():
                    score += 0.3
                elif object_name == "self" and callee_qn.startswith(
                    caller_qn.rsplit(".", 1)[0]
                ):
                    # 'self' refers to the same class
                    score += 0.4

        # 4. Import presence check (simplified - would need import tracking)
        # For now, we'll give a small boost to standard library functions
        if callee_qn.startswith(("builtins.", "typing.", "collections.")):
            score += 0.1

        # 5. Name similarity for disambiguation
        # If function names are unique enough, boost confidence
        possible_count = len(
            self.simple_name_lookup.get(callee_qn.split(".")[-1], set())
        )
        if possible_count == 1:
            score += 0.2
        elif possible_count <= 3:
            score += 0.1

        # Normalize to [0, 1]
        return min(score, 1.0)

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
    ):
        """Initialize the ingestor.

        Args:
            db_path: Path to Kuzu database
            project_name: Optional project name
            exclude_patterns: Patterns to exclude from processing
        """
        self.db_path = Path(db_path)
        self.project_name = project_name
        self.exclude_patterns = exclude_patterns or []

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
            # Create database
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
                ingestor, repo_path_obj, parsers, queries, self.exclude_patterns
            )
            if self.project_name:
                builder.project_name = self.project_name
            builder.run()

            logger.info(f"Graph successfully created at: {self.db_path}")

        except Exception as e:
            logger.error(f"Failed to build graph: {e}")
            raise
