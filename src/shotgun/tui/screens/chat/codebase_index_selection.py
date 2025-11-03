"""Codebase indexing selection models."""

from pathlib import Path

from pydantic import BaseModel


class CodebaseIndexSelection(BaseModel):
    """User-selected repository path and name for indexing."""

    repo_path: Path
    name: str
