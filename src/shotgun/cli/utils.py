"""Common utilities for CLI commands."""

import json
from typing import Any

from pydantic import BaseModel

from .models import OutputFormat


def format_result_json(result: Any) -> str:
    """Format result object as JSON using Pydantic serialization."""
    if isinstance(result, BaseModel):
        return result.model_dump_json(indent=2)
    else:
        # Fallback for non-Pydantic objects
        return json.dumps({"result": str(result)}, indent=2)


def output_result(result: Any, format_type: OutputFormat = OutputFormat.TEXT) -> None:
    """Output result in specified format."""
    if format_type == OutputFormat.JSON:
        print(format_result_json(result))
    else:  # Default to text
        print(str(result))
