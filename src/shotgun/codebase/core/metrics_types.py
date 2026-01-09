"""Type definitions for indexing metrics collection.

These models define the data structures for tracking performance metrics
during codebase indexing operations.
"""

from pydantic import BaseModel, Field


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
    worker_metrics: dict[int, "WorkerMetrics"] | None = Field(
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
