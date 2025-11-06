"""Unit tests for Sentry error filtering."""

from pathlib import Path
from unittest.mock import patch

import pytest

from shotgun.exceptions import ContextSizeLimitExceeded, ErrorNotPickedUpBySentry


@pytest.fixture
def mock_settings():
    """Mock settings with Sentry DSN."""
    with patch("shotgun.sentry_telemetry.settings") as mock:
        mock.telemetry.sentry_dsn = "https://fake@sentry.io/123"
        yield mock


def test_before_send_filters_error_not_picked_up_by_sentry(mock_settings):
    """before_send should filter out ErrorNotPickedUpBySentry exceptions."""
    from shotgun.sentry_telemetry import setup_sentry_observability

    # Mock sentry_sdk inside the function
    with (
        patch("sentry_sdk.is_initialized", return_value=False),
        patch("sentry_sdk.init") as mock_init,
        patch("sentry_sdk.set_user"),
    ):
        # Setup Sentry
        setup_sentry_observability()

        # Get the before_send function that was passed to sentry_sdk.init
        init_call = mock_init.call_args
        before_send = init_call.kwargs["before_send"]

        # Create a mock event and hint with ErrorNotPickedUpBySentry
        event = {"exception": {"values": [{"type": "ErrorNotPickedUpBySentry"}]}}
        error = ErrorNotPickedUpBySentry("test error")
        hint = {"exc_info": (type(error), error, None)}

        # Call before_send
        result = before_send(event, hint)

        # Should return None to filter out the event
        assert result is None


def test_before_send_filters_context_size_limit_exceeded(mock_settings):
    """before_send should filter out ContextSizeLimitExceeded exceptions."""
    from shotgun.sentry_telemetry import setup_sentry_observability

    with (
        patch("sentry_sdk.is_initialized", return_value=False),
        patch("sentry_sdk.init") as mock_init,
        patch("sentry_sdk.set_user"),
    ):
        # Setup Sentry
        setup_sentry_observability()

        # Get the before_send function
        init_call = mock_init.call_args
        before_send = init_call.kwargs["before_send"]

        # Create a mock event and hint with ContextSizeLimitExceeded
        event = {"exception": {"values": [{"type": "ContextSizeLimitExceeded"}]}}
        error = ContextSizeLimitExceeded(model_name="test-model", max_tokens=1000)
        hint = {"exc_info": (type(error), error, None)}

        # Call before_send
        result = before_send(event, hint)

        # Should return None to filter out the event
        assert result is None


def test_before_send_allows_other_exceptions(mock_settings):
    """before_send should allow other exceptions through."""
    from shotgun.sentry_telemetry import setup_sentry_observability

    with (
        patch("sentry_sdk.is_initialized", return_value=False),
        patch("sentry_sdk.init") as mock_init,
        patch("sentry_sdk.set_user"),
    ):
        # Setup Sentry
        setup_sentry_observability()

        # Get the before_send function
        init_call = mock_init.call_args
        before_send = init_call.kwargs["before_send"]

        # Create a mock event and hint with a regular exception
        event = {"exception": {"values": [{"type": "ValueError"}]}}
        error = ValueError("test error")
        hint = {"exc_info": (type(error), error, None)}

        # Call before_send
        result = before_send(event, hint)

        # Should return the event (not filtered)
        assert result == event


def test_before_send_handles_missing_exc_info(mock_settings):
    """before_send should handle hints without exc_info."""
    from shotgun.sentry_telemetry import setup_sentry_observability

    with (
        patch("sentry_sdk.is_initialized", return_value=False),
        patch("sentry_sdk.init") as mock_init,
        patch("sentry_sdk.set_user"),
    ):
        # Setup Sentry
        setup_sentry_observability()

        # Get the before_send function
        init_call = mock_init.call_args
        before_send = init_call.kwargs["before_send"]

        # Create a mock event and hint without exc_info
        event = {"exception": {"values": [{"type": "Exception"}]}}
        hint = {}  # No exc_info

        # Call before_send
        result = before_send(event, hint)

        # Should return the event (not filtered)
        assert result == event


