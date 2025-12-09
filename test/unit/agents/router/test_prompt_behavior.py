"""Tests for router agent prompt behavioral rules."""

from pathlib import Path

import pytest


@pytest.fixture
def router_prompt_content() -> str:
    """Load the router.j2 prompt template content."""
    prompt_path = (
        Path(__file__).parents[4] / "src" / "shotgun" / "prompts" / "agents" / "router.j2"
    )
    return prompt_path.read_text()


def test_prompt_contains_clarifying_question_rules(router_prompt_content: str):
    """Test that prompt contains rules about when to ask clarifying questions."""
    assert "Ask Before Complex Work" in router_prompt_content
    assert "clarifying questions" in router_prompt_content.lower()


def test_prompt_contains_question_limit(router_prompt_content: str):
    """Test that prompt specifies 2-4 question limit."""
    assert "2-4" in router_prompt_content
    assert "Maximum 2-4 questions" in router_prompt_content


def test_prompt_contains_default_examples(router_prompt_content: str):
    """Test that prompt includes examples with defaults."""
    assert "default:" in router_prompt_content.lower()
    # Check for the specific default example
    assert "can add later" in router_prompt_content.lower()


def test_prompt_contains_incremental_execution_rules(router_prompt_content: str):
    """Test that prompt contains incremental execution rules."""
    assert "Work Incrementally" in router_prompt_content
    assert "Each user message gets ONE response" in router_prompt_content
    assert "then WAIT" in router_prompt_content


def test_prompt_contains_when_to_ask_section(router_prompt_content: str):
    """Test that prompt specifies when to ask questions."""
    # Check for key scenarios when to ask
    assert "ambiguous" in router_prompt_content.lower()
    assert "multiple valid approaches" in router_prompt_content.lower()
    assert "scope is unclear" in router_prompt_content.lower()


def test_prompt_contains_when_not_to_ask_section(router_prompt_content: str):
    """Test that prompt specifies when NOT to ask questions."""
    assert "DON'T ask when" in router_prompt_content
    assert "simple and clear" in router_prompt_content.lower()


def test_prompt_contains_anti_batch_example(router_prompt_content: str):
    """Test that prompt warns against batching multiple steps."""
    assert "Don't batch steps" in router_prompt_content
    assert "steps 1-5" in router_prompt_content.lower()


def test_prompt_contains_good_incremental_example(router_prompt_content: str):
    """Test that prompt shows good incremental behavior example."""
    assert "One step at a time" in router_prompt_content
    assert "Step 1 complete" in router_prompt_content


def test_prompt_contains_scope_expansion_warning(router_prompt_content: str):
    """Test that prompt warns against autonomous scope expansion."""
    assert "NEVER expand scope" in router_prompt_content
    assert "Do EXACTLY What The User Says" in router_prompt_content


def test_prompt_contains_cascade_confirmation_rule(router_prompt_content: str):
    """Test that prompt contains cascade confirmation rules."""
    assert "Confirm Before Cascading" in router_prompt_content
    assert "dependent files" in router_prompt_content.lower()


def test_prompt_contains_mode_system(router_prompt_content: str):
    """Test that prompt explains the Planning/Drafting mode system."""
    assert "Planning Mode" in router_prompt_content
    assert "Drafting Mode" in router_prompt_content
    assert "MODE SYSTEM" in router_prompt_content
