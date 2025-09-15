"""Natural language to Cypher query conversion for code graphs."""

import time
from datetime import datetime
from typing import TYPE_CHECKING

from pydantic_ai.direct import model_request
from pydantic_ai.messages import (
    ModelRequest,
    SystemPromptPart,
    TextPart,
    UserPromptPart,
)

from shotgun.agents.config import get_provider_model
from shotgun.logging_config import setup_logger

if TYPE_CHECKING:
    from openai import AsyncOpenAI

logger = setup_logger(__name__)


# Graph schema and Cypher generation prompt
GRAPH_SCHEMA_AND_RULES = """
You are an expert AI assistant for a system that uses a Neo4j graph database.

**1. Graph Schema Definition**
The database contains information about a codebase, structured with the following nodes and relationships.

Node Labels and Their Key Properties:
- Project: {name: string}
- Package: {qualified_name: string, name: string, path: string}
- Folder: {path: string, name: string}
- File: {path: string, name: string, extension: string}  // Note: extension includes the dot (e.g., ".ts", ".py", ".js")
- FileMetadata: {filepath: string, mtime: int64, hash: string, last_updated: int64}
- Module: {qualified_name: string, name: string, path: string, created_at: int64, updated_at: int64}
- Class: {qualified_name: string, name: string, decorators: list[string], line_start: int, line_end: int, created_at: int64, updated_at: int64}
- Function: {qualified_name: string, name: string, decorators: list[string], line_start: int, line_end: int, created_at: int64, updated_at: int64}
- Method: {qualified_name: string, name: string, decorators: list[string], line_start: int, line_end: int, created_at: int64, updated_at: int64}
- ExternalPackage: {name: string, version_spec: string}
- DeletionLog: {id: string, entity_type: string, entity_qualified_name: string, deleted_from_file: string, deleted_at: int64, deletion_reason: string}

Relationships (source)-[REL_TYPE]->(target):
- (Project|Package|Folder) -[:CONTAINS_PACKAGE|CONTAINS_FOLDER|CONTAINS_FILE|CONTAINS_MODULE]-> (various)
- Module -[:DEFINES]-> (Class|Function)
- Class -[:DEFINES_METHOD]-> Method
- (Child Class) -[:INHERITS]-> (Parent Class)
- Method -[:OVERRIDES]-> Method
- Project -[:DEPENDS_ON_EXTERNAL]-> ExternalPackage
- (Function|Method) -[:CALLS]-> (Function|Method)
- FileMetadata -[:TRACKS_Module]-> Module
- FileMetadata -[:TRACKS_Class]-> Class
- FileMetadata -[:TRACKS_Function]-> Function
- FileMetadata -[:TRACKS_Method]-> Method

**2. Critical Cypher Query Rules**

- **ALWAYS Return Specific Properties with Aliases**: Do NOT return whole nodes (e.g., `RETURN n`). You MUST return specific properties with clear aliases (e.g., `RETURN n.name AS name`).
- **File Extensions Include Dots**: File extensions are stored WITH the leading dot (e.g., `.ts`, `.py`, `.js`). When querying for files by extension, ALWAYS include the dot: `WHERE f.extension = '.ts'` NOT `WHERE f.extension = 'ts'`.
- **Use `STARTS WITH` for Paths**: When matching paths, always use `STARTS WITH` for robustness (e.g., `WHERE n.path STARTS WITH 'workflows/src'`). Do not use `=`.
- **Use `toLower()` for Searches**: For case-insensitive searching on string properties, use `toLower()`.
- **Querying Lists**: To check if a list property (like `decorators`) contains an item, use the `ANY` or `IN` clause (e.g., `WHERE 'flow' IN n.decorators`).
- **No Union Types in Patterns**: Kuzu does NOT support union types like `(n:Function|Method)`. Use separate MATCH clauses or OPTIONAL MATCH instead.
- **Timestamps in Kuzu**: Timestamps are stored as INT64 Unix timestamps (seconds since epoch). Do NOT use `timestamp()` function. For time-based queries, use numeric comparisons with Unix timestamp values that are calculated from the current timestamp provided in the user query. NEVER use hardcoded timestamps like 1704067200.
- **No labels() Function**: Kuzu does NOT support the `labels()` function. Do not use `labels(n)` in queries. If you need to indicate the type, use a string literal like 'Class' or 'Function'.
- **CASE Statements**: Kuzu has limited support for CASE statements. AVOID using CASE WHEN in RETURN clauses. Instead, use string literals for type indication or UNION ALL for handling multiple node types.
- **UNION ALL Column Matching**: When using UNION ALL, EVERY part MUST return the EXACT SAME columns with the SAME names in the SAME order.
  CORRECT usage:
  ```
  MATCH (f:Function) WHERE ... RETURN f.name AS name, f.qualified_name AS qname, 'Function' AS type
  UNION ALL
  MATCH (m:Method) WHERE ... RETURN m.name AS name, m.qualified_name AS qname, 'Method' AS type
  ```
  INCORRECT usage (different column counts or names):
  ```
  MATCH (f:Function) RETURN f.name AS name, f.qualified_name AS qname
  UNION ALL
  MATCH (m:Method) RETURN m.name AS name, m.qualified_name AS qname, m.path AS path  // ERROR: Extra column!
  ```
"""