def test_before_send_is_configured(mock_settings):
    """Sentry should be initialized with before_send hook."""
    from shotgun.sentry_telemetry import setup_sentry_observability

    with (
        patch("sentry_sdk.is_initialized", return_value=False),
        patch("sentry_sdk.init") as mock_init,
        patch("sentry_sdk.set_user"),
    ):
        # Setup Sentry
        setup_sentry_observability()

        # Verify sentry_sdk.init was called with before_send
        mock_init.assert_called_once()
        init_call = mock_init.call_args
        assert "before_send" in init_call.kwargs
        assert callable(init_call.kwargs["before_send"])


def test_server_name_is_empty(mock_settings):
    """Sentry should be initialized with empty server_name to prevent hostname leakage."""
    from shotgun.sentry_telemetry import setup_sentry_observability

    with (
        patch("sentry_sdk.is_initialized", return_value=False),
        patch("sentry_sdk.init") as mock_init,
        patch("sentry_sdk.set_user"),
    ):
        # Setup Sentry
        setup_sentry_observability()

        # Verify sentry_sdk.init was called with server_name=""
        mock_init.assert_called_once()
        init_call = mock_init.call_args
        assert "server_name" in init_call.kwargs
        assert init_call.kwargs["server_name"] == ""


def test_scrub_path_removes_home_directory():
    """_scrub_path should replace home directory with ~."""
    from shotgun.sentry_telemetry import _scrub_path

    home = Path.home()
    test_path = str(home / "projects" / "myproject" / "file.py")

    result = _scrub_path(test_path)

    assert result.startswith("~/")
    assert "projects/myproject/file.py" in result
    assert str(home) not in result


def test_scrub_path_removes_cwd():
    """_scrub_path should make paths relative to current working directory."""
    from shotgun.sentry_telemetry import _scrub_path

    cwd = Path.cwd()
    test_path = str(cwd / "src" / "module" / "file.py")

    result = _scrub_path(test_path)

    assert result == "src/module/file.py"
    assert str(cwd) not in result


def test_scrub_path_handles_absolute_paths_outside_cwd_and_home():
    """_scrub_path should return just filename for absolute paths outside cwd and home."""
    from shotgun.sentry_telemetry import _scrub_path

    test_path = "/opt/system/lib/file.py"

    result = _scrub_path(test_path)

    assert result == "file.py"


def test_scrub_path_handles_relative_paths():
    """_scrub_path should leave relative paths unchanged."""
    from shotgun.sentry_telemetry import _scrub_path

    test_path = "src/module/file.py"

    result = _scrub_path(test_path)

    assert result == test_path


def test_scrub_path_handles_empty_string():
    """_scrub_path should handle empty strings."""
    from shotgun.sentry_telemetry import _scrub_path

    result = _scrub_path("")

    assert result == ""


def test_before_send_scrubs_stack_trace_paths(mock_settings):
    """before_send should scrub file paths from stack traces."""
    from shotgun.sentry_telemetry import setup_sentry_observability

    with (
        patch("sentry_sdk.is_initialized", return_value=False),
        patch("sentry_sdk.init") as mock_init,
        patch("sentry_sdk.set_user"),
    ):
        # Setup Sentry
        setup_sentry_observability()

        # Get the before_send function
        init_call = mock_init.call_args
        before_send = init_call.kwargs["before_send"]

        # Create event with absolute paths
        cwd = Path.cwd()
        abs_path = str(cwd / "src" / "module" / "file.py")

        event = {
            "exception": {
                "values": [
                    {
                        "stacktrace": {
                            "frames": [
                                {
                                    "abs_path": abs_path,
                                    "filename": abs_path,
                                }
                            ]
                        }
                    }
                ]
            }
        }
        hint = {}

        # Call before_send
        result = before_send(event, hint)

        # Verify paths were scrubbed
        frame = result["exception"]["values"][0]["stacktrace"]["frames"][0]
        assert frame["abs_path"] == "src/module/file.py"
        assert frame["filename"] == "src/module/file.py"
        assert str(cwd) not in frame["abs_path"]


