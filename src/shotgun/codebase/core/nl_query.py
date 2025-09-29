"""Natural language to Cypher query conversion for code graphs."""

import time
from datetime import datetime
from typing import TYPE_CHECKING

from pydantic_ai import Agent

from shotgun.agents.config import get_provider_model
from shotgun.codebase.core.cypher_models import (
    CypherGenerationNotPossibleError,
    CypherGenerationResponse,
)
from shotgun.logging_config import get_logger
from shotgun.prompts import PromptLoader

if TYPE_CHECKING:
    from openai import AsyncOpenAI

logger = get_logger(__name__)

# Global prompt loader instance
prompt_loader = PromptLoader()


async def llm_cypher_prompt(
    system_prompt: str, user_prompt: str
) -> CypherGenerationResponse:
    """Generate a Cypher query from a natural language prompt using structured output.

    Args:
        system_prompt: The system prompt defining the behavior and context for the LLM
        user_prompt: The user's natural language query
    Returns:
        CypherGenerationResponse with cypher_query, can_generate flag, and reason if not
    """
    model_config = get_provider_model()

    # Create an agent with structured output for Cypher generation
    cypher_agent = Agent(
        model=model_config.model_instance,
        output_type=CypherGenerationResponse,
        retries=2,
    )

    # Combine system and user prompts
    combined_prompt = f"{system_prompt}\n\nUser Query: {user_prompt}"

    try:
        # Run the agent to get structured response
        result = await cypher_agent.run(combined_prompt)
        response = result.output

        # Log the structured response for debugging
        logger.debug(
            "Cypher generation response - can_generate: %s, query: %s, reason: %s",
            response.can_generate_valid_cypher,
            response.cypher_query[:50] if response.cypher_query else None,
            response.reason_cannot_generate,
        )

        return response

    except Exception as e:
        logger.error("Failed to generate Cypher query with structured output: %s", e)
        # Return a failure response
        return CypherGenerationResponse(
            cypher_query=None,
            can_generate_valid_cypher=False,
            reason_cannot_generate=f"LLM error: {str(e)}",
        )


async def generate_cypher(natural_language_query: str) -> str:
    """Convert a natural language query to Cypher using Shotgun's LLM client.

    Args:
        natural_language_query: The user's query in natural language

    Returns:
        Generated Cypher query

    Raises:
        CypherGenerationNotPossibleError: If the query cannot be converted to Cypher
        RuntimeError: If there's an error during generation
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
        response = await llm_cypher_prompt(system_prompt, enhanced_query)

        # Check if the LLM could generate a valid Cypher query
        if not response.can_generate_valid_cypher:
            logger.info(
                "Cannot generate Cypher for query '%s': %s",
                natural_language_query,
                response.reason_cannot_generate,
            )
            raise CypherGenerationNotPossibleError(
                response.reason_cannot_generate or "Query cannot be converted to Cypher"
            )

        if not response.cypher_query:
            raise ValueError("LLM indicated success but provided no query")

        cleaned_query = clean_cypher_response(response.cypher_query)

        # Validate Cypher keywords
        is_valid, validation_error = validate_cypher_keywords(cleaned_query)
        if not is_valid:
            logger.warning(f"Generated query has invalid syntax: {validation_error}")
            logger.warning(f"Problematic query: {cleaned_query}")
            raise ValueError(f"Generated query validation failed: {validation_error}")

        # Validate UNION ALL queries
        is_valid, validation_error = validate_union_query(cleaned_query)
        if not is_valid:
            logger.warning(f"Generated query failed validation: {validation_error}")
            logger.warning(f"Problematic query: {cleaned_query}")
            raise ValueError(f"Generated query validation failed: {validation_error}")

        return cleaned_query

    except CypherGenerationNotPossibleError:
        raise  # Re-raise as-is
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

        response = await llm_cypher_prompt(enhanced_system_prompt, enhanced_query)

        # Check if the LLM could generate a valid Cypher query
        if not response.can_generate_valid_cypher:
            logger.info(
                "Cannot generate Cypher for retry query '%s': %s",
                natural_language_query,
                response.reason_cannot_generate,
            )
            raise CypherGenerationNotPossibleError(
                response.reason_cannot_generate
                or "Query cannot be converted to Cypher even with error context"
            )

        if not response.cypher_query:
            raise ValueError("LLM indicated success but provided no query on retry")

        cleaned_query = clean_cypher_response(response.cypher_query)

        # Validate Cypher keywords
        is_valid, validation_error = validate_cypher_keywords(cleaned_query)
        if not is_valid:
            logger.warning(f"Generated query has invalid syntax: {validation_error}")
            logger.warning(f"Problematic query: {cleaned_query}")
            raise ValueError(f"Generated query validation failed: {validation_error}")

        # Validate UNION ALL queries
        is_valid, validation_error = validate_union_query(cleaned_query)
        if not is_valid:
            logger.warning(f"Retry query failed validation: {validation_error}")
            logger.warning(f"Problematic retry query: {cleaned_query}")
            raise ValueError(f"Retry query validation failed: {validation_error}")

        return cleaned_query

    except CypherGenerationNotPossibleError:
        raise  # Re-raise as-is
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

    Raises:
        CypherGenerationNotPossibleError: If the query cannot be converted to Cypher
        RuntimeError: If there's an error during generation
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
        response = await llm_cypher_prompt(system_prompt, enhanced_query)

        # Check if the LLM could generate a valid Cypher query
        if not response.can_generate_valid_cypher:
            logger.info(
                "Cannot generate Cypher for query '%s': %s",
                natural_language_query,
                response.reason_cannot_generate,
            )
            raise CypherGenerationNotPossibleError(
                response.reason_cannot_generate or "Query cannot be converted to Cypher"
            )

        if not response.cypher_query:
            raise ValueError("LLM indicated success but provided no query")

        return clean_cypher_response(response.cypher_query)

    except CypherGenerationNotPossibleError:
        raise  # Re-raise as-is
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


def validate_cypher_keywords(query: str) -> tuple[bool, str]:
    """Validate that a query starts with valid Kuzu Cypher keywords.

    Args:
        query: The Cypher query to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Valid Kuzu Cypher starting keywords based on parser expectations
    valid_cypher_keywords = {
        "ALTER",
        "ATTACH",
        "BEGIN",
        "CALL",
        "CHECKPOINT",
        "COMMENT",
        "COMMIT",
        "COPY",
        "CREATE",
        "DELETE",
        "DETACH",
        "DROP",
        "EXPLAIN",
        "EXPORT",
        "FORCE",
        "IMPORT",
        "INSTALL",
        "LOAD",
        "MATCH",
        "MERGE",
        "OPTIONAL",
        "PROFILE",
        "RETURN",
        "ROLLBACK",
        "SET",
        "UNWIND",
        "UNINSTALL",
        "UPDATE",
        "USE",
        "WITH",
    }

    query = query.strip()
    if not query:
        return False, "Empty query"

    # Get the first word
    first_word = query.upper().split()[0] if query else ""

    if first_word not in valid_cypher_keywords:
        return (
            False,
            f"Query doesn't start with valid Cypher keyword. Found: '{first_word}'",
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