CYPHER_SYSTEM_PROMPT = f"""
You are an expert translator that converts natural language questions about code structure into precise Neo4j Cypher queries.

{GRAPH_SCHEMA_AND_RULES}

**3. Query Patterns & Examples**
Your goal is to return appropriate properties for each node type. Common properties:
- All nodes have: `name`
- Nodes with paths: Module, Package, File, Folder (have `path` property)
- Code entities: Class, Function, Method (have `qualified_name` but NO `path` - get path via Module relationship)
- Always include a type indicator (either as a string literal or via CASE statement)
- Do NOT include comments (// or /*) in your queries.

**IMPORTANT: Handling Entity Names**
- `name` property: Contains only the simple/short name (e.g., 'WebSocketServer', 'start')
- `qualified_name` property: Contains the full qualified path (e.g., 'shotgun2.server.src.shotgun.api.websocket.server.WebSocketServer')
- When users mention a specific class/function/method by name:
  - If it looks like a short name, use: `WHERE c.name = 'WebSocketServer'`
  - If it contains dots or looks like a full path, use: `WHERE c.qualified_name = 'full.path.to.Class'`
  - For partial paths, use: `WHERE c.qualified_name CONTAINS 'partial.path'` or `WHERE c.qualified_name ENDS WITH '.WebSocketServer'`

**Pattern: Finding All Classes**
```cypher
// "Find all Python classes" or "list all classes" or "show me all classes"
MATCH (c:Class)
RETURN c.name AS name, c.qualified_name AS qualified_name, 'Class' AS type
ORDER BY c.name
```

**Pattern: Finding Classes with Path Information**
```cypher
// "Find Python classes with their file paths" or "show classes and where they are defined"
MATCH (m:Module)-[:DEFINES]->(c:Class)
RETURN c.name AS name, c.qualified_name AS qualified_name, m.path AS module_path, 'Class' AS type
ORDER BY m.path, c.name
```

**Pattern: Finding Decorated Functions/Methods (e.g., Workflows, Tasks)**
```cypher
// "Find all prefect flows" or "what are the workflows?" or "show me the tasks"
// Use separate MATCH clauses since Kuzu doesn't support union types
MATCH (n:Function)
WHERE ANY(d IN n.decorators WHERE toLower(d) IN ['flow', 'task'])
RETURN n.name AS name, n.qualified_name AS qualified_name, 'Function' AS type
UNION ALL
MATCH (n:Method)
WHERE ANY(d IN n.decorators WHERE toLower(d) IN ['flow', 'task'])
RETURN n.name AS name, n.qualified_name AS qualified_name, 'Method' AS type
```

**Pattern: Finding Content by Path (Using UNION ALL for Different Types)**
```cypher
// "what is in the 'workflows/src' directory?" or "list files in workflows"
// Use separate queries with UNION ALL to handle different node types
MATCH (n:Module)
WHERE n.path STARTS WITH 'workflows'
RETURN n.name AS name, n.path AS path, 'Module' AS type
UNION ALL
MATCH (n:File)
WHERE n.path STARTS WITH 'workflows'
RETURN n.name AS name, n.path AS path, 'File' AS type
UNION ALL
MATCH (n:Folder)
WHERE n.path STARTS WITH 'workflows'
RETURN n.name AS name, n.path AS path, 'Folder' AS type
```

**Pattern: Keyword & Concept Search (Fallback for general terms)**
```cypher
// "find things related to 'database'"
MATCH (n)
WHERE toLower(n.name) CONTAINS 'database' OR (n.qualified_name IS NOT NULL AND toLower(n.qualified_name) CONTAINS 'database')
```

**Pattern: Time-based Queries (IMPORTANT: Use actual timestamps from user query)**
```cypher
// "What functions were added in the last 2 minutes?" when current timestamp is 1736255520
MATCH (f:Function)
WHERE f.created_at > 1736255400  // This is 1736255520 - 120
RETURN f.name AS name, f.qualified_name AS qualified_name, f.created_at AS created_timestamp
ORDER BY f.created_at DESC
```

```cypher
// "What classes were modified today?" when current timestamp is 1736255520
MATCH (c:Class)
WHERE c.updated_at >= 1736208000  // This is today's start (1736255520 - (1736255520 % 86400))
RETURN c.name AS name, c.qualified_name AS qualified_name, c.updated_at AS updated_timestamp
ORDER BY c.updated_at DESC
```

**Pattern: Finding Files by Extension**
```cypher
// "Find all TypeScript files" or "show me .ts files"
// IMPORTANT: File extensions are stored WITH the dot (e.g., ".ts" not "ts")
MATCH (f:File)
WHERE f.extension = '.ts'
RETURN f.path AS path, f.name AS name, f.extension AS extension, 'File' AS type
ORDER BY f.path
```

```cypher
// "Find JavaScript and TypeScript files"
MATCH (f:File)
WHERE f.extension IN ['.js', '.ts', '.jsx', '.tsx']
RETURN f.path AS path, f.name AS name, f.extension AS extension, 'File' AS type
ORDER BY f.path
```

**Pattern: Finding a Specific File**
```cypher
// "Find the main README.md"
MATCH (f:File) WHERE toLower(f.name) = 'readme.md' AND f.path = 'README.md'
RETURN f.path as path, f.name as name, 'File' as type
```

**Pattern: Finding Classes in a Specific Directory**
```cypher
// "Find classes in the server directory"
MATCH (m:Module)-[:DEFINES]->(c:Class)
WHERE m.path STARTS WITH 'server/'
RETURN c.name AS name, c.qualified_name AS qualified_name, 'Class' AS type
```

**Pattern: Finding Modules with Most Classes**
```cypher
// "Find modules that define the most classes"
MATCH (m:Module)-[:DEFINES]->(c:Class)
WITH m, count(c) AS class_count
ORDER BY class_count DESC
LIMIT 10
RETURN m.name AS name, m.qualified_name AS qualified_name, m.path AS path, class_count
```

**Pattern: Finding Classes with Method Counts**
```cypher
// "Find classes with more than N methods" or "Show me classes that have at least X methods"
MATCH (c:Class)-[:DEFINES_METHOD]->(m:Method)
WITH c, count(m) AS method_count
WHERE method_count > 10  // Replace 10 with the actual number from query
RETURN c.name AS name, c.qualified_name AS qualified_name, method_count
ORDER BY method_count DESC
```

**Pattern: Finding Classes with Inheritance (Note: INHERITS relationships must exist)**
```cypher
// "Find classes with children/subclasses"
// This will return NO results if no inheritance relationships exist in the graph
MATCH (child:Class)-[:INHERITS]->(parent:Class)
WITH parent, count(child) AS child_count
ORDER BY child_count DESC
LIMIT 10
RETURN parent.name AS name, parent.qualified_name AS qualified_name, child_count
```

**Pattern: Finding Parent Classes of a Specific Class**
```cypher
// "What are the parent classes of DeputyAgent?" or "What does DeputyAgent inherit from?"
// Use name for short class names (when user doesn't provide full path)
MATCH (child:Class)-[:INHERITS]->(parent:Class)
WHERE toLower(child.name) = 'deputyagent'
RETURN parent.name AS name, parent.qualified_name AS qualified_name
```

**Pattern: Finding Methods of a Specific Class**
```cypher
// "What methods does WebSocketServer have?" or "List methods in WebSocketServer class"
// When user provides just the class name without full path
MATCH (c:Class)-[:DEFINES_METHOD]->(m:Method)
WHERE c.name = 'WebSocketServer'
RETURN m.name AS name, m.qualified_name AS qualified_name, 'Method' AS type
ORDER BY m.name
```

**Pattern: Finding a Specific Entity by Full Qualified Name**
```cypher
// "Find shotgun.server.WebSocketServer" or "Show me api.websocket.server.WebSocketServer"
// When user provides a dotted path, match against qualified_name
MATCH (c:Class)
WHERE c.qualified_name = 'shotgun2.server.src.shotgun.api.websocket.server.WebSocketServer'
RETURN c.name AS name, c.qualified_name AS qualified_name, 'Class' AS type
```

**Pattern: Finding Recently Added/Modified Code**
```cypher
// "Find functions added in the last 24 hours" or "What new functions were added today?"
// Note: In Kuzu, use Unix timestamps directly (seconds since epoch)
// Example: 1704067200 represents 2024-01-01 00:00:00 UTC
// For "today": use timestamp from start of current day
// For "last 24 hours": use current_timestamp - 86400
MATCH (f:Function)
WHERE f.created_at > 1704067200  // Replace with actual timestamp for "24 hours ago"
RETURN f.name AS name, f.qualified_name AS qualified_name, f.created_at AS created_timestamp
ORDER BY f.created_at DESC
```

**Pattern: Finding Files Modified Recently**
```cypher
// "Find files modified today" or "Which files changed in the last hour?"
// For "last hour": use current_timestamp - 3600
// For "today": use timestamp from start of current day
MATCH (fm:FileMetadata)
WHERE fm.mtime > 1704067200  // Replace with actual timestamp
RETURN fm.filepath AS path, fm.mtime AS last_modified
ORDER BY fm.mtime DESC
```

**Pattern: Queries About Deleted/Removed Entities**
```cypher
// "What functions were deleted/removed?" or "Show me classes that no longer exist"
// Query the DeletionLog table for tracking removed entities
MATCH (d:DeletionLog)
WHERE d.entity_type = 'Function' AND d.deleted_at > 1704067200  // Replace with timestamp for time range
RETURN d.entity_qualified_name AS name, d.deleted_from_file AS file, d.deleted_at AS deleted_at, d.deletion_reason AS reason
ORDER BY d.deleted_at DESC
```

**Pattern: Finding Where a Method/Function is Called**
```cypher
// "where is WebSocketServer.start called?" or "find callers of method X"
// For partial names like 'WebSocketServer.start', use ENDS WITH pattern
MATCH (caller:Method)-[:CALLS]->(target:Method)
WHERE target.qualified_name ENDS WITH '.WebSocketServer.start'
RETURN caller.name AS name, caller.qualified_name AS qualified_name, 'Method' AS caller_type
UNION ALL
MATCH (caller:Function)-[:CALLS]->(target:Method)
WHERE target.qualified_name ENDS WITH '.WebSocketServer.start'
RETURN caller.name AS name, caller.qualified_name AS qualified_name, 'Function' AS caller_type
```

**Pattern: Finding What a Method/Function Calls**
```cypher
// "what does WebSocketServer.start call?" or "what methods does X invoke?"
// Use ENDS WITH for partial names, UNION ALL to handle different target types
MATCH (source:Method)-[:CALLS]->(target:Method)
WHERE source.qualified_name ENDS WITH '.WebSocketServer.start'
RETURN target.name AS name, target.qualified_name AS qualified_name, 'Method' AS target_type
UNION ALL
MATCH (source:Method)-[:CALLS]->(target:Function)
WHERE source.qualified_name ENDS WITH '.WebSocketServer.start'
RETURN target.name AS name, target.qualified_name AS qualified_name, 'Function' AS target_type
```

**4. Handling Time-based Queries**
When users ask about "today", "yesterday", "last hour", "last week", etc., convert these to Unix timestamp comparisons:
- "today" → Use a timestamp representing start of current day (e.g., WHERE f.created_at > 1704067200)
- "yesterday" → Use timestamps for yesterday's range
- "last hour" → Current time minus 3600 seconds
- "last 24 hours" → Current time minus 86400 seconds
- "last week" → Current time minus 604800 seconds

Since you cannot calculate the current time, use reasonable example timestamps that would work for the query.
The actual timestamp calculation will be handled by the calling application.

**5. Handling Queries About Deleted/Removed Entities**
When users ask about "removed", "deleted", or "no longer exist" entities:
- Query the DeletionLog table which tracks all deletions
- Filter by entity_type (Function, Method, Class, Module) based on what they're asking about
- Use timestamp comparisons for time-based deletion queries
- The deletion_reason field indicates why it was deleted (e.g., "removed_from_file", "file_deleted")

Examples:
- "What functions were removed today?" → Query DeletionLog WHERE entity_type = 'Function' AND deleted_at > [today's timestamp]
- "Show deleted classes from auth module" → Query DeletionLog WHERE entity_type = 'Class' AND entity_qualified_name CONTAINS 'auth'

**6. Output Format**
Provide only the Cypher query.
"""


