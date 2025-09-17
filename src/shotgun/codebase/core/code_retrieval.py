"""Code retrieval functionality for extracting source code from the knowledge graph."""

from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel

from shotgun.logging_config import get_logger

if TYPE_CHECKING:
    from shotgun.codebase.core.manager import CodebaseGraphManager

logger = get_logger(__name__)


class CodeSnippet(BaseModel):
    """Model for code snippet retrieval results."""

    qualified_name: str
    source_code: str
    file_path: str
    line_start: int
    line_end: int
    found: bool = True
    error_message: str | None = None
    docstring: str | None = None


async def retrieve_code_by_qualified_name(
    manager: "CodebaseGraphManager", graph_id: str, qualified_name: str
) -> CodeSnippet:
    """Retrieve code snippet by qualified name.

    Args:
        manager: CodebaseGraphManager instance
        graph_id: Graph ID to query
        qualified_name: Fully qualified name of the entity

    Returns:
        CodeSnippet with the retrieved code
    """
    logger.info(f"Retrieving code for: {qualified_name}")

    # Query to find the entity and its module
    # The relationships in Kuzu are:
    # - Module-[:DEFINES]->Class
    # - Module-[:DEFINES]->Function
    # - Class-[:DEFINES_METHOD]->Method
    # For methods, we need to traverse back to the module
    query = """
        MATCH (n)
        WHERE n.qualified_name = $qualified_name
        OPTIONAL MATCH (m:Module)-[:DEFINES]->(n)
        OPTIONAL MATCH (c:Class)-[:DEFINES_METHOD]->(n), (m2:Module)-[:DEFINES]->(c)
        RETURN
            n.name AS name,
            n.line_start AS start_line,
            n.line_end AS end_line,
            COALESCE(m.path, m2.path) AS path,
            COALESCE(n.docstring, NULL) AS docstring
        LIMIT 1
    """

    try:
        # Execute the query
        results = await manager._execute_query(
            graph_id, query, {"qualified_name": qualified_name}
        )

        if not results:
            return CodeSnippet(
                qualified_name=qualified_name,
                source_code="",
                file_path="",
                line_start=0,
                line_end=0,
                found=False,
                error_message=f"Entity '{qualified_name}' not found in graph.",
            )

        # Extract the first (and only) result
        result = results[0]
        file_path_str = result.get("path")
        start_line = result.get("start_line", 0)
        end_line = result.get("end_line", 0)
        docstring = result.get("docstring")

        # Check if we have all required location data
        if not all([file_path_str, start_line, end_line]):
            return CodeSnippet(
                qualified_name=qualified_name,
                source_code="",
                file_path=file_path_str or "",
                line_start=start_line or 0,
                line_end=end_line or 0,
                found=False,
                error_message="Graph entry is missing location data. The DEFINES relationship may be missing.",
            )

        # Get the repository path from the Project node
        repo_path_query = "MATCH (p:Project) RETURN p.repo_path LIMIT 1"
        repo_results = await manager._execute_query(graph_id, repo_path_query)

        if not repo_results or not repo_results[0].get("p.repo_path"):
            return CodeSnippet(
                qualified_name=qualified_name,
                source_code="",
                file_path=file_path_str or "",
                line_start=start_line,
                line_end=end_line,
                found=False,
                error_message="Repository path not found in graph.",
            )

        repo_path = Path(repo_results[0]["p.repo_path"])

        # Read the source code from the file
        if file_path_str is None:
            return CodeSnippet(
                qualified_name=qualified_name,
                source_code="",
                file_path="",
                line_start=start_line,
                line_end=end_line,
                found=False,
                error_message="File path is missing from graph data.",
            )

        full_path = repo_path / file_path_str

        if not full_path.exists():
            return CodeSnippet(
                qualified_name=qualified_name,
                source_code="",
                file_path=file_path_str,
                line_start=start_line,
                line_end=end_line,
                found=False,
                error_message=f"Source file not found: {full_path}",
            )

        # Read the file and extract the snippet
        try:
            with full_path.open("r", encoding="utf-8") as f:
                all_lines = f.readlines()

            # Extract the relevant lines (1-indexed to 0-indexed)
            snippet_lines = all_lines[start_line - 1 : end_line]
            source_code = "".join(snippet_lines)

            return CodeSnippet(
                qualified_name=qualified_name,
                source_code=source_code,
                file_path=file_path_str,
                line_start=start_line,
                line_end=end_line,
                docstring=docstring,
                found=True,
            )

        except Exception as e:
            logger.error(f"Error reading source file: {e}")
            return CodeSnippet(
                qualified_name=qualified_name,
                source_code="",
                file_path=file_path_str,
                line_start=start_line,
                line_end=end_line,
                found=False,
                error_message=f"Error reading source file: {str(e)}",
            )

    except Exception as e:
        logger.error(f"Error retrieving code: {e}", exc_info=True)
        return CodeSnippet(
            qualified_name=qualified_name,
            source_code="",
            file_path="",
            line_start=0,
            line_end=0,
            found=False,
            error_message=str(e),
        )


async def retrieve_code_by_cypher(
    manager: "CodebaseGraphManager", graph_id: str, cypher_query: str
) -> list[CodeSnippet]:
    """Retrieve code snippets for all entities matching a Cypher query.

    The query should return nodes with qualified_name property.

    Args:
        manager: CodebaseGraphManager instance
        graph_id: Graph ID to query
        cypher_query: Cypher query that returns entities

    Returns:
        List of CodeSnippet objects
    """
    logger.info(f"Retrieving code using Cypher query: {cypher_query}")

    try:
        # Execute the user's query
        results = await manager._execute_query(graph_id, cypher_query)

        if not results:
            logger.info("No results from Cypher query")
            return []

        # Extract qualified names from results
        qualified_names = set()
        for result in results:
            # Try different possible property names
            for key in [
                "qualified_name",
                "n.qualified_name",
                "c.qualified_name",
                "f.qualified_name",
                "m.qualified_name",
            ]:
                if key in result and result[key]:
                    qualified_names.add(result[key])
                    break

        if not qualified_names:
            logger.warning("Query results don't contain qualified_name properties")
            return []

        logger.info(f"Found {len(qualified_names)} entities to retrieve code for")

        # Retrieve code for each qualified name
        snippets = []
        for qn in qualified_names:
            snippet = await retrieve_code_by_qualified_name(manager, graph_id, qn)
            snippets.append(snippet)

        return snippets

    except Exception as e:
        logger.error(f"Error executing Cypher query: {e}", exc_info=True)
        # Return empty list on query error
        return []
