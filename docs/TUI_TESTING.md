# TUI Testing Automation Guide

This guide demonstrates how to write automated tests for the Shotgun Textual TUI using Textual's built-in testing capabilities.

## Overview

Textual provides powerful testing tools that allow you to:
- Start the app in test mode without rendering to a terminal
- Simulate user interactions (key presses, clicks)
- Take SVG screenshots for visual verification
- Query and inspect widgets
- Verify app state and behavior

## Quick Start

See the proof-of-concept tests in `/test/unit/tui/test_app_automation.py` for complete examples.

### Basic Test Structure

```python
import pytest
from shotgun.tui.app import ShotgunApp

@pytest.mark.asyncio
async def test_example(screenshots_dir, mock_config):
    """Example test demonstrating TUI automation."""
    app = ShotgunApp(no_update_check=True)

    async with app.run_test() as pilot:
        # Wait for app to render
        await pilot.pause()

        # Take a screenshot
        pilot.app.save_screenshot(screenshots_dir / "example.svg")

        # Simulate key press
        await pilot.press("tab")
        await pilot.pause()

        # Verify app state
        assert pilot.app.screen is not None
```

## Key Concepts

### 1. Test Mode (`app.run_test()`)

The `run_test()` context manager starts the app in test mode, which:
- Doesn't render to a terminal
- Provides a `pilot` object for controlling the app
- Runs much faster than real-time
- Allows deterministic testing

```python
async with app.run_test() as pilot:
    # Your test code here
    pass
```

### 2. The Pilot Object

The `pilot` is your interface to control the app:

```python
# Pause to let app render
await pilot.pause()          # Pause for a moment
await pilot.pause(0.5)       # Pause for 0.5 seconds

# Simulate key presses
await pilot.press("escape")
await pilot.press("tab")
await pilot.press("enter")
await pilot.press("up", "down", "left", "right")

# Simulate clicks (requires selector)
await pilot.click("#my-button")
await pilot.click(".my-class")

# Access the app
app = pilot.app
current_screen = pilot.app.screen
```

### 3. Taking Screenshots

Screenshots are saved as SVG files that show the exact terminal rendering:

```python
# Save a screenshot
pilot.app.save_screenshot(path / "screenshot.svg")

# Screenshots are perfect for:
# - Visual regression testing
# - Debugging test failures
# - Documenting app behavior
# - Comparing before/after states
```

### 4. Querying Widgets

You can query and inspect widgets in the app:

```python
# Get the current screen
screen = pilot.app.screen

# Query widgets by CSS selector
buttons = pilot.app.query("Button")
input_field = pilot.app.query_one("#input")

# Check widget properties
assert screen is not None
assert hasattr(screen, "id")
```

## Test Fixtures

### `screenshots_dir`

A pytest fixture that provides a temporary directory for screenshots:

```python
@pytest.fixture(scope="session")
def screenshots_dir(tmp_path_factory):
    """Create a temporary directory for test screenshots."""
    screenshots_path = tmp_path_factory.mktemp("tui_screenshots")
    return screenshots_path
```

### `mock_config`

A pytest fixture that mocks the configuration to avoid requiring real API keys:

```python
@pytest.fixture
def mock_config(monkeypatch, tmp_path):
    """Mock configuration to avoid requiring real API keys or directories."""
    # See test_app_automation.py for full implementation
    # This fixture mocks:
    # - ConfigManager with test API keys
    # - Shotgun base path to temp directory
    # - Telemetry tracking
    # - Auto-update checks
    # - Installation method detection
```

## Common Test Patterns

### 1. Screenshot Workflow Tests

Test a user workflow by taking screenshots at each step:

```python
@pytest.mark.asyncio
async def test_user_workflow(screenshots_dir, mock_config):
    app = ShotgunApp(no_update_check=True)

    async with app.run_test() as pilot:
        # Step 1: Initial state
        await pilot.pause()
        pilot.app.save_screenshot(screenshots_dir / "01_start.svg")

        # Step 2: Navigate with tab
        await pilot.press("tab")
        await pilot.pause()
        pilot.app.save_screenshot(screenshots_dir / "02_after_tab.svg")

        # Step 3: Perform action
        await pilot.press("enter")
        await pilot.pause()
        pilot.app.save_screenshot(screenshots_dir / "03_after_action.svg")
```

### 2. Widget Inspection Tests

Verify that widgets are present and configured correctly:

```python
@pytest.mark.asyncio
async def test_widgets(mock_config):
    app = ShotgunApp(no_update_check=True)

    async with app.run_test() as pilot:
        await pilot.pause()

        # Verify screen exists
        assert pilot.app.screen is not None

        # Verify app configuration
        assert "chat" in app.SCREENS
        assert "provider_config" in app.SCREENS
```

### 3. Keyboard Binding Tests

Test that keybindings work as expected:

```python
@pytest.mark.asyncio
async def test_keybindings(mock_config):
    app = ShotgunApp(no_update_check=True)

    async with app.run_test() as pilot:
        await pilot.pause()

        # Verify bindings exist
        bindings = list(app.BINDINGS)
        assert len(bindings) > 0

        # Test specific binding
        quit_binding = next(
            (b for b in bindings if "quit" in b.action),
            None
        )
        assert quit_binding is not None
```

## Dynamic Test Generation

The test file includes a `generate_test_scenario()` helper for creating dynamic tests:

```python
steps = [
    {
        "action": "pause",
        "target": 0.2,
        "screenshot": "step1.svg",
    },
    {
        "action": "press",
        "target": "tab",
        "screenshot": "step2.svg",
        "verify": lambda pilot: pilot.app.screen is not None,
    },
]

test_func = generate_test_scenario(
    "My Test",
    steps,
    screenshots_dir,
    mock_config,
)

await test_func()
```

## Running Tests

```bash
# Run all TUI automation tests
uv run pytest test/unit/tui/test_app_automation.py -v

# Run a specific test
uv run pytest test/unit/tui/test_app_automation.py::test_app_starts_and_takes_screenshot -v

# Run with verbose output
uv run pytest test/unit/tui/test_app_automation.py -vv

# View screenshots after tests
find /tmp/pytest-of-$USER -name "*.svg" -type f
```

## Tips and Best Practices

### 1. Always Use `await pilot.pause()`

After any action (key press, click), always pause to let the app render:

```python
await pilot.press("tab")
await pilot.pause()  # IMPORTANT!
```

### 2. Use Descriptive Screenshot Names

Name screenshots to indicate what they show:

```python
# Good
pilot.app.save_screenshot(screenshots_dir / "01_initial_state.svg")
pilot.app.save_screenshot(screenshots_dir / "02_after_tab_navigation.svg")
pilot.app.save_screenshot(screenshots_dir / "03_modal_opened.svg")

# Less helpful
pilot.app.save_screenshot(screenshots_dir / "test1.svg")
pilot.app.save_screenshot(screenshots_dir / "test2.svg")
```

### 3. Test Real User Workflows

Design tests that mirror actual user interactions:

```python
# Good - tests a real workflow
async def test_create_and_send_message():
    # 1. User types a message
    # 2. User presses enter to send
    # 3. Verify message appears in history

# Less useful - tests arbitrary interactions
async def test_press_all_keys():
    # Press every key on the keyboard
```

### 4. Use Fixtures for Common Setup

Create fixtures for common test setup patterns:

```python
@pytest.fixture
async def app_with_chat_screen(mock_config):
    """Start app and navigate to chat screen."""
    app = ShotgunApp(no_update_check=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Navigate to chat screen...
        yield pilot
```

### 5. Verify Screenshots Were Created

Always assert that screenshots exist and have content:

```python
screenshot_path = screenshots_dir / "test.svg"
pilot.app.save_screenshot(screenshot_path)

assert screenshot_path.exists()
assert screenshot_path.stat().st_size > 0
```

## Limitations

1. **No LLM Interactions**: Tests don't have API keys, so they can't test actual LLM responses
2. **No External Services**: Tests mock external dependencies
3. **Timing Sensitive**: Some tests may need longer pauses for complex rendering
4. **Widget Queries**: Not all CSS selectors work the same in test mode

## Debugging Test Failures

### View Screenshots

When a test fails, check the screenshots to see what happened:

```bash
# Find all screenshots from the latest test run
find /tmp/pytest-of-$USER -name "*.svg" -type f | sort

# Open a screenshot in a browser
firefox /tmp/pytest-of-$USER/pytest-5/tui_screenshots0/01_app_start.svg
```

### Add More Screenshots

Add screenshots before and after the failing assertion:

```python
pilot.app.save_screenshot(screenshots_dir / "before_failure.svg")
# The failing code...
pilot.app.save_screenshot(screenshots_dir / "after_failure.svg")
```

### Use Longer Pauses

If the test is timing-sensitive, try longer pauses:

```python
# Short pause (default)
await pilot.pause()

# Longer pause
await pilot.pause(1.0)  # 1 second
```

## Resources

- [Textual Testing Guide](https://textual.textualize.io/guide/testing/)
- [Textual API Reference](https://textual.textualize.io/api/)
- [Pytest Documentation](https://docs.pytest.org/)
- Example tests: `/test/unit/tui/test_app_automation.py`

## Summary

Textual's testing framework makes it easy to write automated tests for TUI applications. The key features are:

1. **Test Mode**: Run the app without a terminal using `app.run_test()`
2. **Pilot**: Control the app with key presses, clicks, and pauses
3. **Screenshots**: Capture SVG screenshots for visual verification
4. **Widget Queries**: Inspect app state and widgets
5. **Async Support**: Tests work seamlessly with async/await

With these tools, you can write comprehensive test suites that verify your TUI behaves correctly, catch regressions, and document expected behavior.