async def llm_cypher_prompt(system_prompt: str, user_prompt: str) -> str:
    """Generate a Cypher query from a natural language prompt using the configured LLM provider.

    Args:
        system_prompt: The system prompt defining the behavior and context for the LLM
        user_prompt: The user's natural language query
    Returns:
        The generated Cypher query as a string
    """
    model_config = get_provider_model()
    query_cypher_response = await model_request(
        model=model_config.pydantic_model_name,
        messages=[
            ModelRequest(
                parts=[
                    SystemPromptPart(content=system_prompt),
                    UserPromptPart(content=user_prompt),
                ]
            ),
        ],
    )

    if not query_cypher_response.parts or not query_cypher_response.parts[0]:
        raise ValueError("Empty response from LLM")

    message_part = query_cypher_response.parts[0]
    if not isinstance(message_part, TextPart):
        raise ValueError("Unexpected response part type from LLM")
    cypher_query = str(message_part.content)
    if not cypher_query:
        raise ValueError("Empty content in LLM response")
    return cypher_query


async def generate_cypher(natural_language_query: str) -> str:
    """Convert a natural language query to Cypher using Shotgun's LLM client.

    Args:
        client: Shotgun LLM client instance
        natural_language_query: The user's query in natural language
        model_id: Optional specific model ID to use

    Returns:
        Generated Cypher query
    """
    # Get current time for context
    current_timestamp = int(time.time())
    current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Enhance query with temporal context
    enhanced_query = f"""Current datetime: {current_datetime} (Unix timestamp: {current_timestamp})

User query: {natural_language_query}

IMPORTANT: All timestamps in the database are stored as Unix timestamps (INT64). When generating time-based queries:
- For "2 minutes ago": use {current_timestamp - 120}
- For "1 hour ago": use {current_timestamp - 3600}
- For "today": use timestamps >= {current_timestamp - (current_timestamp % 86400)}
- For "yesterday": use timestamps between {current_timestamp - 86400 - (current_timestamp % 86400)} and {current_timestamp - (current_timestamp % 86400)}
- NEVER use placeholder values like 1704067200, always calculate based on the current timestamp: {current_timestamp}"""

    try:
        cypher_query = await llm_cypher_prompt(CYPHER_SYSTEM_PROMPT, enhanced_query)
        cleaned_query = clean_cypher_response(cypher_query)

        # Validate UNION ALL queries
        is_valid, validation_error = validate_union_query(cleaned_query)
        if not is_valid:
            logger.warning(f"Generated query failed validation: {validation_error}")
            logger.warning(f"Problematic query: {cleaned_query}")
            raise ValueError(f"Generated query validation failed: {validation_error}")

        return cleaned_query

    except Exception as e:
        raise RuntimeError(f"Failed to generate Cypher query: {e}") from e


