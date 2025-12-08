"""
Plan Storage Layer for Router Agent.

Handles loading and saving execution plans to .shotgun/execution_plan.json.
"""

import json
import logging
import os

import aiofiles

from shotgun.utils.file_system_utils import get_shotgun_base_path

from .models import ExecutionPlan

logger = logging.getLogger(__name__)

PLAN_FILE_NAME = "execution_plan.json"


def _get_plan_file_path() -> str:
    """Get the full path to the execution plan file."""
    return str(get_shotgun_base_path() / PLAN_FILE_NAME)


async def load_plan() -> ExecutionPlan | None:
    """Load the execution plan from disk.

    Returns:
        ExecutionPlan if file exists and is valid, None otherwise.
    """
    plan_path = _get_plan_file_path()

    try:
        async with aiofiles.open(plan_path) as f:
            content = await f.read()
            data = json.loads(content)
            return ExecutionPlan.model_validate(data)
    except FileNotFoundError:
        logger.debug("No execution plan found at %s", plan_path)
        return None
    except json.JSONDecodeError as e:
        logger.warning("Invalid JSON in execution plan file: %s", e)
        return None
    except Exception as e:
        logger.warning("Failed to load execution plan: %s", e)
        return None


async def save_plan(plan: ExecutionPlan) -> None:
    """Save the execution plan to disk.

    Args:
        plan: The execution plan to save.
    """
    plan_path = _get_plan_file_path()

    # Ensure .shotgun directory exists
    base_path = get_shotgun_base_path()
    base_path.mkdir(exist_ok=True)

    try:
        async with aiofiles.open(plan_path, "w") as f:
            content = plan.model_dump_json(indent=2)
            await f.write(content)
        logger.debug("Saved execution plan to %s", plan_path)
    except Exception as e:
        logger.error("Failed to save execution plan: %s", e)
        raise


async def delete_plan() -> bool:
    """Delete the execution plan file if it exists.

    Returns:
        True if file was deleted, False if it didn't exist.
    """
    plan_path = _get_plan_file_path()

    try:
        os.remove(plan_path)
        logger.debug("Deleted execution plan at %s", plan_path)
        return True
    except FileNotFoundError:
        return False
    except Exception as e:
        logger.error("Failed to delete execution plan: %s", e)
        raise
