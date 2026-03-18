"""Tests for ResponseChoice model and AgentResponse.choices field."""

import pytest

from shotgun.agents.models import AgentResponse, ResponseChoice


def test_response_choice_basic():
    """Test creating a basic ResponseChoice."""
    choice = ResponseChoice(
        label="Continue",
        value="continue",
    )
    assert choice.label == "Continue"
    assert choice.value == "continue"
    assert choice.is_default is False


def test_response_choice_with_default():
    """Test creating a default ResponseChoice."""
    choice = ResponseChoice(
        label="Continue with plan",
        value="continue",
        is_default=True,
    )
    assert choice.is_default is True


def test_agent_response_without_choices():
    """Test that AgentResponse works without choices (backward compatible)."""
    response = AgentResponse(response="Done!")
    assert response.choices is None


def test_agent_response_with_choices():
    """Test AgentResponse with choices."""
    choices = [
        ResponseChoice(label="Continue", value="continue", is_default=True),
        ResponseChoice(label="Talk about it", value="Let's discuss first."),
    ]
    response = AgentResponse(response="Plan status", choices=choices)
    assert response.choices is not None
    assert len(response.choices) == 2
    assert response.choices[0].is_default is True
    assert response.choices[1].is_default is False


def test_agent_response_choices_serialization():
    """Test that choices serialize and deserialize correctly."""
    choices = [
        ResponseChoice(label="Option A", value="a", is_default=True),
        ResponseChoice(label="Option B", value="b"),
    ]
    response = AgentResponse(response="Pick one", choices=choices)

    dumped = response.model_dump()
    assert "choices" in dumped
    assert len(dumped["choices"]) == 2
    assert dumped["choices"][0]["label"] == "Option A"
    assert dumped["choices"][0]["is_default"] is True

    # Round-trip
    restored = AgentResponse.model_validate(dumped)
    assert restored.choices is not None
    assert len(restored.choices) == 2
    assert restored.choices[0].label == "Option A"


@pytest.mark.smoke
def test_response_choice_model_dump():
    """Test ResponseChoice model_dump."""
    choice = ResponseChoice(
        label="Continue",
        value="continue",
        is_default=True,
    )
    dumped = choice.model_dump()
    assert dumped == {
        "label": "Continue",
        "value": "continue",
        "is_default": True,
    }