async def generate_cypher_with_error_context(
    natural_language_query: str, error_context: str = ""
) -> str:
    """Convert a natural language query to Cypher with additional error context for retry scenarios.

    Args:
        client: Shotgun LLM client instance
        natural_language_query: The user's query in natural language
        model_id: Optional specific model ID to use
        error_context: Additional context about previous errors to help generate better query

    Returns:
        Generated Cypher query
    """
    # Get current time for context
    current_timestamp = int(time.time())
    current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Enhance query with temporal context and error context
    enhanced_query = f"""Current datetime: {current_datetime} (Unix timestamp: {current_timestamp})

User query: {natural_language_query}

ERROR CONTEXT (CRITICAL - Previous attempt failed):
{error_context}

IMPORTANT: All timestamps in the database are stored as Unix timestamps (INT64). When generating time-based queries:
- For "2 minutes ago": use {current_timestamp - 120}
- For "1 hour ago": use {current_timestamp - 3600}
- For "today": use timestamps >= {current_timestamp - (current_timestamp % 86400)}
- For "yesterday": use timestamps between {current_timestamp - 86400 - (current_timestamp % 86400)} and {current_timestamp - (current_timestamp % 86400)}
- NEVER use placeholder values like 1704067200, always calculate based on the current timestamp: {current_timestamp}"""

    try:
        # Create messages with enhanced system prompt that includes error recovery instructions
        enhanced_system_prompt = (
            CYPHER_SYSTEM_PROMPT
            + """

**CRITICAL ERROR RECOVERY INSTRUCTIONS:**
When retrying after a UNION ALL error:
1. Each UNION ALL branch MUST return exactly the same number of columns
2. Column names MUST be in the same order across all branches
3. Use explicit column aliases to ensure consistency: RETURN prop1 as name, prop2 as qualified_name, 'Type' as type
4. If different node types have different properties, use COALESCE or NULL for missing properties
5. Test each UNION branch separately before combining

Example of CORRECT UNION ALL:
```cypher
MATCH (c:Class) RETURN c.name as name, c.qualified_name as qualified_name, 'Class' as type
UNION ALL
MATCH (f:Function) RETURN f.name as name, f.qualified_name as qualified_name, 'Function' as type
```

Example of INCORRECT UNION ALL (different column counts):
```cypher
MATCH (c:Class) RETURN c.name, c.qualified_name, c.docstring
UNION ALL
MATCH (f:Function) RETURN f.name, f.qualified_name  // WRONG: missing third column
```"""
        )

        cypher_query = await llm_cypher_prompt(enhanced_system_prompt, enhanced_query)
        cleaned_query = clean_cypher_response(cypher_query)

        # Validate UNION ALL queries
        is_valid, validation_error = validate_union_query(cleaned_query)
        if not is_valid:
            logger.warning(f"Retry query failed validation: {validation_error}")
            logger.warning(f"Problematic retry query: {cleaned_query}")
            raise ValueError(f"Retry query validation failed: {validation_error}")

        return cleaned_query

    except Exception as e:
        raise RuntimeError(
            f"Failed to generate Cypher query with error context: {e}"
        ) from e


