"""Codebase management CLI commands."""

import asyncio
import traceback
from pathlib import Path
from typing import Annotated

import typer

from shotgun.codebase.models import CodebaseGraph, QueryType
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
) -> None:
    """Index a new codebase."""
    sdk = CodebaseSDK()

    try:
        repo_path = Path(path)
        result = asyncio.run(sdk.index_codebase(repo_path, name))
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
