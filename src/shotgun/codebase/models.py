"""Data models for codebase service."""

from collections.abc import Callable
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class GraphStatus(StrEnum):
    """Status of a code knowledge graph."""

    READY = "READY"  # Graph is ready for queries
    BUILDING = "BUILDING"  # Initial build in progress
    UPDATING = "UPDATING"  # Update in progress
    ERROR = "ERROR"  # Last operation failed


class IgnoreReason(StrEnum):
    """Reason why a file or directory was ignored during indexing."""

    HARDCODED = (
        "hardcoded"  # Matched hardcoded ignore patterns (venv, node_modules, etc.)
    )
    GITIGNORE = "gitignore"  # Matched .gitignore pattern


class QueryType(StrEnum):
    """Type of query being executed."""

    NATURAL_LANGUAGE = "natural_language"
    CYPHER = "cypher"


class ProgressPhase(StrEnum):
    """Phase of codebase indexing progress."""

    STRUCTURE = "structure"  # Identifying packages and folders
    DEFINITIONS = "definitions"  # Processing files and extracting definitions
    RELATIONSHIPS = "relationships"  # Processing relationships (calls, imports)
    FLUSH_NODES = "flush_nodes"  # Flushing nodes to database
    FLUSH_RELATIONSHIPS = "flush_relationships"  # Flushing relationships to database


class NodeLabel(StrEnum):
    """Node type labels for the code knowledge graph."""

    PROJECT = "Project"  # Top-level project node
    PACKAGE = "Package"  # Python package/namespace
    FOLDER = "Folder"  # Directory structure
    FILE = "File"  # Source file
    MODULE = "Module"  # Python module
    CLASS = "Class"  # Class definition
    FUNCTION = "Function"  # Function definition
    METHOD = "Method"  # Method definition (inside a class)
    FILE_METADATA = "FileMetadata"  # File tracking metadata (hash, mtime)
    EXTERNAL_PACKAGE = "ExternalPackage"  # External dependency
    DELETION_LOG = "DeletionLog"  # Deletion audit trail


class RelationshipType(StrEnum):
    """Relationship types for the code knowledge graph."""

    # Containment relationships (used with suffixes _PKG, _FOLDER in tables)
    CONTAINS_PACKAGE = "CONTAINS_PACKAGE"  # Container to Package
    CONTAINS_FOLDER = "CONTAINS_FOLDER"  # Container to Folder
    CONTAINS_FILE = "CONTAINS_FILE"  # Container to File
    CONTAINS_MODULE = "CONTAINS_MODULE"  # Container to Module

    # Definition relationships
    DEFINES = "DEFINES"  # Module to Class
    DEFINES_FUNC = "DEFINES_FUNC"  # Module to Function
    DEFINES_METHOD = "DEFINES_METHOD"  # Class to Method

    # Call relationships
    CALLS = "CALLS"  # Function to Function
    CALLS_FM = "CALLS_FM"  # Function to Method
    CALLS_MF = "CALLS_MF"  # Method to Function
    CALLS_MM = "CALLS_MM"  # Method to Method

    # Tracking relationships (FileMetadata to entity)
    TRACKS_MODULE = "TRACKS_Module"  # FileMetadata to Module
    TRACKS_CLASS = "TRACKS_Class"  # FileMetadata to Class
    TRACKS_FUNCTION = "TRACKS_Function"  # FileMetadata to Function
    TRACKS_METHOD = "TRACKS_Method"  # FileMetadata to Method

    # Other relationships
    INHERITS = "INHERITS"  # Child Class to Parent Class
    OVERRIDES = "OVERRIDES"  # Method to Method (override)
    IMPORTS = "IMPORTS"  # Module to Module
    DEPENDS_ON_EXTERNAL = "DEPENDS_ON_EXTERNAL"  # Project to ExternalPackage


class IndexProgress(BaseModel):
    """Progress information for codebase indexing."""

    phase: ProgressPhase = Field(..., description="Current indexing phase")
    phase_name: str = Field(..., description="Human-readable phase name")
    current: int = Field(..., description="Current item count")
    total: int | None = Field(None, description="Total items (None if unknown)")
    phase_complete: bool = Field(
        default=False, description="Whether this phase is complete"
    )


# Type alias for progress callback function
ProgressCallback = Callable[[IndexProgress], None]