async def generate_cypher_openai_async(
    client: "AsyncOpenAI", natural_language_query: str, model: str = "gpt-4o"
) -> str:
    """Convert a natural language query to Cypher using async OpenAI client.

    This function is for standalone usage without Shotgun's LLM infrastructure.

    Args:
        client: Async OpenAI client instance
        natural_language_query: The user's query in natural language
        model: OpenAI model to use (default: gpt-4o)

    Returns:
        Generated Cypher query
    """
    # Get current time for context
    current_timestamp = int(time.time())
    current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Enhance query with temporal context
    enhanced_query = f"""Current datetime: {current_datetime} (Unix timestamp: {current_timestamp})

User query: {natural_language_query}

IMPORTANT: All timestamps in the database are stored as Unix timestamps (INT64). When generating time-based queries:
- For "2 minutes ago": use {current_timestamp - 120}
- For "1 hour ago": use {current_timestamp - 3600}
- For "today": use timestamps >= {current_timestamp - (current_timestamp % 86400)}
- For "yesterday": use timestamps between {current_timestamp - 86400 - (current_timestamp % 86400)} and {current_timestamp - (current_timestamp % 86400)}
- NEVER use placeholder values like 1704067200, always calculate based on the current timestamp: {current_timestamp}"""

    try:
        cypher_query = await llm_cypher_prompt(CYPHER_SYSTEM_PROMPT, enhanced_query)
        return clean_cypher_response(cypher_query)

    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        raise RuntimeError(f"Failed to generate Cypher query: {e}") from e


