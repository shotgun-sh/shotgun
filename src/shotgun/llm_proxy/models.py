"""Pydantic models for LiteLLM Proxy API."""

from enum import StrEnum

from pydantic import BaseModel, Field


class BudgetSource(StrEnum):
    """Source of budget information."""

    KEY = "key"
    TEAM = "team"


class KeyInfoData(BaseModel):
    """Key information data from /key/info endpoint."""

    key_name: str = Field(description="Key name/identifier")
    key_alias: str | None = Field(default=None, description="Human-readable key alias")
    spend: float = Field(description="Current spend for this key in USD")
    max_budget: float | None = Field(
        default=None, description="Maximum budget for this key in USD"
    )
    team_id: str = Field(description="Team ID associated with this key")
    user_id: str = Field(description="User ID associated with this key")
    models: list[str] = Field(
        default_factory=list, description="List of models available to this key"
    )


class KeyInfoResponse(BaseModel):
    """Response from /key/info endpoint."""

    key: str = Field(description="The API key")
    info: KeyInfoData = Field(description="Key information data")


class TeamInfoData(BaseModel):
    """Team information data from /team/info endpoint."""

    team_id: str = Field(description="Team identifier")
    team_alias: str | None = Field(
        default=None, description="Human-readable team alias"
    )
    max_budget: float | None = Field(
        default=None, description="Maximum budget for this team in USD"
    )
    spend: float = Field(description="Current spend for this team in USD")
    models: list[str] = Field(
        default_factory=list, description="List of models available to this team"
    )


class TeamInfoResponse(BaseModel):
    """Response from /team/info endpoint."""

    team_id: str = Field(description="Team identifier")
    team_info: TeamInfoData = Field(description="Team information data")


class BudgetInfo(BaseModel):
    """Unified budget information.

    Combines key and team budget information to provide a single view
    of budget status. Budget can come from either key-level or team-level,
    with key-level taking priority if set.
    """

    max_budget: float = Field(description="Maximum budget in USD")
    spend: float = Field(description="Current spend in USD")
    remaining: float = Field(description="Remaining budget in USD")
    source: BudgetSource = Field(
        description="Source of budget information (key or team)"
    )
    percentage_used: float = Field(description="Percentage of budget used (0-100)")

    @classmethod
    def from_key_info(cls, key_info: KeyInfoData) -> "BudgetInfo":
        """Create BudgetInfo from key-level budget.

        Args:
            key_info: Key information containing budget data

        Returns:
            BudgetInfo instance with key-level budget

        Raises:
            ValueError: If key does not have max_budget set
        """
        if key_info.max_budget is None:
            raise ValueError("Key does not have max_budget set")

        remaining = key_info.max_budget - key_info.spend
        percentage_used = (
            (key_info.spend / key_info.max_budget * 100)
            if key_info.max_budget > 0
            else 0.0
        )

        return cls(
            max_budget=key_info.max_budget,
            spend=key_info.spend,
            remaining=remaining,
            source=BudgetSource.KEY,
            percentage_used=percentage_used,
        )

    @classmethod
    def from_team_info(cls, team_info: TeamInfoData) -> "BudgetInfo":
        """Create BudgetInfo from team-level budget.

        Args:
            team_info: Team information containing budget data

        Returns:
            BudgetInfo instance with team-level budget

        Raises:
            ValueError: If team does not have max_budget set
        """
        if team_info.max_budget is None:
            raise ValueError("Team does not have max_budget set")

        remaining = team_info.max_budget - team_info.spend
        percentage_used = (
            (team_info.spend / team_info.max_budget * 100)
            if team_info.max_budget > 0
            else 0.0
        )

        return cls(
            max_budget=team_info.max_budget,
            spend=team_info.spend,
            remaining=remaining,
            source=BudgetSource.TEAM,
            percentage_used=percentage_used,
        )
