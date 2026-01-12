"""Codebase management CLI commands."""

import asyncio
import traceback
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)

from shotgun.codebase.benchmarks import BenchmarkRunner, MetricsExporter, get_formatter
from shotgun.codebase.benchmarks.formatters import MetricsDisplayOptions
from shotgun.codebase.models import (
    CodebaseGraph,
    IndexProgress,
    QueryType,
)
from shotgun.logging_config import get_logger
from shotgun.sdk.codebase import CodebaseSDK
from shotgun.sdk.exceptions import CodebaseNotFoundError, InvalidPathError

from ..models import OutputFormat
from ..utils import output_result
from .models import ErrorResult

app = typer.Typer(
    name="codebase",
    help="Manage and query code knowledge graphs",
    no_args_is_help=True,
)

# Set up logger but it will be suppressed by default
logger = get_logger(__name__)


@app.command(name="list")
def list_codebases(
    format_type: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format")
    ] = OutputFormat.TEXT,
) -> None:
    """List all indexed codebases."""
    sdk = CodebaseSDK()

    try:
        result = asyncio.run(sdk.list_codebases())
        output_result(result, format_type)
    except Exception as e:
        error_result = ErrorResult(
            error_message=f"Error listing codebases: {e}",
            details=f"Full traceback:\n{traceback.format_exc()}",
        )
        output_result(error_result, format_type)
        raise typer.Exit(1) from e


@app.command()
def index(
    path: Annotated[str, typer.Argument(help="Path to repository to index")],
    name: Annotated[
        str, typer.Option("--name", "-n", help="Human-readable name for the codebase")
    ],
    format_type: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format")
    ] = OutputFormat.TEXT,
    # Benchmark flags
    benchmark: Annotated[
        bool,
        typer.Option("--benchmark", help="Enable benchmark mode with detailed metrics"),
    ] = False,
    iterations: Annotated[
        int,
        typer.Option(
            "--benchmark-iterations",
            help="Number of benchmark runs (requires --benchmark)",
        ),
    ] = 1,
    warmup: Annotated[
        int,
        typer.Option(
            "--benchmark-warmup", help="Number of warmup runs (requires --benchmark)"
        ),
    ] = 0,
    benchmark_output: Annotated[
        str,
        typer.Option(
            "--benchmark-output",
            help="Benchmark output format: json|markdown",
        ),
    ] = "json",
    benchmark_export: Annotated[
        str | None,
        typer.Option("--benchmark-export", help="Export metrics to file"),
    ] = None,
    show_files: Annotated[
        bool,
        typer.Option("--show-files", help="Show per-file metrics in benchmark output"),
    ] = False,
    show_workers: Annotated[
        bool,
        typer.Option(
            "--show-workers", help="Show per-worker metrics in benchmark output"
        ),
    ] = False,
    top_n: Annotated[
        int | None,
        typer.Option("--top-n", help="Show N slowest files (requires --benchmark)"),
    ] = None,
    sequential: Annotated[
        bool,
        typer.Option(
            "--sequential", help="Force sequential mode (disable parallelization)"
        ),
    ] = False,
) -> None:
    """Index a new codebase.

    By default, runs with a TUI progress display. Use --benchmark for detailed
    metrics reporting.
    """
    console = Console()

    # Validate path
    repo_path = Path(path).resolve()
    if not repo_path.exists():
        error_result = ErrorResult(error_message=f"Path does not exist: {repo_path}")
        output_result(error_result, format_type)
        raise typer.Exit(1)

    # Benchmark mode
    if benchmark:
        try:
            # Create and run benchmark
            runner = BenchmarkRunner(
                codebase_path=repo_path,
                codebase_name=name,
                iterations=iterations,
                warmup_iterations=warmup,
                parallel=not sequential,
                collect_file_metrics=show_files or top_n is not None,
                collect_worker_metrics=show_workers,
            )

            console.print(f"\n[bold blue]Starting benchmark: {name}[/bold blue]")
            console.print(f"Path: {repo_path}")
            console.print(f"Mode: {'Sequential' if sequential else 'Parallel'}")
            console.print(f"Iterations: {iterations} ({warmup} warmup)")
            console.print()

            results = asyncio.run(runner.run())

            # Format output
            formatter = get_formatter(benchmark_output)
            options = MetricsDisplayOptions(
                show_phase_metrics=True,
                show_worker_metrics=show_workers,
                show_file_metrics=show_files or top_n is not None,
                top_n_files=top_n,
            )
            output = formatter.format_results(results, options)
            console.print(output)

            # Export if requested
            if benchmark_export:
                exporter = MetricsExporter()
                exporter.export(results, Path(benchmark_export), options=options)
                console.print(
                    f"\n[green]Metrics exported to: {benchmark_export}[/green]"
                )

        except Exception as e:
            error_result = ErrorResult(
                error_message=f"Benchmark error: {e}",
                details=f"Full traceback:\n{traceback.format_exc()}",
            )
            output_result(error_result, format_type)
            raise typer.Exit(1) from e

    else:
        # Normal mode with TUI progress display
        sdk = CodebaseSDK()

        # Create progress display
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console,
        )

        # Track tasks by phase
        tasks = {}

        def progress_callback(progress_info: IndexProgress) -> None:
            """Update progress display based on indexing phase."""
            phase = progress_info.phase

            # Create task if it doesn't exist
            if phase not in tasks:
                if progress_info.total is not None:
                    tasks[phase] = progress.add_task(
                        progress_info.phase_name, total=progress_info.total
                    )
                else:
                    # Indeterminate progress (spinner only)
                    tasks[phase] = progress.add_task(
                        progress_info.phase_name, total=None
                    )

            task_id = tasks[phase]

            # Update task
            if progress_info.total is not None:
                progress.update(
                    task_id,
                    completed=progress_info.current,
                    total=progress_info.total,
                    description=f"[bold blue]{progress_info.phase_name}",
                )
            else:
                # Just update description for indeterminate tasks
                progress.update(
                    task_id,
                    description=f"[bold blue]{progress_info.phase_name} ({progress_info.current} items)",
                )

            # Mark as complete if phase is done
            if progress_info.phase_complete:
                if progress_info.total is not None:
                    progress.update(task_id, completed=progress_info.total)

        try:
            # Run indexing with progress display
            with progress:
                result = asyncio.run(
                    sdk.index_codebase(
                        repo_path, name, progress_callback=progress_callback
                    )
                )

            output_result(result, format_type)
        except InvalidPathError as e:
            error_result = ErrorResult(error_message=str(e))
            output_result(error_result, format_type)
            raise typer.Exit(1) from e
        except Exception as e:
            error_result = ErrorResult(
                error_message=f"Error indexing codebase: {e}",
                details=f"Full traceback:\n{traceback.format_exc()}",
            )
            output_result(error_result, format_type)
            raise typer.Exit(1) from e


