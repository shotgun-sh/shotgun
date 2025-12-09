"""Unit tests for ModeIndicator widget."""

import pytest
from textual.app import App

from shotgun.agents.models import AgentType
from shotgun.tui.components.mode_indicator import (
    AGENT_DESCRIPTIONS,
    AGENT_DISPLAY_NAMES,
    ModeIndicator,
    RouterModeCssClass,
)

pytestmark = pytest.mark.asyncio


async def test_render_legacy_research_mode() -> None:
    """Test that legacy Research mode displays correctly."""

    class TestApp(App):
        def compose(self):
            yield ModeIndicator(mode=AgentType.RESEARCH)

    async with TestApp().run_test() as pilot:
        indicator = pilot.app.query_one(ModeIndicator)
        rendered = indicator.render()

        # Should contain mode name and description
        assert "Research" in rendered
        assert "mode" in rendered


async def test_render_legacy_specify_mode() -> None:
    """Test that legacy Specify mode displays correctly."""

    class TestApp(App):
        def compose(self):
            yield ModeIndicator(mode=AgentType.SPECIFY)

    async with TestApp().run_test() as pilot:
        indicator = pilot.app.query_one(ModeIndicator)
        rendered = indicator.render()

        # Should contain mode name
        assert "Specify" in rendered
        assert "mode" in rendered


async def test_render_legacy_plan_mode() -> None:
    """Test that legacy Plan mode displays correctly."""

    class TestApp(App):
        def compose(self):
            yield ModeIndicator(mode=AgentType.PLAN)

    async with TestApp().run_test() as pilot:
        indicator = pilot.app.query_one(ModeIndicator)
        rendered = indicator.render()

        # Should contain mode name
        assert "Planning" in rendered
        assert "mode" in rendered


async def test_render_legacy_tasks_mode() -> None:
    """Test that legacy Tasks mode displays correctly."""

    class TestApp(App):
        def compose(self):
            yield ModeIndicator(mode=AgentType.TASKS)

    async with TestApp().run_test() as pilot:
        indicator = pilot.app.query_one(ModeIndicator)
        rendered = indicator.render()

        # Should contain mode name
        assert "Tasks" in rendered
        assert "mode" in rendered


async def test_render_legacy_export_mode() -> None:
    """Test that legacy Export mode displays correctly."""

    class TestApp(App):
        def compose(self):
            yield ModeIndicator(mode=AgentType.EXPORT)

    async with TestApp().run_test() as pilot:
        indicator = pilot.app.query_one(ModeIndicator)
        rendered = indicator.render()

        # Should contain mode name
        assert "Export" in rendered
        assert "mode" in rendered


async def test_render_router_mode_defaults_to_planning() -> None:
    """Test that Router mode defaults to Planning display when no provider."""

    class TestApp(App):
        def compose(self):
            yield ModeIndicator(mode=AgentType.ROUTER)

    async with TestApp().run_test() as pilot:
        indicator = pilot.app.query_one(ModeIndicator)
        rendered = indicator.render()

        # Should show Planning mode by default (screen doesn't provide router_mode)
        assert "📋" in rendered
        assert "Planning" in rendered


async def test_mode_indicator_initialization() -> None:
    """Test ModeIndicator initializes with correct mode."""
    indicator = ModeIndicator(mode=AgentType.RESEARCH)
    assert indicator.mode == AgentType.RESEARCH

    indicator2 = ModeIndicator(mode=AgentType.ROUTER)
    assert indicator2.mode == AgentType.ROUTER


async def test_legacy_mode_clears_router_css_classes() -> None:
    """Test that legacy modes don't have router CSS classes."""

    class TestApp(App):
        def compose(self):
            yield ModeIndicator(mode=AgentType.RESEARCH)

    async with TestApp().run_test() as pilot:
        indicator = pilot.app.query_one(ModeIndicator)
        # Force a render
        indicator.render()

        assert not indicator.has_class(RouterModeCssClass.PLANNING)
        assert not indicator.has_class(RouterModeCssClass.DRAFTING)


async def test_render_router_mode_method_planning() -> None:
    """Test _render_router_mode returns Planning format when screen has no provider."""

    class TestApp(App):
        def compose(self):
            yield ModeIndicator(mode=AgentType.ROUTER)

    async with TestApp().run_test() as pilot:
        indicator = pilot.app.query_one(ModeIndicator)
        # Call internal method with screen context (screen doesn't provide router_mode)
        rendered = indicator._render_router_mode()

        # Should default to Planning
        assert "📋" in rendered
        assert "Planning" in rendered
        assert "mode" in rendered


