"""Type definitions for indexing metrics collection.

These models define the data structures for tracking performance metrics
during codebase indexing operations, as well as work distribution types
for parallel file parsing.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from shotgun.codebase.models import NodeLabel, RelationshipType

__all__ = [
    "DistributionStats",
    "FileInfo",
    "FileParseMetrics",
    "FileParseResult",
    "FileParseTask",
    "IndexingMetrics",
    "IndexingPhase",
    "InheritanceData",
    "NodeData",
    "NodeLabel",
    "ParallelExecutionResult",
    "PhaseMetrics",
    "RawCallData",
    "RelationshipData",
    "RelationshipType",
    "WorkBatch",
    "WorkerMetrics",
]


class IndexingPhase(StrEnum):
    """Phase names for indexing operations."""

    STRUCTURE = "structure"
    DEFINITIONS = "definitions"
    RELATIONSHIPS = "relationships"
    FLUSH_NODES = "flush_nodes"
    FLUSH_RELATIONSHIPS = "flush_relationships"


class PhaseMetrics(BaseModel):
    """Metrics for a single execution phase."""

    phase_name: str = Field(..., description="Name of the phase")
    start_time: float = Field(..., description="Unix timestamp when phase started")
    end_time: float = Field(..., description="Unix timestamp when phase ended")
    duration_seconds: float = Field(..., description="Total duration in seconds")
    items_processed: int = Field(..., description="Number of items processed")
    throughput: float = Field(..., description="Items per second")
    memory_mb: float = Field(..., description="Peak memory usage in MB")

    # Worker-specific metrics (for parallel phases)
    worker_count: int | None = Field(None, description="Number of parallel workers")
    worker_metrics: dict[int, WorkerMetrics] | None = Field(
        None, description="Per-worker performance metrics"
    )


class WorkerMetrics(BaseModel):
    """Metrics for a single worker process."""

    worker_id: int = Field(..., description="Unique worker identifier")
    files_processed: int = Field(..., description="Files processed by this worker")
    nodes_created: int = Field(..., description="Nodes created by this worker")
    relationships_created: int = Field(..., description="Relationships created")
    duration_seconds: float = Field(..., description="Total processing time")
    throughput: float = Field(..., description="Files per second")
    peak_memory_mb: float = Field(..., description="Peak memory usage")
    idle_time_seconds: float = Field(..., description="Time spent waiting for work")
    error_count: int = Field(default=0, description="Number of errors encountered")


class FileParseMetrics(BaseModel):
    """Detailed metrics for parsing a single file."""

    file_path: str = Field(..., description="Relative path to file")
    language: str = Field(..., description="Programming language")
    file_size_bytes: int = Field(..., description="File size in bytes")
    parse_time_ms: float = Field(..., description="Time to parse file")
    ast_nodes: int = Field(..., description="Number of AST nodes")
    definitions_extracted: int = Field(
        ..., description="Classes, functions, methods found"
    )
    relationships_found: int = Field(..., description="Calls, imports found")
    worker_id: int | None = Field(None, description="Worker that processed this file")


class IndexingMetrics(BaseModel):
    """Complete metrics for the entire indexing operation."""

    session_id: str = Field(..., description="Unique session identifier")
    codebase_name: str = Field(..., description="Name of indexed codebase")
    total_duration_seconds: float = Field(..., description="End-to-end duration")

    # Phase-level metrics
    phase_metrics: dict[str, PhaseMetrics] = Field(
        default_factory=dict, description="Metrics for each indexing phase"
    )

    # File-level metrics
    file_metrics: list[FileParseMetrics] = Field(
        default_factory=list, description="Per-file parsing metrics"
    )

    # Aggregate statistics
    total_files: int = Field(..., description="Total files processed")
    total_nodes: int = Field(..., description="Total nodes created")
    total_relationships: int = Field(..., description="Total relationships created")

    # Performance metrics
    avg_throughput: float = Field(..., description="Average files per second")
    peak_memory_mb: float = Field(..., description="Peak memory usage")
    parallelism_efficiency: float | None = Field(
        None, description="Efficiency factor (0.0-1.0) of parallelization"
    )


# =============================================================================
# Work Distribution Types
# =============================================================================


class FileInfo(BaseModel):
    """Information about a file for work distribution.

    Used by WorkDistributor to calculate balanced work assignments
    based on file size.
    """

    file_path: Path = Field(..., description="Absolute path to file")
    relative_path: Path = Field(..., description="Path relative to repo root")
    language: str = Field(..., description="Programming language")
    module_qn: str = Field(..., description="Qualified name for the module")
    container_qn: str | None = Field(
        None, description="Parent package/folder qualified name"
    )
    file_size_bytes: int = Field(..., description="File size in bytes for balancing")

    model_config = {"arbitrary_types_allowed": True}


class FileParseTask(BaseModel):
    """A task representing a file to be parsed by a worker.

    This is the serializable unit of work sent to worker processes.
    """

    file_path: Path = Field(..., description="Absolute path to file")
    relative_path: Path = Field(..., description="Path relative to repo root")
    language: str = Field(..., description="Programming language")
    module_qn: str = Field(..., description="Qualified name for the module")
    container_qn: str | None = Field(
        None, description="Parent package/folder qualified name"
    )

    model_config = {"arbitrary_types_allowed": True}


class WorkBatch(BaseModel):
    """A batch of file parse tasks for distribution to a worker.

    Batches group multiple tasks together to reduce queue overhead
    when distributing work across processes.
    """

    batch_id: int = Field(..., description="Unique batch identifier")
    tasks: list[FileParseTask] = Field(..., description="Tasks in this batch")
    estimated_duration_seconds: float | None = Field(
        None, description="Estimated processing time"
    )


class DistributionStats(BaseModel):
    """Statistics about work distribution across workers.

    Provides insight into how files are balanced across workers
    for debugging and verification.
    """

    total_files: int = Field(..., description="Total number of files")
    total_bytes: int = Field(..., description="Total size in bytes")
    worker_count: int = Field(..., description="Number of workers")
    batch_size: int = Field(..., description="Files per batch")
    files_per_worker: list[int] = Field(
        ..., description="Number of files assigned to each worker"
    )
    bytes_per_worker: list[int] = Field(
        ..., description="Total bytes assigned to each worker"
    )


# =============================================================================
# Parallel Execution Types
# =============================================================================


class NodeData(BaseModel):
    """Data for creating a graph node.

    Used by workers to return extracted node information without
    direct database access. Use NodeLabel enum values for the label field.
    """

    label: str = Field(..., description="Node type from NodeLabel enum")
    properties: dict[str, Any] = Field(..., description="Node properties")


class RelationshipData(BaseModel):
    """Data for creating a graph relationship.

    Used by workers to return extracted relationship information
    without direct database access. Use NodeLabel enum for label fields
    and RelationshipType enum for rel_type.
    """

    from_label: str = Field(..., description="Source node type from NodeLabel enum")
    from_key: str = Field(..., description="Source node primary key field")
    from_value: Any = Field(..., description="Source node primary key value")
    rel_type: str = Field(
        ..., description="Relationship type from RelationshipType enum"
    )
    to_label: str = Field(..., description="Target node type from NodeLabel enum")
    to_key: str = Field(..., description="Target node primary key field")
    to_value: Any = Field(..., description="Target node primary key value")
    properties: dict[str, Any] | None = Field(
        None, description="Relationship properties"
    )


class RawCallData(BaseModel):
    """Raw call information extracted by worker (unresolved).

    Call relationships cannot be fully resolved in workers because
    they require the complete function_registry and simple_name_lookup
    which are built by aggregating data from all workers.
    """

    caller_qn: str = Field(..., description="Qualified name of caller function/method")
    callee_name: str = Field(..., description="Simple name of called function")
    object_name: str | None = Field(
        None, description="Object the method is called on (if method call)"
    )
    line_number: int = Field(..., description="Line number of the call")
    module_qn: str = Field(..., description="Module qualified name for context")


class InheritanceData(BaseModel):
    """Raw inheritance information extracted by worker.

    Inheritance relationships require resolution against the global
    registry to find the actual parent class qualified names.
    """

    child_class_qn: str = Field(..., description="Qualified name of child class")
    parent_simple_names: list[str] = Field(
        ..., description="Simple names of parent classes (need resolution)"
    )


class FileParseResult(BaseModel):
    """Result of parsing a single file.

    Contains all data extracted by a worker from a single file,
    including nodes, relationships, and deferred relationship data
    that requires post-aggregation resolution.
    """

    task: FileParseTask = Field(..., description="Original task")
    success: bool = Field(..., description="Whether parsing succeeded")
    error: str | None = Field(None, description="Error message if failed")

    # Extracted nodes and direct relationships
    nodes: list[NodeData] = Field(
        default_factory=list, description="Nodes extracted from file"
    )
    relationships: list[RelationshipData] = Field(
        default_factory=list, description="Direct relationships extracted"
    )

    # Registry data for aggregation
    function_registry_entries: dict[str, str] = Field(
        default_factory=dict,
        description="Map of qualified_name -> type (Class/Function/Method)",
    )
    simple_name_entries: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Map of simple_name -> list of qualified_names",
    )

    # Deferred relationship data (requires post-aggregation resolution)
    raw_calls: list[RawCallData] = Field(
        default_factory=list, description="Unresolved call data"
    )
    inheritance_data: list[InheritanceData] = Field(
        default_factory=list, description="Unresolved inheritance data"
    )

    # File metadata
    file_hash: str = Field(default="", description="SHA256 hash of file content")
    mtime: int = Field(default=0, description="File modification time")

    # Metrics
    metrics: FileParseMetrics | None = Field(
        None, description="Parsing metrics for this file"
    )

    model_config = {"arbitrary_types_allowed": True}


class ParallelExecutionResult(BaseModel):
    """Complete results from parallel execution.

    Aggregates results from all workers including resolved relationships
    and merged registries.
    """

    results: list[FileParseResult] = Field(
        default_factory=list, description="Results from all files"
    )
    resolved_relationships: list[RelationshipData] = Field(
        default_factory=list, description="Relationships resolved post-aggregation"
    )
    function_registry: dict[str, str] = Field(
        default_factory=dict, description="Merged function registry from all workers"
    )
    simple_name_lookup: dict[str, list[str]] = Field(
        default_factory=dict, description="Merged simple name lookup from all workers"
    )

    # Metrics
    total_files: int = Field(default=0, description="Total files processed")
    successful_files: int = Field(default=0, description="Files successfully parsed")
    failed_files: int = Field(default=0, description="Files that failed to parse")
    total_duration_seconds: float = Field(
        default=0.0, description="Total execution duration"
    )
    worker_metrics: dict[int, WorkerMetrics] = Field(
        default_factory=dict, description="Per-worker metrics"
    )
