"""Pydantic models and exceptions for Cypher query generation."""

from typing import Any

from pydantic import BaseModel, Field


class CypherGenerationResponse(BaseModel):
    """Structured response from LLM for Cypher query generation.

    This model ensures the LLM explicitly indicates whether it can generate
    a valid Cypher query and provides a reason if it cannot.
    """

    cypher_query: str | None = Field(
        default=None,
        description="The generated Cypher query, or None if generation not possible",
    )
    can_generate_valid_cypher: bool = Field(
        description="Whether a valid Cypher query can be generated for this request"
    )
    reason_cannot_generate: str | None = Field(
        default=None,
        description="Explanation why query cannot be generated (if applicable)",
    )

    def model_post_init(self, __context: Any) -> None:
        """Validate that reason is provided when query cannot be generated."""
        if not self.can_generate_valid_cypher and not self.reason_cannot_generate:
            self.reason_cannot_generate = "No reason provided"
        if self.can_generate_valid_cypher and not self.cypher_query:
            raise ValueError(
                "cypher_query must be provided when can_generate_valid_cypher is True"
            )


class CypherGenerationNotPossibleError(Exception):
    """Raised when LLM cannot generate valid Cypher for the query.

    This typically happens when the query is conceptual rather than structural,
    or when it requires interpretation beyond what can be expressed in Cypher.
    """

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Cannot generate Cypher query: {reason}")