class GitignoreStats(BaseModel):
    """Statistics from gitignore pattern matching."""

    gitignore_files_loaded: int = Field(
        default=0, description="Number of .gitignore files loaded"
    )
    patterns_loaded: int = Field(default=0, description="Total patterns loaded")
    files_checked: int = Field(default=0, description="Number of paths checked")
    files_ignored: int = Field(
        default=0, description="Number of paths ignored by gitignore"
    )


class IndexingStats(BaseModel):
    """Statistics from codebase indexing."""

    dirs_scanned: int = Field(default=0, description="Directories scanned")
    dirs_ignored_hardcoded: int = Field(
        default=0, description="Directories ignored by hardcoded patterns"
    )
    dirs_ignored_gitignore: int = Field(
        default=0, description="Directories ignored by gitignore"
    )
    files_scanned: int = Field(default=0, description="Files scanned")
    files_ignored_hardcoded: int = Field(
        default=0, description="Files ignored by hardcoded patterns"
    )
    files_ignored_gitignore: int = Field(
        default=0, description="Files ignored by gitignore"
    )
    files_ignored_no_parser: int = Field(
        default=0, description="Files ignored due to no parser available"
    )
    files_processed: int = Field(default=0, description="Files successfully processed")


class OperationStats(BaseModel):
    """Statistics for a graph operation (build/update)."""

    operation_type: str = Field(..., description="Type of operation: build or update")
    started_at: float = Field(..., description="Unix timestamp when operation started")
    completed_at: float | None = Field(
        None, description="Unix timestamp when operation completed"
    )
    success: bool = Field(default=False, description="Whether operation succeeded")
    error: str | None = Field(None, description="Error message if operation failed")
    stats: dict[str, Any] = Field(
        default_factory=dict, description="Operation statistics"
    )


class CodebaseGraph(BaseModel):
    """Represents a code knowledge graph."""

    graph_id: str = Field(..., description="Unique graph ID (hash of repo path)")
    repo_path: str = Field(..., description="Absolute path to repository")
    graph_path: str = Field(..., description="Path to Kuzu database")
    name: str = Field(..., description="Human-readable name for the graph")
    created_at: float = Field(..., description="Unix timestamp of creation")
    updated_at: float = Field(..., description="Unix timestamp of last update")
    schema_version: str = Field(default="1.0.0", description="Graph schema version")
    build_options: dict[str, Any] = Field(
        default_factory=dict, description="Build configuration"
    )
    language_stats: dict[str, int] = Field(
        default_factory=dict, description="File count by language"
    )
    node_count: int = Field(default=0, description="Total number of nodes")
    relationship_count: int = Field(
        default=0, description="Total number of relationships"
    )
    node_stats: dict[str, int] = Field(
        default_factory=dict, description="Node counts by type"
    )
    relationship_stats: dict[str, int] = Field(
        default_factory=dict, description="Relationship counts by type"
    )
    is_watching: bool = Field(default=False, description="Whether watcher is active")
    status: GraphStatus = Field(
        default=GraphStatus.READY, description="Current status of the graph"
    )
    last_operation: OperationStats | None = Field(
        None, description="Statistics from the last operation"
    )
    current_operation_id: str | None = Field(
        None, description="ID of current in-progress operation"
    )
    indexed_from_cwds: list[str] = Field(
        default_factory=list,
        description="List of working directories from which this graph is accessible. Empty list means globally accessible.",
    )


class QueryResult(BaseModel):
    """Result of a Cypher query execution."""

    query: str = Field(..., description="Original query (natural language or Cypher)")
    cypher_query: str | None = Field(
        None, description="Generated Cypher query if from natural language"
    )
    results: list[dict[str, Any]] = Field(
        default_factory=list, description="Query results"
    )
    column_names: list[str] = Field(
        default_factory=list, description="Result column names"
    )
    row_count: int = Field(default=0, description="Number of result rows")
    execution_time_ms: float = Field(
        ..., description="Query execution time in milliseconds"
    )
    success: bool = Field(default=True, description="Whether query succeeded")
    error: str | None = Field(None, description="Error message if failed")


class FileChange(BaseModel):
    """Represents a file system change."""

    event_type: str = Field(
        ..., description="Type of change: created, modified, deleted, moved"
    )
    src_path: str = Field(..., description="Source file path")
    dest_path: str | None = Field(None, description="Destination path for moves")
    is_directory: bool = Field(default=False, description="Whether path is a directory")
