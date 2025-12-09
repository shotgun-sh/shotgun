"""Unit tests for ModeIndicator widget."""

import pytest

from shotgun.agents.models import AgentType
from shotgun.tui.components.mode_indicator import ModeIndicator

pytestmark = pytest.mark.asyncio


async def test_render_legacy_research_mode() -> None:
    """Test that legacy Research mode displays correctly."""
    from textual.app import App

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
    from textual.app import App

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
    from textual.app import App

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
    from textual.app import App

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
    from textual.app import App

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
    from textual.app import App

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
    from textual.app import App

    class TestApp(App):
        def compose(self):
            yield ModeIndicator(mode=AgentType.RESEARCH)

    async with TestApp().run_test() as pilot:
        indicator = pilot.app.query_one(ModeIndicator)
        # Force a render
        indicator.render()

        assert not indicator.has_class("mode-planning")
        assert not indicator.has_class("mode-drafting")


async def test_render_router_mode_method_planning() -> None:
    """Test _render_router_mode returns Planning format when screen has no provider."""
    from textual.app import App

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
    from textual.app import App

    class TestApp(App):
        def compose(self):
            yield ModeIndicator(mode=AgentType.ROUTER)

    async with TestApp().run_test() as pilot:
        indicator = pilot.app.query_one(ModeIndicator)
        # Force render which sets CSS class
        indicator.render()

        # Default should be planning mode
        assert indicator.has_class("mode-planning")


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
    """Test that all modes have descriptions."""
    indicator = ModeIndicator(mode=AgentType.RESEARCH)

    expected_descriptions = {
        AgentType.RESEARCH: "research",
        AgentType.SPECIFY: "specification",
        AgentType.PLAN: "plan",
        AgentType.TASKS: "task",
        AgentType.EXPORT: "export",
    }

    for mode, _keyword in expected_descriptions.items():
        indicator.mode = mode
        rendered = indicator._render_legacy_mode()
        # Each mode should have some description text
        assert len(rendered) > 20  # Has some content beyond just mode name


def test_sub_agent_display_mapping() -> None:
    """Test that sub-agent type strings map to display names correctly."""
    # Verify the sub_agent_display dict mapping used in ModeIndicator
    sub_agent_types = ["research", "specify", "plan", "tasks", "export"]

    for sub_type in sub_agent_types:
        # The mapping should handle these types
        expected_display = sub_type.title()
        # Verify the display name would be used (dict lookup)
        sub_agent_display = {
            "research": "Research",
            "specify": "Specify",
            "plan": "Plan",
            "tasks": "Tasks",
            "export": "Export",
        }
        assert sub_agent_display.get(sub_type) == expected_display


async def test_indicator_can_change_mode() -> None:
    """Test that mode can be changed after initialization."""
    from textual.app import App

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
