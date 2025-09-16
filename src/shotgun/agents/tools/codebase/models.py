"""Pydantic models for codebase tool outputs."""

from typing import Any

from pydantic import BaseModel, Field


class QueryGraphResult(BaseModel):
    """Result from graph query with formatted string output."""

    success: bool = Field(description="Whether the query was successful")
    query: str = Field(description="Original natural language query")
    cypher_query: str | None = Field(None, description="Generated Cypher query")
    column_names: list[str] = Field(
        default_factory=list, description="Result column names"
    )
    results: list[dict[str, Any]] = Field(
        default_factory=list, description="Query results"
    )
    row_count: int = Field(0, description="Number of result rows")
    execution_time_ms: float = Field(
        0.0, description="Query execution time in milliseconds"
    )
    error: str | None = Field(default=None, description="Error message if failed")

    def __str__(self) -> str:
        """Format query result for LLM consumption."""
        if not self.success:
            return f"**Query Failed**: {self.error}"

        if not self.results:
            return f"**No Results Found** for query: {self.query}"

        output_lines = []
        if self.cypher_query:
            output_lines.append(f"**Generated Cypher**: `{self.cypher_query}`")
            output_lines.append("")

        output_lines.append(
            f"**Results** ({self.row_count} rows, {self.execution_time_ms:.1f}ms):"
        )
        output_lines.append("")

        if self.column_names and self.results:
            # Create markdown table
            headers = self.column_names
            output_lines.append("| " + " | ".join(headers) + " |")
            output_lines.append("|" + "|".join([" --- " for _ in headers]) + "|")

            # Limit to first 10 rows to avoid overwhelming output
            rows_to_show = min(10, len(self.results))
            for row in self.results[:rows_to_show]:
                row_values = []
                for col in headers:
                    value = row.get(col, "")
                    # Convert to string and truncate if too long
                    str_value = str(value) if value is not None else ""
                    if len(str_value) > 50:
                        str_value = str_value[:47] + "..."
                    row_values.append(str_value)
                output_lines.append("| " + " | ".join(row_values) + " |")

            if self.row_count > rows_to_show:
                output_lines.append(
                    f"... and {self.row_count - rows_to_show} more rows"
                )

        return "\n".join(output_lines)


class CodeSnippetResult(BaseModel):
    """Result from code retrieval with formatted output."""

    found: bool = Field(description="Whether the code entity was found")
    qualified_name: str = Field(description="Fully qualified name searched for")
    file_path: str | None = Field(None, description="Path to source file")
    line_start: int | None = Field(None, description="Starting line number")
    line_end: int | None = Field(None, description="Ending line number")
    source_code: str | None = Field(None, description="Source code content")
    docstring: str | None = Field(None, description="Docstring if available")
    language: str = Field(
        default="", description="Programming language for syntax highlighting"
    )
    error: str | None = Field(None, description="Error message if not found")

    def __str__(self) -> str:
        """Format code snippet for LLM consumption."""
        if not self.found:
            error_msg = (
                self.error or f"Entity '{self.qualified_name}' not found in graph"
            )
            return f"**Not Found**: {error_msg}\n\nTry using `query_graph` to search for similar entities or check the qualified name."

        output_lines = []
        output_lines.append(f"**Qualified Name**: `{self.qualified_name}`")

        if self.file_path:
            output_lines.append(f"**File**: `{self.file_path}`")

        if self.line_start and self.line_end:
            output_lines.append(f"**Lines**: {self.line_start}-{self.line_end}")

        if self.docstring:
            output_lines.append(f"**Docstring**: {self.docstring}")

        if self.source_code:
            output_lines.append("")
            output_lines.append("**Source Code**:")
            language_tag = self.language if self.language else ""
            output_lines.append(f"```{language_tag}")
            output_lines.append(self.source_code)
            output_lines.append("```")

        return "\n".join(output_lines)