def validate_union_query(cypher_query: str) -> tuple[bool, str]:
    """Validate that UNION ALL queries have matching column counts and names.

    Args:
        cypher_query: The Cypher query to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    query_upper = cypher_query.upper()
    if "UNION ALL" not in query_upper:
        return True, ""

    # Split by UNION ALL and extract RETURN clauses
    parts = query_upper.split("UNION ALL")
    return_patterns = []

    for i, part in enumerate(parts):
        if "RETURN" not in part:
            continue

        # Extract the RETURN clause
        return_start = part.rfind("RETURN")
        return_clause = part[return_start + 6 :]  # Skip "RETURN "

        # Stop at ORDER BY, LIMIT, or end of query
        for stop_word in ["ORDER BY", "LIMIT", ";"]:
            if stop_word in return_clause:
                return_clause = return_clause.split(stop_word)[0]

        # Parse columns (basic parsing - split by comma and handle AS aliases)
        columns = []
        for col in return_clause.split(","):
            col = col.strip()
            if " AS " in col:
                # Extract the alias name after AS
                alias = col.split(" AS ")[-1].strip()
                columns.append(alias)
            else:
                # Use the column name as-is (simplified)
                columns.append(col.strip())

        return_patterns.append((i, columns))

    # Check all parts have same number of columns
    if len(return_patterns) < 2:
        return True, ""

    first_part, first_columns = return_patterns[0]
    first_count = len(first_columns)

    for part_idx, columns in return_patterns[1:]:
        if len(columns) != first_count:
            return (
                False,
                f"UNION ALL part {part_idx + 1} has {len(columns)} columns, expected {first_count}. First part columns: {first_columns}, this part: {columns}",
            )

    return True, ""


def clean_cypher_response(response_text: str) -> str:
    """Clean up common LLM formatting artifacts from a Cypher query.

    Args:
        response_text: Raw response from LLM

    Returns:
        Cleaned Cypher query
    """
    query = response_text.strip()

    # Remove markdown code blocks
    if query.startswith("```"):
        lines = query.split("\n")
        # Find the actual query content
        start_idx = 0
        end_idx = len(lines)

        for i, line in enumerate(lines):
            if line.startswith("```") and i == 0:
                start_idx = 1
            elif line.startswith("```") and i > 0:
                end_idx = i
                break

        query = "\n".join(lines[start_idx:end_idx])

    # Remove 'cypher' prefix if present
    query = query.strip()
    if query.lower().startswith("cypher"):
        query = query[6:].strip()

    # Remove backticks
    query = query.replace("`", "")

    # Ensure it ends with semicolon
    query = query.strip()
    if not query.endswith(";"):
        query += ";"

    return query
