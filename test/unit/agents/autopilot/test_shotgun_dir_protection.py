"""Tests that .shotgun/ directory protection rules appear in all autopilot prompts.

Users reported files disappearing from .shotgun/ during autopilot execution.
These tests verify that every prompt template includes explicit instructions
forbidding deletion or modification of .shotgun/ files.
"""

from shotgun.agents.autopilot.prompts import (
    ParallelStageInfo,
    render_create_pr,
    render_execute_parallel_stages,
    render_execute_stage,
    render_qa_testing,
    render_review_code,
)

# Key phrases that MUST appear in every prompt (via context_preamble.j2)
PROTECTION_PHRASES = [
    "DO NOT DELETE, MOVE, OR OVERWRITE files in .shotgun/",
    "MUST remain intact",
    "DO NOT run `rm`",
    "DO NOT overwrite `.shotgun/` files",
]

READONLY_PHRASES = [
    "Read-only reference material",
    "NOT to be referenced or imported by production code",
]

CONTRACT_COPY_PHRASES = [
    "Contracts and example code must be copied, not used directly",
    "specifications and reference implementations, not production code",
    "Never** import from, reference, or directly use files in `.shotgun/`",
]

GITIGNORE_PHRASES = [
    "Ensure .shotgun/ is in the project's .gitignore",
    "add `.shotgun/` to `.gitignore`",
]

TASKS_CHECKBOX_PHRASE = "changing `- [ ]` to `- [x]`"


def _render_execute_stage() -> str:
    return render_execute_stage(
        tasks_file_path=".shotgun/tasks.md",
        stage_number="1",
        stage_name="Setup",
        pending_tasks=["Initialize project"],
        branch_name="autopilot/stage-1",
        base_branch="main",
    )


def _render_review_code() -> str:
    return render_review_code(
        tasks_file_path=".shotgun/tasks.md",
        stage_number="1",
        stage_name="Setup",
    )


def _render_create_pr() -> str:
    return render_create_pr(
        tasks_file_path=".shotgun/tasks.md",
        stage_number="1",
        stage_name="Setup",
        branch_name="autopilot/stage-1",
        base_branch="main",
    )


def _render_qa_testing() -> str:
    return render_qa_testing(
        tasks_file_path=".shotgun/tasks.md",
        stage_number="1",
        stage_name="Setup",
    )


def _render_parallel_stages() -> str:
    return render_execute_parallel_stages(
        tasks_file_path=".shotgun/tasks.md",
        stages=[
            ParallelStageInfo(
                number="1",
                name="Auth",
                branch_name="autopilot/stage-1",
                pending_tasks=["Add login"],
            ),
        ],
        base_branch="main",
        batch_level=1,
    )


# --- Protection rules in execute_stage ---


def test_execute_stage_includes_no_delete_rules():
    """Execute stage prompt forbids deleting .shotgun/ files."""
    prompt = _render_execute_stage()
    for phrase in PROTECTION_PHRASES:
        assert phrase in prompt, f"Missing protection phrase: {phrase}"


def test_execute_stage_includes_readonly_rules():
    """Execute stage prompt marks .shotgun/ as read-only reference."""
    prompt = _render_execute_stage()
    for phrase in READONLY_PHRASES:
        assert phrase in prompt, f"Missing readonly phrase: {phrase}"


def test_execute_stage_includes_contract_copy_rules():
    """Execute stage prompt requires copying contracts, not using directly."""
    prompt = _render_execute_stage()
    for phrase in CONTRACT_COPY_PHRASES:
        assert phrase in prompt, f"Missing contract copy phrase: {phrase}"


def test_execute_stage_permits_tasks_checkbox_updates():
    """Execute stage prompt explicitly allows updating task checkboxes."""
    prompt = _render_execute_stage()
    assert TASKS_CHECKBOX_PHRASE in prompt


# --- Protection rules in review_code ---


def test_review_code_includes_no_delete_rules():
    """Review code prompt forbids deleting .shotgun/ files."""
    prompt = _render_review_code()
    for phrase in PROTECTION_PHRASES:
        assert phrase in prompt, f"Missing protection phrase: {phrase}"


def test_review_code_includes_readonly_rules():
    """Review code prompt marks .shotgun/ as read-only reference."""
    prompt = _render_review_code()
    for phrase in READONLY_PHRASES:
        assert phrase in prompt, f"Missing readonly phrase: {phrase}"


# --- Protection rules in create_pr ---


def test_create_pr_includes_no_delete_rules():
    """Create PR prompt forbids deleting .shotgun/ files."""
    prompt = _render_create_pr()
    for phrase in PROTECTION_PHRASES:
        assert phrase in prompt, f"Missing protection phrase: {phrase}"


# --- Protection rules in qa_testing ---


def test_qa_testing_includes_no_delete_rules():
    """QA testing prompt forbids deleting .shotgun/ files."""
    prompt = _render_qa_testing()
    for phrase in PROTECTION_PHRASES:
        assert phrase in prompt, f"Missing protection phrase: {phrase}"


# --- Protection rules in parallel stages ---


def test_parallel_stages_includes_no_delete_rules():
    """Parallel stages prompt forbids deleting .shotgun/ files."""
    prompt = _render_parallel_stages()
    for phrase in PROTECTION_PHRASES:
        assert phrase in prompt, f"Missing protection phrase: {phrase}"


def test_parallel_stages_includes_contract_copy_rules():
    """Parallel stages prompt requires copying contracts, not using directly."""
    prompt = _render_parallel_stages()
    for phrase in CONTRACT_COPY_PHRASES:
        assert phrase in prompt, f"Missing contract copy phrase: {phrase}"


# --- Gitignore instruction in all prompts ---


def test_execute_stage_includes_gitignore_instruction():
    """Execute stage prompt tells Claude Code to add .shotgun/ to .gitignore."""
    prompt = _render_execute_stage()
    for phrase in GITIGNORE_PHRASES:
        assert phrase in prompt, f"Missing gitignore phrase: {phrase}"


def test_review_code_includes_gitignore_instruction():
    """Review code prompt tells Claude Code to add .shotgun/ to .gitignore."""
    prompt = _render_review_code()
    for phrase in GITIGNORE_PHRASES:
        assert phrase in prompt, f"Missing gitignore phrase: {phrase}"


def test_create_pr_includes_gitignore_instruction():
    """Create PR prompt tells Claude Code to add .shotgun/ to .gitignore."""
    prompt = _render_create_pr()
    for phrase in GITIGNORE_PHRASES:
        assert phrase in prompt, f"Missing gitignore phrase: {phrase}"


def test_qa_testing_includes_gitignore_instruction():
    """QA testing prompt tells Claude Code to add .shotgun/ to .gitignore."""
    prompt = _render_qa_testing()
    for phrase in GITIGNORE_PHRASES:
        assert phrase in prompt, f"Missing gitignore phrase: {phrase}"


def test_parallel_stages_includes_gitignore_instruction():
    """Parallel stages prompt tells Claude Code to add .shotgun/ to .gitignore."""
    prompt = _render_parallel_stages()
    for phrase in GITIGNORE_PHRASES:
        assert phrase in prompt, f"Missing gitignore phrase: {phrase}"
