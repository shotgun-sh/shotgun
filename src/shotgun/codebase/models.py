"""Data models for codebase service."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class GraphStatus(str, Enum):
    """Status of a code knowledge graph."""

    READY = "READY"  # Graph is ready for queries
    BUILDING = "BUILDING"  # Initial build in progress
    UPDATING = "UPDATING"  # Update in progress
    ERROR = "ERROR"  # Last operation failed


class QueryType(str, Enum):
    """Type of query being executed."""

    NATURAL_LANGUAGE = "natural_language"
    CYPHER = "cypher"


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
