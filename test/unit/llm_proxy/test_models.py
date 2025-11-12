"""Tests for LiteLLM Proxy API models."""

import pytest

from shotgun.llm_proxy.models import (
    BudgetInfo,
    BudgetSource,
    KeyInfoData,
    KeyInfoResponse,
    TeamInfoData,
    TeamInfoResponse,
)


def test_key_info_data_creation():
    """Test KeyInfoData model creation."""
    key_info = KeyInfoData(
        key_name="sk-test",
        key_alias="TestKey",
        spend=1.5,
        max_budget=10.0,
        team_id="team-123",
        user_id="user-456",
        models=["gpt-4", "claude"],
    )
    assert key_info.key_name == "sk-test"
    assert key_info.spend == 1.5
    assert key_info.max_budget == 10.0


def test_key_info_data_optional_fields():
    """Test KeyInfoData with optional fields."""
    key_info = KeyInfoData(
        key_name="sk-test",
        spend=0.0,
        max_budget=None,  # Optional
        team_id="team-123",
        user_id="user-456",
    )
    assert key_info.key_alias is None
    assert key_info.max_budget is None
    assert key_info.models == []


def test_key_info_response_from_dict():
    """Test KeyInfoResponse from API response dict."""
    api_data = {
        "key": "sk-test123",
        "info": {
            "key_name": "sk-test",
            "key_alias": "TestKey",
            "spend": 2.5,
            "max_budget": 50.0,
            "team_id": "team-789",
            "user_id": "user-101",
            "models": ["model1", "model2"],
        },
    }
    response = KeyInfoResponse.model_validate(api_data)
    assert response.key == "sk-test123"
    assert response.info.spend == 2.5
    assert response.info.max_budget == 50.0


def test_team_info_data_creation():
    """Test TeamInfoData model creation."""
    team_info = TeamInfoData(
        team_id="team-456",
        team_alias="TestTeam",
        max_budget=100.0,
        spend=25.5,
        models=["gpt-4"],
    )
    assert team_info.team_id == "team-456"
    assert team_info.spend == 25.5
    assert team_info.max_budget == 100.0


def test_team_info_response_from_dict():
    """Test TeamInfoResponse from API response dict."""
    api_data = {
        "team_id": "team-xyz",
        "team_info": {
            "team_id": "team-xyz",
            "team_alias": "MyTeam",
            "max_budget": 200.0,
            "spend": 50.0,
            "models": [],
        },
    }
    response = TeamInfoResponse.model_validate(api_data)
    assert response.team_id == "team-xyz"
    assert response.team_info.max_budget == 200.0


def test_budget_info_from_key_info():
    """Test BudgetInfo creation from key-level budget."""
    key_info = KeyInfoData(
        key_name="sk-test",
        spend=3.0,
        max_budget=10.0,
        team_id="team-123",
        user_id="user-456",
    )
    budget_info = BudgetInfo.from_key_info(key_info)

    assert budget_info.max_budget == 10.0
    assert budget_info.spend == 3.0
    assert budget_info.remaining == 7.0
    assert budget_info.source == BudgetSource.KEY
    assert budget_info.percentage_used == 30.0


def test_budget_info_from_key_info_no_budget():
    """Test BudgetInfo creation fails when key has no budget."""
    key_info = KeyInfoData(
        key_name="sk-test",
        spend=0.0,
        max_budget=None,  # No budget set
        team_id="team-123",
        user_id="user-456",
    )

    with pytest.raises(ValueError, match="Key does not have max_budget set"):
        BudgetInfo.from_key_info(key_info)


def test_budget_info_from_team_info():
    """Test BudgetInfo creation from team-level budget."""
    team_info = TeamInfoData(
        team_id="team-456",
        max_budget=50.0,
        spend=12.5,
    )
    budget_info = BudgetInfo.from_team_info(team_info)

    assert budget_info.max_budget == 50.0
    assert budget_info.spend == 12.5
    assert budget_info.remaining == 37.5
    assert budget_info.source == BudgetSource.TEAM
    assert budget_info.percentage_used == 25.0


def test_budget_info_from_team_info_no_budget():
    """Test BudgetInfo creation fails when team has no budget."""
    team_info = TeamInfoData(
        team_id="team-456",
        max_budget=None,  # No budget set
        spend=0.0,
    )

    with pytest.raises(ValueError, match="Team does not have max_budget set"):
        BudgetInfo.from_team_info(team_info)


def test_budget_info_percentage_calculation():
    """Test percentage used calculation."""
    key_info = KeyInfoData(
        key_name="sk-test",
        spend=7.5,
        max_budget=10.0,
        team_id="team-123",
        user_id="user-456",
    )
    budget_info = BudgetInfo.from_key_info(key_info)

    assert budget_info.percentage_used == 75.0


def test_budget_info_zero_budget():
    """Test BudgetInfo with zero budget."""
    key_info = KeyInfoData(
        key_name="sk-test",
        spend=0.0,
        max_budget=0.0,
        team_id="team-123",
        user_id="user-456",
    )
    budget_info = BudgetInfo.from_key_info(key_info)

    assert budget_info.percentage_used == 0.0
    assert budget_info.remaining == 0.0