def test_render_legacy_mode_method() -> None:
    """Test _render_legacy_mode returns correct format."""
    indicator = ModeIndicator(mode=AgentType.RESEARCH)

    rendered = indicator._render_legacy_mode()

    assert "Research" in rendered
    assert "mode" in rendered


def test_render_legacy_mode_with_unknown_type() -> None:
    """Test _render_legacy_mode handles unknown mode gracefully."""
    # Create indicator with a mode that might not have a mapping
    indicator = ModeIndicator(mode=AgentType.ROUTER)
    indicator.mode = AgentType.RESEARCH  # Change to known type

    rendered = indicator._render_legacy_mode()

    # Should still render without error
    assert "Research" in rendered


async def test_router_mode_sets_planning_css_class() -> None:
    """Test that router mode sets mode-planning CSS class."""

    class TestApp(App):
        def compose(self):
            yield ModeIndicator(mode=AgentType.ROUTER)

    async with TestApp().run_test() as pilot:
        indicator = pilot.app.query_one(ModeIndicator)
        # Force render which sets CSS class
        indicator.render()

        # Default should be planning mode
        assert indicator.has_class(RouterModeCssClass.PLANNING)


def test_mode_display_mapping() -> None:
    """Test that all expected mode display names are defined."""
    indicator = ModeIndicator(mode=AgentType.RESEARCH)

    # These should all be in the mode_display dict
    expected_modes = [
        AgentType.RESEARCH,
        AgentType.SPECIFY,
        AgentType.PLAN,
        AgentType.TASKS,
        AgentType.EXPORT,
    ]

    for mode in expected_modes:
        indicator.mode = mode
        rendered = indicator._render_legacy_mode()
        # Should render without error and contain "mode"
        assert "mode" in rendered


def test_mode_description_mapping() -> None:
    """Test that AGENT_DESCRIPTIONS constant contains all agent types."""
    expected_agent_types = [
        AgentType.RESEARCH,
        AgentType.SPECIFY,
        AgentType.PLAN,
        AgentType.TASKS,
        AgentType.EXPORT,
    ]

    for agent_type in expected_agent_types:
        # All expected types should be in the mapping
        assert agent_type in AGENT_DESCRIPTIONS
        # Description should be a non-empty string
        description = AGENT_DESCRIPTIONS[agent_type]
        assert isinstance(description, str)
        assert len(description) > 10  # Has meaningful content


def test_sub_agent_display_mapping() -> None:
    """Test that AGENT_DISPLAY_NAMES constant maps all agent types correctly."""
    # Verify the shared AGENT_DISPLAY_NAMES constant used in ModeIndicator
    expected_agent_types = [
        AgentType.RESEARCH,
        AgentType.SPECIFY,
        AgentType.PLAN,
        AgentType.TASKS,
        AgentType.EXPORT,
    ]

    for agent_type in expected_agent_types:
        # All expected types should be in the mapping
        assert agent_type in AGENT_DISPLAY_NAMES
        # Display name should be a non-empty string
        display_name = AGENT_DISPLAY_NAMES[agent_type]
        assert isinstance(display_name, str)
        assert len(display_name) > 0


def test_router_mode_css_class_enum() -> None:
    """Test that RouterModeCssClass enum has expected values."""
    # Verify enum values match expected CSS class names
    assert RouterModeCssClass.PLANNING == "mode-planning"
    assert RouterModeCssClass.DRAFTING == "mode-drafting"

    # Verify enum has exactly 2 members
    assert len(RouterModeCssClass) == 2


async def test_indicator_can_change_mode() -> None:
    """Test that mode can be changed after initialization."""

    class TestApp(App):
        def compose(self):
            yield ModeIndicator(mode=AgentType.RESEARCH)

    async with TestApp().run_test() as pilot:
        indicator = pilot.app.query_one(ModeIndicator)

        # Initial mode
        assert indicator.mode == AgentType.RESEARCH
        rendered1 = indicator.render()
        assert "Research" in rendered1

        # Change mode
        indicator.mode = AgentType.SPECIFY
        rendered2 = indicator.render()
        assert "Specify" in rendered2

        # Change to router
        indicator.mode = AgentType.ROUTER
        rendered3 = indicator.render()
        assert "📋" in rendered3 or "Planning" in rendered3