def test_before_send_scrubs_local_variables(mock_settings):
    """before_send should scrub paths from local variables in stack traces."""
    from shotgun.sentry_telemetry import setup_sentry_observability

    with (
        patch("sentry_sdk.is_initialized", return_value=False),
        patch("sentry_sdk.init") as mock_init,
        patch("sentry_sdk.set_user"),
    ):
        # Setup Sentry
        setup_sentry_observability()

        # Get the before_send function
        init_call = mock_init.call_args
        before_send = init_call.kwargs["before_send"]

        # Create event with local variables containing paths
        home = Path.home()
        sensitive_path = str(home / "username" / "project" / "data.json")

        event = {
            "exception": {
                "values": [
                    {
                        "stacktrace": {
                            "frames": [
                                {
                                    "abs_path": "file.py",
                                    "filename": "file.py",
                                    "vars": {
                                        "config_file": sensitive_path,
                                        "counter": 42,  # Non-string should be unchanged
                                    },
                                }
                            ]
                        }
                    }
                ]
            }
        }
        hint = {}

        # Call before_send
        result = before_send(event, hint)

        # Verify path was scrubbed from variables
        frame = result["exception"]["values"][0]["stacktrace"]["frames"][0]
        assert frame["vars"]["config_file"].startswith("~/")
        assert str(home) not in frame["vars"]["config_file"]
        assert frame["vars"]["counter"] == 42  # Non-string unchanged


def test_before_send_removes_server_name_from_event(mock_settings):
    """before_send should remove server_name from events."""
    from shotgun.sentry_telemetry import setup_sentry_observability

    with (
        patch("sentry_sdk.is_initialized", return_value=False),
        patch("sentry_sdk.init") as mock_init,
        patch("sentry_sdk.set_user"),
    ):
        # Setup Sentry
        setup_sentry_observability()

        # Get the before_send function
        init_call = mock_init.call_args
        before_send = init_call.kwargs["before_send"]

        # Create event with server_name
        event = {
            "server_name": "johns-macbook.local",
            "exception": {"values": []},
        }
        hint = {}

        # Call before_send
        result = before_send(event, hint)

        # Verify server_name was scrubbed
        assert result["server_name"] == ""


def test_before_send_removes_cwd_from_runtime_context(mock_settings):
    """before_send should remove CWD from runtime context."""
    from shotgun.sentry_telemetry import setup_sentry_observability

    with (
        patch("sentry_sdk.is_initialized", return_value=False),
        patch("sentry_sdk.init") as mock_init,
        patch("sentry_sdk.set_user"),
    ):
        # Setup Sentry
        setup_sentry_observability()

        # Get the before_send function
        init_call = mock_init.call_args
        before_send = init_call.kwargs["before_send"]

        # Create event with runtime context containing CWD
        event = {
            "contexts": {
                "runtime": {
                    "name": "python",
                    "version": "3.11",
                    "cwd": "/home/username/sensitive/path",
                }
            }
        }
        hint = {}

        # Call before_send
        result = before_send(event, hint)

        # Verify CWD was removed
        assert "cwd" not in result["contexts"]["runtime"]
        assert result["contexts"]["runtime"]["name"] == "python"  # Other fields preserved


def test_before_send_scrubs_sys_argv(mock_settings):
    """before_send should scrub paths from sys.argv in runtime context."""
    from shotgun.sentry_telemetry import setup_sentry_observability

    with (
        patch("sentry_sdk.is_initialized", return_value=False),
        patch("sentry_sdk.init") as mock_init,
        patch("sentry_sdk.set_user"),
    ):
        # Setup Sentry
        setup_sentry_observability()

        # Get the before_send function
        init_call = mock_init.call_args
        before_send = init_call.kwargs["before_send"]

        # Create event with runtime context containing sys.argv with full path
        cwd = Path.cwd()
        sensitive_path = str(cwd / ".venv" / "bin" / "shotgun")

        event = {
            "contexts": {
                "runtime": {
                    "name": "python",
                    "version": "3.11",
                    "sys.argv": [sensitive_path, "--debug", "arg2"],
                }
            }
        }
        hint = {}

        # Call before_send
        result = before_send(event, hint)

        # Verify sys.argv was scrubbed
        argv = result["contexts"]["runtime"]["sys.argv"]
        assert argv[0] == ".venv/bin/shotgun"  # Path scrubbed to relative
        assert argv[1] == "--debug"  # Non-path arguments unchanged
        assert argv[2] == "arg2"  # Non-path arguments unchanged
        assert str(cwd) not in argv[0]  # CWD removed
