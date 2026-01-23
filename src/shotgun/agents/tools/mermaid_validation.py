"""Mermaid diagram validation tool for Pydantic AI agents.

This tool allows agents to validate mermaid diagram syntax before writing
files that contain mermaid diagrams, ensuring they render correctly.
"""

import os
import re

import httpx
from pydantic import BaseModel
from pydantic_ai import RunContext

from shotgun.agents.models import AgentDeps
from shotgun.agents.tools.registry import ToolCategory, register_tool
from shotgun.logging_config import get_logger

logger = get_logger(__name__)

# API configuration
MERMAID_API_URL = os.environ.get("MERMAID_API_URL", "http://localhost:8080")
MERMAID_API_TIMEOUT = float(os.environ.get("MERMAID_API_TIMEOUT", "30"))

# Shotgun identification for API requests
SHOTGUN_INSTANCE_ID = os.environ.get(
    "SHOTGUN_INSTANCE_ID", "550e8400-e29b-41d4-a716-446655440000"
)
SHOTGUN_VERSION = os.environ.get("SHOTGUN_VERSION", "0.3.0")


class MermaidValidationResult(BaseModel):
    """Result of mermaid diagram validation."""

    valid: bool
    diagram_type: str | None = None
    error_message: str | None = None
    error_line: int | None = None


class MermaidBatchResult(BaseModel):
    """Result of batch mermaid validation."""

    total: int
    valid_count: int
    invalid_count: int
    results: list[MermaidValidationResult]

    @property
    def all_valid(self) -> bool:
        return self.invalid_count == 0


async def _call_validation_api(diagram: str) -> MermaidValidationResult:
    """Call the mermaid validation API for a single diagram."""
    async with httpx.AsyncClient(timeout=MERMAID_API_TIMEOUT) as client:
        try:
            response = await client.post(
                f"{MERMAID_API_URL}/validate",
                json={
                    "shotgun_instance_id": SHOTGUN_INSTANCE_ID,
                    "shotgun_version": SHOTGUN_VERSION,
                    "diagram": diagram,
                },
            )
            response.raise_for_status()
            data = response.json()

            if data.get("valid"):
                return MermaidValidationResult(
                    valid=True,
                    diagram_type=data.get("diagramType"),
                )
            else:
                error = data.get("error", {})
                return MermaidValidationResult(
                    valid=False,
                    error_message=error.get("message"),
                    error_line=error.get("line"),
                )

        except httpx.TimeoutException:
            return MermaidValidationResult(
                valid=False,
                error_message="Validation API request timed out",
            )
        except httpx.RequestError as e:
            return MermaidValidationResult(
                valid=False,
                error_message=f"Validation API request failed: {e}",
            )
        except Exception as e:
            return MermaidValidationResult(
                valid=False,
                error_message=f"Unexpected error during validation: {e}",
            )