class FileReadResult(BaseModel):
    """Result from file reading with content output."""

    success: bool = Field(description="Whether file was read successfully")
    file_path: str = Field(description="Path to file that was read")
    content: str | None = Field(None, description="File content")
    encoding: str = Field("utf-8", description="Encoding used to read file")
    size_bytes: int = Field(0, description="File size in bytes")
    language: str = Field(
        default="", description="Programming language for syntax highlighting"
    )
    error: str | None = Field(default=None, description="Error message if failed")

    def __str__(self) -> str:
        """Return file content or error message."""
        if not self.success:
            return f"**Error reading file `{self.file_path}`**: {self.error}"

        output_lines = []
        output_lines.append(f"**File**: `{self.file_path}`")
        output_lines.append(f"**Size**: {self.size_bytes} bytes")

        if self.encoding != "utf-8":
            output_lines.append(f"**Encoding**: {self.encoding}")

        output_lines.append("")
        output_lines.append("**Content**:")
        language_tag = self.language if self.language else ""
        output_lines.append(f"```{language_tag}")
        output_lines.append(self.content or "")
        output_lines.append("```")

        return "\n".join(output_lines)


class DirectoryListResult(BaseModel):
    """Result from directory listing with structured output."""

    success: bool = Field(description="Whether directory was listed successfully")
    directory: str = Field(description="Directory path that was listed")
    full_path: str = Field(description="Absolute path to directory")
    directories: list[str] = Field(
        default_factory=list, description="Subdirectory names"
    )
    files: list[tuple[str, int]] = Field(
        default_factory=list, description="Files as (name, size_bytes) tuples"
    )
    error: str | None = Field(default=None, description="Error message if failed")

    def __str__(self) -> str:
        """Format directory listing for LLM consumption."""
        if not self.success:
            return f"**Error listing directory `{self.directory}`**: {self.error}"

        output_lines = []
        output_lines.append(f"**Directory**: `{self.directory}`")
        output_lines.append(f"**Full Path**: `{self.full_path}`")
        output_lines.append("")

        if not self.directories and not self.files:
            return "\n".join(output_lines + ["Directory is empty"])

        if self.directories:
            output_lines.append("**Directories**:")
            for dir_name in self.directories:
                output_lines.append(f"  📁 {dir_name}/")
            output_lines.append("")

        if self.files:
            output_lines.append("**Files**:")
            for file_name, size_bytes in self.files:
                if size_bytes < 1024:
                    size_str = f"{size_bytes}B"
                elif size_bytes < 1024 * 1024:
                    size_str = f"{size_bytes / 1024:.1f}KB"
                else:
                    size_str = f"{size_bytes / (1024 * 1024):.1f}MB"
                output_lines.append(f"  📄 {file_name} ({size_str})")

        output_lines.append("")
        output_lines.append(
            f"**Total**: {len(self.directories)} directories, {len(self.files)} files"
        )

        return "\n".join(output_lines)


class ShellCommandResult(BaseModel):
    """Result from shell command execution with formatted output."""

    success: bool = Field(description="Whether command executed without errors")
    command: str = Field(description="Command that was executed")
    args: list[str] = Field(default_factory=list, description="Command arguments")
    stdout: str = Field(default="", description="Standard output")
    stderr: str = Field(default="", description="Standard error output")
    return_code: int = Field(default=0, description="Process return code")
    execution_time_ms: float = Field(
        default=0.0, description="Execution time in milliseconds"
    )
    error: str | None = Field(
        default=None, description="Error message if execution failed"
    )

    def __str__(self) -> str:
        """Format command output for LLM consumption."""
        if self.error:
            return f"**Command Failed**: {self.error}"

        output_lines = []
        cmd_str = f"{self.command} {' '.join(self.args)}".strip()
        output_lines.append(f"**Command**: `{cmd_str}`")
        output_lines.append(f"**Execution Time**: {self.execution_time_ms:.1f}ms")

        if self.stdout:
            output_lines.append("")
            output_lines.append("**Output**:")
            output_lines.append("```")
            output_lines.append(self.stdout.rstrip())
            output_lines.append("```")

        if self.stderr:
            output_lines.append("")
            output_lines.append("**Error Output**:")
            output_lines.append("```")
            output_lines.append(self.stderr.rstrip())
            output_lines.append("```")

        if self.return_code != 0:
            output_lines.append("")
            output_lines.append(f"**Exit Code**: {self.return_code}")

        if not self.stdout and not self.stderr:
            output_lines.append("")
            output_lines.append("Command executed successfully with no output")

        return "\n".join(output_lines)
