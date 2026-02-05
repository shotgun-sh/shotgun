"""Jinja2 prompt templates for Autopilot agent.

This module provides template loading and rendering for autopilot prompts.
"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

# Set up Jinja2 environment with the prompts directory
_PROMPTS_DIR = Path(__file__).parent
_env = Environment(
    loader=FileSystemLoader(_PROMPTS_DIR),
    trim_blocks=True,
    lstrip_blocks=True,
    autoescape=True,  # Safe for plain text, satisfies security linter
)


def render_execute_stage(
    tasks_file_path: str,
    stage_number: str | int,
    stage_name: str,
    pending_tasks: list[str],
    branch_name: str,
    base_branch: str,
) -> str:
    """Render the execute stage prompt.

    Args:
        tasks_file_path: Path to the tasks.md file.
        stage_number: The stage number.
        stage_name: The stage name.
        pending_tasks: List of pending task descriptions.
        branch_name: The branch name to create/checkout for this stage.
        base_branch: The base branch to create from.

    Returns:
        Rendered prompt string.
    """
    template = _env.get_template("execute_stage.j2")
    return template.render(
        tasks_file_path=tasks_file_path,
        stage_number=stage_number,
        stage_name=stage_name,
        pending_tasks=pending_tasks,
        branch_name=branch_name,
        base_branch=base_branch,
    )


def render_create_pr(
    tasks_file_path: str,
    stage_number: str | int,
    stage_name: str,
    branch_name: str,
    base_branch: str,
) -> str:
    """Render the create PR prompt.

    Args:
        tasks_file_path: Path to the tasks.md file.
        stage_number: The stage number.
        stage_name: The stage name.
        branch_name: The branch name for this stage.
        base_branch: The base branch for the PR.

    Returns:
        Rendered prompt string.
    """
    template = _env.get_template("create_pr.j2")
    return template.render(
        tasks_file_path=tasks_file_path,
        stage_number=stage_number,
        stage_name=stage_name,
        branch_name=branch_name,
        base_branch=base_branch,
    )


def render_review_code(
    tasks_file_path: str,
    stage_number: str | int,
    stage_name: str,
) -> str:
    """Render the code review prompt.

    Args:
        tasks_file_path: Path to the tasks.md file.
        stage_number: The stage number.
        stage_name: The stage name.

    Returns:
        Rendered prompt string.
    """
    template = _env.get_template("review_code.j2")
    return template.render(
        tasks_file_path=tasks_file_path,
        stage_number=stage_number,
        stage_name=stage_name,
    )


def render_qa_testing(
    tasks_file_path: str,
    stage_number: str | int,
    stage_name: str,
) -> str:
    """Render the QA testing prompt.

    Args:
        tasks_file_path: Path to the tasks.md file.
        stage_number: The stage number.
        stage_name: The stage name.

    Returns:
        Rendered prompt string.
    """
    template = _env.get_template("qa_testing.j2")
    return template.render(
        tasks_file_path=tasks_file_path,
        stage_number=stage_number,
        stage_name=stage_name,
    )