async def _call_batch_validation_api(
    diagrams: list[dict[str, str]],
) -> list[MermaidValidationResult]:
    """Call the mermaid validation API for multiple diagrams."""
    async with httpx.AsyncClient(timeout=MERMAID_API_TIMEOUT) as client:
        try:
            response = await client.post(
                f"{MERMAID_API_URL}/validate/batch",
                json={
                    "shotgun_instance_id": SHOTGUN_INSTANCE_ID,
                    "shotgun_version": SHOTGUN_VERSION,
                    "diagrams": diagrams,
                },
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for item in data.get("results", []):
                if item.get("valid"):
                    results.append(
                        MermaidValidationResult(
                            valid=True,
                            diagram_type=item.get("diagramType"),
                        )
                    )
                else:
                    error = item.get("error", {})
                    results.append(
                        MermaidValidationResult(
                            valid=False,
                            error_message=error.get("message"),
                            error_line=error.get("line"),
                        )
                    )
            return results

        except httpx.TimeoutException:
            return [
                MermaidValidationResult(
                    valid=False,
                    error_message="Validation API request timed out",
                )
                for _ in diagrams
            ]
        except httpx.RequestError as e:
            return [
                MermaidValidationResult(
                    valid=False,
                    error_message=f"Validation API request failed: {e}",
                )
                for _ in diagrams
            ]
        except Exception as e:
            return [
                MermaidValidationResult(
                    valid=False,
                    error_message=f"Unexpected error during validation: {e}",
                )
                for _ in diagrams
            ]


# Pattern to extract mermaid code blocks from markdown
MERMAID_BLOCK_PATTERN = re.compile(
    r"```\s*mermaid\s*\n(.*?)```",
    re.DOTALL | re.IGNORECASE,
)


def extract_mermaid_diagrams(content: str) -> list[tuple[str, int, int]]:
    """Extract mermaid diagrams from markdown content.

    Returns:
        List of tuples: (diagram_content, start_line, end_line)
    """
    diagrams = []
    for match in MERMAID_BLOCK_PATTERN.finditer(content):
        diagram = match.group(1).strip()
        start_line = content[: match.start()].count("\n") + 1
        end_line = content[: match.end()].count("\n") + 1
        diagrams.append((diagram, start_line, end_line))
    return diagrams


@register_tool(
    category=ToolCategory.ARTIFACT_MANAGEMENT,
    display_text="Validating mermaid",
    key_arg="diagram",
)
async def validate_mermaid(
    ctx: RunContext[AgentDeps],
    diagram: str,
) -> str:
    """Validate a mermaid diagram's syntax before using it.

    Use this tool to check if a mermaid diagram is syntactically correct
    before including it in a document. This helps catch errors early and
    ensures diagrams will render properly.

    Args:
        diagram: The mermaid diagram code to validate (without the ```mermaid wrapper)

    Returns:
        Validation result with diagram type if valid, or error details if invalid.

    Example:
        validate_mermaid("flowchart TD\\n    A[Start] --> B[End]")
        # Returns: "✅ Valid mermaid diagram (type: flowchart-v2)"

        validate_mermaid("flowchart TD\\n    INVALID SYNTAX")
        # Returns: "❌ Invalid mermaid diagram: Parse error on line 2..."
    """
    logger.debug("🔍 Validating mermaid diagram (%d chars)", len(diagram))

    result = await _call_validation_api(diagram)

    if result.valid:
        msg = f"✅ Valid mermaid diagram (type: {result.diagram_type})"
        logger.debug(msg)
        return msg
    else:
        error_location = f" on line {result.error_line}" if result.error_line else ""
        msg = f"❌ Invalid mermaid diagram{error_location}: {result.error_message}"
        logger.debug(msg)
        return msg


@register_tool(
    category=ToolCategory.ARTIFACT_MANAGEMENT,
    display_text="Validating mermaid in content",
    key_arg="content",
)
async def validate_mermaid_in_content(
    ctx: RunContext[AgentDeps],
    content: str,
) -> str:
    """Validate all mermaid diagrams in markdown content.

    Use this tool to check all mermaid code blocks in a markdown document
    before writing it to a file. This ensures all diagrams will render properly.

    Args:
        content: Markdown content that may contain mermaid code blocks

    Returns:
        Summary of validation results for all diagrams found.

    Example:
        validate_mermaid_in_content("# Doc\\n```mermaid\\nflowchart TD\\n    A --> B\\n```")
        # Returns: "Found 1 mermaid diagram(s). All valid! ✅"
    """
    diagrams = extract_mermaid_diagrams(content)

    if not diagrams:
        return "No mermaid diagrams found in content."

    logger.debug("🔍 Validating %d mermaid diagram(s)", len(diagrams))

    # Prepare batch request
    batch_input = [{"id": str(i), "diagram": d[0]} for i, d in enumerate(diagrams)]
    results = await _call_batch_validation_api(batch_input)

    # Build response
    lines = [f"Found {len(diagrams)} mermaid diagram(s):"]

    all_valid = True
    for i, (result, (_, start_line, end_line)) in enumerate(
        zip(results, diagrams, strict=True)
    ):
        if result.valid:
            lines.append(
                f"  ✅ Diagram {i + 1} (lines {start_line}-{end_line}): {result.diagram_type}"
            )
        else:
            all_valid = False
            error_preview = (result.error_message or "Unknown error")[:80]
            lines.append(
                f"  ❌ Diagram {i + 1} (lines {start_line}-{end_line}): {error_preview}"
            )

    if all_valid:
        lines.append("\nAll diagrams are valid! ✅")
    else:
        invalid_count = sum(1 for r in results if not r.valid)
        lines.append(
            f"\n{invalid_count} diagram(s) have errors. Please fix before writing."
        )

    return "\n".join(lines)
