"""Proof-of-concept tests for TUI automation using Textual's testing capabilities.

This module demonstrates how to:
- Start the app in test mode
- Simulate user interactions (key presses, clicks)
- Take screenshots for visual verification
- Query and inspect widgets
- Create dynamic test scripts

Textual Testing Guide: https://textual.textualize.io/guide/testing/
"""

import pytest
from pathlib import Path
from textual.pilot import Pilot
from shotgun.tui.app import ShotgunApp


# Configure pytest to create screenshots directory
@pytest.fixture(scope="session")
def screenshots_dir(tmp_path_factory):
    """Create a temporary directory for test screenshots."""
    screenshots_path = tmp_path_factory.mktemp("tui_screenshots")
    return screenshots_path


@pytest.fixture
def mock_config(monkeypatch, tmp_path):
    """Mock configuration to avoid requiring real API keys or directories."""
    # Mock the config manager to return a valid config
    from shotgun.agents.config import ShotgunConfig
    from shotgun.agents.config.models import (
        OpenAIConfig,
        AnthropicConfig,
        GoogleConfig,
        ShotgunAccountConfig,
        ModelName,
    )
    from pydantic import SecretStr
    import uuid

    class MockConfigManager:
        def load(self):
            return ShotgunConfig(
                shown_welcome_screen=True,
                openai=OpenAIConfig(api_key=SecretStr("test-key-openai")),
                anthropic=AnthropicConfig(api_key=SecretStr("test-key-anthropic")),
                google=GoogleConfig(api_key=SecretStr("test-key-google")),
                shotgun=ShotgunAccountConfig(api_key=SecretStr("test-key-shotgun")),
                selected_model=ModelName.CLAUDE_SONNET_4_5,
                shotgun_instance_id=str(uuid.uuid4()),
            )

        def has_any_provider_key(self):
            return True

        def save(self, config):
            pass

    # Mock get_config_manager
    monkeypatch.setattr(
        "shotgun.tui.app.get_config_manager",
        lambda: MockConfigManager()
    )

    # Mock get_shotgun_base_path to return a temp directory
    shotgun_dir = tmp_path / ".shotgun-sh"
    shotgun_dir.mkdir(exist_ok=True)
    monkeypatch.setattr(
        "shotgun.tui.app.get_shotgun_base_path",
        lambda: shotgun_dir
    )

    # Mock telemetry to avoid tracking during tests
    monkeypatch.setattr(
        "shotgun.posthog_telemetry.track_event",
        lambda *args, **kwargs: None
    )

    # Mock auto-update to avoid update checks
    monkeypatch.setattr(
        "shotgun.tui.app.perform_auto_update_async",
        lambda **kwargs: None
    )

    # Mock detect_installation_method to return "uv" (not pipx)
    monkeypatch.setattr(
        "shotgun.tui.app.detect_installation_method",
        lambda: "uv"
    )

    return MockConfigManager()


@pytest.mark.asyncio
async def test_app_starts_and_takes_screenshot(screenshots_dir, mock_config):
    """Test that the app starts and we can take a screenshot of the initial state.

    This demonstrates the most basic TUI automation: starting the app and
    capturing visual output.
    """
    app = ShotgunApp(no_update_check=True)

    async with app.run_test() as pilot:
        # Wait for the app to fully render
        await pilot.pause()

        # Take a screenshot of the initial state
        screenshot_path = screenshots_dir / "01_app_start.svg"
        pilot.app.save_screenshot(screenshot_path)

        # Verify screenshot was created
        assert screenshot_path.exists()
        assert screenshot_path.stat().st_size > 0

        # Verify we're on a screen (either splash or chat depending on timing)
        assert pilot.app.screen is not None


@pytest.mark.asyncio
async def test_simulate_key_presses(screenshots_dir, mock_config):
    """Test simulating keyboard input and capturing state changes.

    This demonstrates:
    - Pressing keys to navigate
    - Typing text into input fields
    - Taking screenshots before/after interactions
    """
    app = ShotgunApp(no_update_check=True)

    async with app.run_test() as pilot:
        # Wait for initial render
        await pilot.pause()

        # Take screenshot of initial state
        screenshot_path_before = screenshots_dir / "02_before_input.svg"
        pilot.app.save_screenshot(screenshot_path_before)

        # Simulate pressing Escape key (common navigation)
        await pilot.press("escape")
        await pilot.pause()

        # Take screenshot after key press
        screenshot_path_after = screenshots_dir / "03_after_escape.svg"
        pilot.app.save_screenshot(screenshot_path_after)

        assert screenshot_path_before.exists()
        assert screenshot_path_after.exists()


