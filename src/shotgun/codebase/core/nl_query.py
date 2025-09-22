"""Natural language to Cypher query conversion for code graphs."""

import time
from datetime import datetime
from typing import TYPE_CHECKING

from pydantic_ai.messages import (
    ModelRequest,
    SystemPromptPart,
    TextPart,
    UserPromptPart,
)

from shotgun.agents.config import get_provider_model
from shotgun.agents.config.models import shotgun_model_request
from shotgun.logging_config import get_logger
from shotgun.prompts import PromptLoader

if TYPE_CHECKING:
    from openai import AsyncOpenAI

logger = get_logger(__name__)

# Global prompt loader instance
prompt_loader = PromptLoader()


async def llm_cypher_prompt(system_prompt: str, user_prompt: str) -> str:
    """Generate a Cypher query from a natural language prompt using the configured LLM provider.

    Args:
        system_prompt: The system prompt defining the behavior and context for the LLM
        user_prompt: The user's natural language query
    Returns:
        The generated Cypher query as a string
    """
    model_config = get_provider_model()
    # Use shotgun wrapper to maximize response quality for codebase queries
    query_cypher_response = await shotgun_model_request(
        model_config=model_config,
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
        natural_language_query: The user's query in natural language

    Returns:
        Generated Cypher query
    """
    # Get current time for context
    current_timestamp = int(time.time())
    current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Generate system prompt using template
    system_prompt = prompt_loader.render("codebase/cypher_system.j2")

    # Generate enhanced query using template
    enhanced_query = prompt_loader.render(
        "codebase/enhanced_query_context.j2",
        current_datetime=current_datetime,
        current_timestamp=current_timestamp,
        natural_language_query=natural_language_query,
    )

    try:
        cypher_query = await llm_cypher_prompt(system_prompt, enhanced_query)
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
        natural_language_query: The user's query in natural language
        error_context: Additional context about previous errors to help generate better query

    Returns:
        Generated Cypher query
    """
    # Get current time for context
    current_timestamp = int(time.time())
    current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Generate enhanced query with error context using template
    enhanced_query = prompt_loader.render_string(
        """Current datetime: {{ current_datetime }} (Unix timestamp: {{ current_timestamp }})

User query: {{ natural_language_query }}

ERROR CONTEXT (CRITICAL - Previous attempt failed):
{{ error_context }}

IMPORTANT: All timestamps in the database are stored as Unix timestamps (INT64). When generating time-based queries:
- For "2 minutes ago": use {{ current_timestamp - 120 }}
- For "1 hour ago": use {{ current_timestamp - 3600 }}
- For "today": use timestamps >= {{ current_timestamp - (current_timestamp % 86400) }}
- For "yesterday": use timestamps between {{ current_timestamp - 86400 - (current_timestamp % 86400) }} and {{ current_timestamp - (current_timestamp % 86400) }}
- NEVER use placeholder values like 1704067200, always calculate based on the current timestamp: {{ current_timestamp }}""",
        current_datetime=current_datetime,
        current_timestamp=current_timestamp,
        natural_language_query=natural_language_query,
        error_context=error_context,
    )

    try:
        # Create enhanced system prompt with error recovery instructions
        enhanced_system_prompt = prompt_loader.render_string(
            """{{ base_system_prompt }}

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
```""",
            base_system_prompt=prompt_loader.render("codebase/cypher_system.j2"),
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

    # Generate system prompt using template
    system_prompt = prompt_loader.render("codebase/cypher_system.j2")

    # Generate enhanced query using template
    enhanced_query = prompt_loader.render(
        "codebase/enhanced_query_context.j2",
        current_datetime=current_datetime,
        current_timestamp=current_timestamp,
        natural_language_query=natural_language_query,
    )

    try:
        cypher_query = await llm_cypher_prompt(system_prompt, enhanced_query)
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