@app.command()
def delete(
    graph_id: Annotated[str, typer.Argument(help="Graph ID to delete")],
    format_type: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format")
    ] = OutputFormat.TEXT,
) -> None:
    """Delete an indexed codebase."""
    sdk = CodebaseSDK()

    # CLI-specific confirmation callback
    def cli_confirm(graph: CodebaseGraph) -> bool:
        return typer.confirm(
            f"Are you sure you want to delete codebase '{graph.name}' ({graph_id})?"
        )

    try:
        result = asyncio.run(sdk.delete_codebase(graph_id, cli_confirm))
        output_result(result, format_type)
        if not result.deleted and not result.cancelled:
            raise typer.Exit(1)
    except CodebaseNotFoundError as e:
        error_result = ErrorResult(error_message=str(e))
        output_result(error_result, format_type)
        raise typer.Exit(1) from e
    except Exception as e:
        error_result = ErrorResult(
            error_message=f"Error deleting codebase: {e}",
            details=f"Full traceback:\n{traceback.format_exc()}",
        )
        output_result(error_result, format_type)
        raise typer.Exit(1) from e


@app.command()
def info(
    graph_id: Annotated[str, typer.Argument(help="Graph ID to show info for")],
    format_type: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format")
    ] = OutputFormat.TEXT,
) -> None:
    """Show detailed information about a codebase."""
    sdk = CodebaseSDK()

    try:
        result = asyncio.run(sdk.get_info(graph_id))
        output_result(result, format_type)
    except CodebaseNotFoundError as e:
        error_result = ErrorResult(error_message=str(e))
        output_result(error_result, format_type)
        raise typer.Exit(1) from e
    except Exception as e:
        error_result = ErrorResult(
            error_message=f"Error getting codebase info: {e}",
            details=f"Full traceback:\n{traceback.format_exc()}",
        )
        output_result(error_result, format_type)
        raise typer.Exit(1) from e


@app.command()
def query(
    graph_id: Annotated[str, typer.Argument(help="Graph ID to query")],
    query_text: Annotated[
        str, typer.Argument(help="Query text (natural language or Cypher)")
    ],
    cypher: Annotated[
        bool,
        typer.Option(
            "--cypher", help="Treat query as Cypher instead of natural language"
        ),
    ] = False,
    format_type: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format")
    ] = OutputFormat.TEXT,
) -> None:
    """Query a codebase using natural language or Cypher."""

    try:
        sdk = CodebaseSDK()
        query_type = QueryType.CYPHER if cypher else QueryType.NATURAL_LANGUAGE
        result = asyncio.run(sdk.query_codebase(graph_id, query_text, query_type))
        output_result(result, format_type)
    except CodebaseNotFoundError as e:
        error_result = ErrorResult(error_message=str(e))
        output_result(error_result, format_type)
        raise typer.Exit(1) from e

    except Exception as e:
        error_result = ErrorResult(
            error_message=f"Error executing query: {e}",
            details=f"Full traceback:\n{traceback.format_exc()}",
        )
        output_result(error_result, format_type)
        raise typer.Exit(1) from e


@app.command()
def reindex(
    graph_id: Annotated[str, typer.Argument(help="Graph ID to reindex")],
    format_type: Annotated[
        OutputFormat, typer.Option("--format", "-f", help="Output format")
    ] = OutputFormat.TEXT,
) -> None:
    """Reindex an existing codebase."""

    try:
        sdk = CodebaseSDK()
        result = asyncio.run(sdk.reindex_codebase(graph_id))
        # Stats are always shown now that verbose is controlled by env var
        output_result(result, format_type)
    except CodebaseNotFoundError as e:
        error_result = ErrorResult(error_message=str(e))
        output_result(error_result, format_type)
        raise typer.Exit(1) from e

    except Exception as e:
        error_result = ErrorResult(
            error_message=f"Error reindexing codebase: {e}",
            details=f"Full traceback:\n{traceback.format_exc()}",
        )
        output_result(error_result, format_type)
        raise typer.Exit(1) from e