@pytest.mark.asyncio
async def test_query_widgets(mock_config):
    """Test querying and inspecting widgets in the TUI.

    This demonstrates:
    - Finding widgets by CSS selector
    - Inspecting widget properties
    - Verifying widget state
    """
    app = ShotgunApp(no_update_check=True)

    async with app.run_test() as pilot:
        # Wait for initial render
        await pilot.pause()

        # Verify the app is running and has a screen
        assert pilot.app.screen is not None

        # Verify we can access the current screen
        current_screen = pilot.app.screen
        assert current_screen is not None
        assert hasattr(current_screen, "id")

        # Verify the app has screens defined in SCREENS dict
        assert "chat" in app.SCREENS
        assert "provider_config" in app.SCREENS
        assert "model_picker" in app.SCREENS
        assert "directory_setup" in app.SCREENS
        assert "feedback" in app.SCREENS


@pytest.mark.asyncio
async def test_navigation_workflow(screenshots_dir, mock_config):
    """Test a complete navigation workflow with multiple screenshots.

    This demonstrates a realistic test scenario:
    1. Start the app
    2. Navigate through different states
    3. Capture screenshots at each step
    4. Verify expected behavior
    """
    app = ShotgunApp(no_update_check=True)

    async with app.run_test() as pilot:
        # Step 1: Initial load
        await pilot.pause()
        pilot.app.save_screenshot(
            screenshots_dir / "04_workflow_step1_initial.svg"
        )

        # Step 2: Wait for splash screen to finish (if present)
        await pilot.pause(0.5)
        pilot.app.save_screenshot(
            screenshots_dir / "05_workflow_step2_after_splash.svg"
        )

        # Step 3: Try to press a key
        await pilot.press("tab")
        await pilot.pause()
        pilot.app.save_screenshot(
            screenshots_dir / "06_workflow_step3_after_tab.svg"
        )

        # Verify all screenshots were created
        assert (screenshots_dir / "04_workflow_step1_initial.svg").exists()
        assert (screenshots_dir / "05_workflow_step2_after_splash.svg").exists()
        assert (screenshots_dir / "06_workflow_step3_after_tab.svg").exists()


@pytest.mark.asyncio
async def test_app_bindings(mock_config):
    """Test that keyboard bindings are configured correctly.

    This demonstrates:
    - Verifying keybindings exist
    - Testing that bound actions work
    """
    app = ShotgunApp(no_update_check=True)

    async with app.run_test() as pilot:
        await pilot.pause()

        # Verify the quit binding exists
        bindings = list(app.BINDINGS)
        assert len(bindings) > 0

        # Check that ctrl+c is bound to quit
        quit_binding = next(
            (b for b in bindings if "quit" in b.action),
            None
        )
        assert quit_binding is not None


# Helper function for future dynamic test generation
def generate_test_scenario(
    name: str,
    steps: list[dict],
    screenshots_dir: Path,
    mock_config,
) -> None:
    """Generate a test scenario dynamically.

    This is a template for creating dynamic test scripts. Each step can:
    - Press keys
    - Click elements
    - Take screenshots
    - Verify conditions

    Args:
        name: Test scenario name
        steps: List of dicts with keys: 'action', 'target', 'screenshot'
        screenshots_dir: Directory to save screenshots
        mock_config: Mock configuration fixture

    Example step:
        {
            'action': 'press',
            'target': 'tab',
            'screenshot': 'step1_after_tab.svg',
            'verify': lambda pilot: len(pilot.app.query("Screen")) > 0
        }
    """
    async def _run_scenario():
        app = ShotgunApp(no_update_check=True)

        async with app.run_test() as pilot:
            await pilot.pause()

            for i, step in enumerate(steps):
                action = step.get("action")
                target = step.get("target")
                screenshot = step.get("screenshot")
                verify = step.get("verify")

                # Execute action
                if action == "press":
                    await pilot.press(target)
                elif action == "click":
                    await pilot.click(target)
                elif action == "pause":
                    await pilot.pause(target)

                await pilot.pause()

                # Take screenshot if specified
                if screenshot:
                    pilot.app.save_screenshot(
                        screenshots_dir / screenshot
                    )

                # Run verification if specified
                if verify:
                    assert verify(pilot), f"Step {i+1} verification failed"

    return _run_scenario


# Example of how to use the dynamic test generator
@pytest.mark.asyncio
async def test_dynamic_scenario_example(screenshots_dir, mock_config):
    """Example of using the dynamic test generator."""
    steps = [
        {
            "action": "pause",
            "target": 0.2,
            "screenshot": "dynamic_01_start.svg",
        },
        {
            "action": "press",
            "target": "tab",
            "screenshot": "dynamic_02_after_tab.svg",
        },
        {
            "action": "press",
            "target": "escape",
            "screenshot": "dynamic_03_after_escape.svg",
            "verify": lambda pilot: pilot.app.screen is not None,
        },
    ]

    test_func = generate_test_scenario(
        "Dynamic Example",
        steps,
        screenshots_dir,
        mock_config,
    )

    await test_func()
