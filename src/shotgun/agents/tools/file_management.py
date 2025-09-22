"""File management tools for Pydantic AI agents.

These tools are restricted to the .shotgun directory for security.
"""

from pathlib import Path
from typing import Literal

from pydantic_ai import RunContext

from shotgun.agents.models import AgentDeps, FileOperationType
from shotgun.logging_config import get_logger
from shotgun.utils.file_system_utils import get_shotgun_base_path

logger = get_logger(__name__)


def _validate_shotgun_path(filename: str) -> Path:
    """Validate and resolve a file path within the .shotgun directory.

    Args:
        filename: Relative filename within .shotgun directory

    Returns:
        Absolute path to the file within .shotgun directory

    Raises:
        ValueError: If the path attempts to access files outside .shotgun directory
    """
    base_path = get_shotgun_base_path()

    # Create the full path
    full_path = (base_path / filename).resolve()

    # Ensure the resolved path is within the .shotgun directory
    try:
        full_path.relative_to(base_path.resolve())
    except ValueError as e:
        raise ValueError(
            f"Access denied: Path '{filename}' is outside .shotgun directory"
        ) from e

    return full_path


async def read_file(ctx: RunContext[AgentDeps], filename: str) -> str:
    """Read a file from the .shotgun directory.

    Args:
        filename: Relative path to file within .shotgun directory

    Returns:
        File contents as string

    Raises:
        ValueError: If path is outside .shotgun directory
        FileNotFoundError: If file does not exist
    """
    logger.debug("🔧 Reading file: %s", filename)

    try:
        file_path = _validate_shotgun_path(filename)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {filename}")

        content = file_path.read_text(encoding="utf-8")
        logger.debug("📄 Read %d characters from %s", len(content), filename)
        return content

    except Exception as e:
        error_msg = f"Error reading file '{filename}': {str(e)}"
        logger.error("❌ File read failed: %s", error_msg)
        return error_msg


async def write_file(
    ctx: RunContext[AgentDeps],
    filename: str,
    content: str,
    mode: Literal["w", "a"] = "w",
) -> str:
    """Write content to a file in the .shotgun directory.

    Args:
        filename: Relative path to file within .shotgun directory
        content: Content to write to the file
        mode: Write mode - 'w' for overwrite, 'a' for append

    Returns:
        Success message or error message

    Raises:
        ValueError: If path is outside .shotgun directory or invalid mode
    """
    logger.debug("🔧 Writing file: %s (mode: %s)", filename, mode)

    if mode not in ["w", "a"]:
        raise ValueError(f"Invalid mode '{mode}'. Use 'w' for write or 'a' for append")

    try:
        file_path = _validate_shotgun_path(filename)

        # Determine operation type
        if mode == "a":
            operation = FileOperationType.UPDATED
        else:
            operation = (
                FileOperationType.CREATED
                if not file_path.exists()
                else FileOperationType.UPDATED
            )

        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write content
        if mode == "a":
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(content)
            logger.debug("📄 Appended %d characters to %s", len(content), filename)
            result = f"Successfully appended {len(content)} characters to {filename}"
        else:
            file_path.write_text(content, encoding="utf-8")
            logger.debug("📄 Wrote %d characters to %s", len(content), filename)
            result = f"Successfully wrote {len(content)} characters to {filename}"

        # Track the file operation
        ctx.deps.file_tracker.add_operation(file_path, operation)

        return result

    except Exception as e:
        error_msg = f"Error writing file '{filename}': {str(e)}"
        logger.error("❌ File write failed: %s", error_msg)
        return error_msg


async def append_file(ctx: RunContext[AgentDeps], filename: str, content: str) -> str:
    """Append content to a file in the .shotgun directory.

    Args:
        filename: Relative path to file within .shotgun directory
        content: Content to append to the file

    Returns:
        Success message or error message
    """
    return await write_file(ctx, filename, content, mode="a")
