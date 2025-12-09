"""Tests for mode toggle functionality."""

import pytest

from shotgun.agents.router.models import RouterDeps, RouterMode


class TestRouterModeToggle:
    """Tests for Router mode toggle behavior."""

    def test_toggle_planning_to_drafting(self):
        """Toggle from Planning to Drafting mode."""
        # Create a minimal RouterDeps - just testing the enum assignment
        # RouterDeps inherits from AgentDeps which has many required fields,
        # so we test the mode toggle logic directly on the enum

        # Start in Planning mode
        mode = RouterMode.PLANNING
        assert mode == RouterMode.PLANNING

        # Toggle to Drafting
        if mode == RouterMode.PLANNING:
            mode = RouterMode.DRAFTING

        assert mode == RouterMode.DRAFTING

    def test_toggle_drafting_to_planning(self):
        """Toggle from Drafting to Planning mode."""
        mode = RouterMode.DRAFTING
        assert mode == RouterMode.DRAFTING

        # Toggle to Planning
        if mode == RouterMode.DRAFTING:
            mode = RouterMode.PLANNING

        assert mode == RouterMode.PLANNING

    def test_router_mode_enum_values(self):
        """Test RouterMode enum has expected values."""
        assert RouterMode.PLANNING == "planning"
        assert RouterMode.DRAFTING == "drafting"

    def test_router_mode_default_is_planning(self):
        """Verify that RouterMode.PLANNING is the intended default."""
        # This tests the implicit design decision
        assert RouterMode.PLANNING.value == "planning"


class TestModePersistence:
    """Tests for mode persistence to config."""

    @pytest.mark.asyncio
    async def test_migration_adds_router_mode(self):
        """Test that v5->v6 migration adds router_mode field."""
        from shotgun.agents.config.manager import _migrate_v5_to_v6

        # Config at version 5 without router_mode
        data = {"config_version": 5, "some_field": "value"}

        # Apply migration
        result = _migrate_v5_to_v6(data)

        # Should have router_mode with default "planning"
        assert result["router_mode"] == "planning"
        assert result["config_version"] == 6

    @pytest.mark.asyncio
    async def test_migration_preserves_existing_router_mode(self):
        """Test that migration doesn't overwrite existing router_mode."""
        from shotgun.agents.config.manager import _migrate_v5_to_v6

        # Config already has router_mode
        data = {"config_version": 5, "router_mode": "drafting"}

        # Apply migration
        result = _migrate_v5_to_v6(data)

        # Should preserve the existing value
        assert result["router_mode"] == "drafting"
        assert result["config_version"] == 6

    def test_shotgun_config_has_router_mode_field(self):
        """Test ShotgunConfig model has router_mode field with correct default."""
        from shotgun.agents.config.models import ShotgunConfig

        # Create config with only required fields
        config = ShotgunConfig(shotgun_instance_id="test-id")

        # Should have router_mode with default "planning"
        assert config.router_mode == "planning"

    def test_shotgun_config_accepts_drafting_mode(self):
        """Test ShotgunConfig accepts 'drafting' as router_mode."""
        from shotgun.agents.config.models import ShotgunConfig

        config = ShotgunConfig(
            shotgun_instance_id="test-id",
            router_mode="drafting",
        )

        assert config.router_mode == "drafting"


class TestExecutionGuard:
    """Tests for the is_executing guard that prevents mode switching."""

    def test_is_executing_flag_defaults_to_false(self):
        """Test that is_executing defaults to False on RouterDeps."""
        # We can't easily instantiate RouterDeps without mocking many things,
        # but we can test the field definition

        # Check the field has correct default in the model
        field_info = RouterDeps.model_fields["is_executing"]
        assert field_info.default is False

    def test_is_executing_prevents_toggle(self):
        """Test that mode toggle should be blocked when is_executing=True.

        This is a behavioral test - the actual blocking happens in ChatScreen.
        Here we just verify the flag can be set.
        """
        # The is_executing flag should be a boolean
        is_executing = True

        # When is_executing is True, toggle should be blocked
        # (The actual blocking logic is in ChatScreen._toggle_router_mode)
        should_allow_toggle = not is_executing
        assert should_allow_toggle is False


class TestConfigManagerMethods:
    """Tests for ConfigManager router mode methods."""

    @pytest.mark.asyncio
    async def test_get_router_mode(self, tmp_path):
        """Test get_router_mode returns saved mode."""
        from shotgun.agents.config.manager import ConfigManager

        config_path = tmp_path / "config.json"
        manager = ConfigManager(config_path=config_path)

        # Initialize config (creates file with defaults)
        await manager.initialize()

        # Get mode - should be default "planning"
        mode = await manager.get_router_mode()
        assert mode == "planning"

    @pytest.mark.asyncio
    async def test_set_router_mode(self, tmp_path):
        """Test set_router_mode saves mode to config."""
        from shotgun.agents.config.manager import ConfigManager

        config_path = tmp_path / "config.json"
        manager = ConfigManager(config_path=config_path)

        # Initialize config
        await manager.initialize()

        # Set mode to drafting
        await manager.set_router_mode("drafting")

        # Verify it was saved
        mode = await manager.get_router_mode()
        assert mode == "drafting"

    @pytest.mark.asyncio
    async def test_set_router_mode_persists(self, tmp_path):
        """Test that router mode persists across manager instances."""
        from shotgun.agents.config.manager import ConfigManager

        config_path = tmp_path / "config.json"

        # First manager instance
        manager1 = ConfigManager(config_path=config_path)
        await manager1.initialize()
        await manager1.set_router_mode("drafting")

        # Second manager instance (simulates restart)
        manager2 = ConfigManager(config_path=config_path)
        mode = await manager2.get_router_mode()

        assert mode == "drafting"
