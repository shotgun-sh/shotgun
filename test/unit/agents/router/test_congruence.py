"""Tests for planner agent congruence checking rules (Stage 6).

These rules live in the planner prompt (planner.j2) which is the full
orchestrator prompt. In tiered mode, the Router uses a simplified triage
prompt and escalates to the Planner for complex work.
"""

from pathlib import Path

import pytest


@pytest.fixture
def router_prompt_content() -> str:
    """Load the planner.j2 prompt template content (was router.j2 before tiering)."""
    prompt_path = (
        Path(__file__).parents[4]
        / "src"
        / "shotgun"
        / "prompts"
        / "agents"
        / "planner.j2"
    )
    return prompt_path.read_text()


def test_prompt_contains_congruence_rule(router_prompt_content: str):
    """Test that prompt contains the congruence verification rule."""
    assert "Verify Congruence Before Changes" in router_prompt_content
    assert '<RULE name="Verify Congruence Before Changes">' in router_prompt_content


def test_prompt_contains_file_dependency_direction(router_prompt_content: str):
    """Test that prompt specifies upstream to downstream file dependency."""
    assert "upstream" in router_prompt_content.lower()
    assert "downstream" in router_prompt_content.lower()
    # Check the dependency chain is documented
    assert "specification.md" in router_prompt_content
    assert "plan.md" in router_prompt_content
    assert "tasks.md" in router_prompt_content


def test_prompt_contains_when_to_check_congruence(router_prompt_content: str):
    """Test that prompt specifies when congruence checks are needed."""
    assert "When to check congruence:" in router_prompt_content
    # Adding to tasks.md requires checking plan and spec
    assert "Adding to tasks.md" in router_prompt_content
    # Adding to plan.md requires checking spec
    assert "Adding to plan.md" in router_prompt_content


def test_prompt_contains_no_check_for_upstream_files(router_prompt_content: str):
    """Test that prompt specifies no congruence check for upstream files."""
    assert "No congruence check needed" in router_prompt_content
    # Spec and research are upstream - no check needed
    assert "specification.md" in router_prompt_content
    assert "research.md" in router_prompt_content


def test_prompt_contains_incongruence_resolution_options(router_prompt_content: str):
    """Test that prompt contains the three resolution options for incongruence."""
    # Option 1: Add anyway
    assert "Add the task anyway" in router_prompt_content
    # Option 2: Update upstream first
    assert "add caching to the spec and plan" in router_prompt_content.lower()
    # Option 3: Skip/review
    assert "Skip" in router_prompt_content


def test_prompt_contains_congruence_bad_example(router_prompt_content: str):
    """Test that prompt shows a bad example of ignoring congruence."""
    # The bad example shows adding without checking
    assert "adds task to tasks.md without checking" in router_prompt_content
    assert "out of sync" in router_prompt_content.lower()


def test_prompt_contains_congruence_good_example(router_prompt_content: str):
    """Test that prompt shows a good example of congruence checking."""
    # The good example shows checking spec and plan first
    assert "I checked specification.md and plan.md" in router_prompt_content
    assert "Which would you prefer?" in router_prompt_content
