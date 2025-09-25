"""Result models for SDK operations."""

from typing import Any

from pydantic import BaseModel

from shotgun.codebase.models import CodebaseGraph, QueryResult


class ListResult(BaseModel):
    """Result for list command."""

    graphs: list[CodebaseGraph]

    def __str__(self) -> str:
        """Format list result as plain text table."""
        if not self.graphs:
            return "No indexed codebases found."

        lines = [
            f"{'ID':<12} {'Name':<30} {'Status':<10} {'Files':<8} {'Path'}",
            "-" * 80,
        ]

        for graph in self.graphs:
            file_count = (
                sum(graph.language_stats.values()) if graph.language_stats else 0
            )
            lines.append(
                f"{graph.graph_id[:12]:<12} {graph.name[:30]:<30} {graph.status.value:<10} {file_count:<8} {graph.repo_path}"
            )

        return "\n".join(lines)


class IndexResult(BaseModel):
    """Result for index command."""

    graph_id: str
    name: str
    repo_path: str
    file_count: int
    node_count: int
    relationship_count: int

    def __str__(self) -> str:
        """Format index result as success message."""
        return (
            "Successfully indexed codebase!\n"
            f"Graph ID: {self.graph_id}\n"
            f"Files processed: {self.file_count}\n"
            f"Nodes: {self.node_count}\n"
            f"Relationships: {self.relationship_count}"
        )


class DeleteResult(BaseModel):
    """Result for delete command."""

    graph_id: str
    name: str
    deleted: bool
    cancelled: bool = False

    def __str__(self) -> str:
        """Format delete result message."""
        if self.cancelled:
            return "Deletion cancelled."
        elif self.deleted:
            return f"Successfully deleted codebase: {self.graph_id}"
        else:
            return f"Failed to delete codebase: {self.graph_id}"


class InfoResult(BaseModel):
    """Result for info command."""

    graph: CodebaseGraph

    def __str__(self) -> str:
        """Format detailed graph information."""
        graph = self.graph
        lines = [
            f"Graph ID: {graph.graph_id}",
            f"Name: {graph.name}",
            f"Status: {graph.status.value}",
            f"Repository Path: {graph.repo_path}",
            f"Database Path: {graph.graph_path}",
            f"Created: {graph.created_at}",
            f"Updated: {graph.updated_at}",
            f"Schema Version: {graph.schema_version}",
            f"Total Nodes: {graph.node_count}",
            f"Total Relationships: {graph.relationship_count}",
        ]

        if graph.language_stats:
            lines.append("\nLanguage Statistics:")
            for lang, count in graph.language_stats.items():
                lines.append(f"  {lang}: {count} files")

        if graph.node_stats:
            lines.append("\nNode Statistics:")
            for node_type, count in graph.node_stats.items():
                lines.append(f"  {node_type}: {count}")

        if graph.relationship_stats:
            lines.append("\nRelationship Statistics:")
            for rel_type, count in graph.relationship_stats.items():
                lines.append(f"  {rel_type}: {count}")

        return "\n".join(lines)


class QueryCommandResult(BaseModel):
    """Result for query command."""

    graph_name: str
    query_type: str
    result: QueryResult

    def __str__(self) -> str:
        """Format query results table."""
        query_result = self.result

        if not query_result.success:
            return f"Query failed: {query_result.error}"

        if not query_result.results:
            return "No results found."

        lines = [
            f"Query executed in {query_result.execution_time_ms:.2f}ms",
            f"Results: {query_result.row_count} rows",
        ]

        if query_result.cypher_query:
            lines.append(f"Generated Cypher: {query_result.cypher_query}")

        lines.append("")  # Empty line

        # Format results table
        if query_result.column_names:
            header = " | ".join(f"{col:<20}" for col in query_result.column_names)
            lines.append(header)
            lines.append("-" * len(header))

            for row in query_result.results:
                row_data = " | ".join(
                    f"{str(row.get(col, '')):<20}" for col in query_result.column_names
                )
                lines.append(row_data)
        else:
            # Fallback for results without column names
            for i, row in enumerate(query_result.results):
                lines.append(f"Row {i + 1}:")
                for key, value in row.items():
                    lines.append(f"  {key}: {value}")
                lines.append("")

        return "\n".join(lines)


class ReindexResult(BaseModel):
    """Result for reindex command."""

    graph_id: str
    name: str
    stats: dict[str, Any] | None = None

    def __str__(self) -> str:
        """Format reindex completion message."""
        lines = ["Reindexing completed!"]
        if self.stats:
            lines.append(f"Stats: {self.stats}")
        return "\n".join(lines)


class ErrorResult(BaseModel):
    """Result for error cases."""

    error_message: str
    details: str | None = None

    def __str__(self) -> str:
        """Format error message."""
        output = f"Error: {self.error_message}"
        if self.details:
            output += f"\n{self.details}"
        return output
