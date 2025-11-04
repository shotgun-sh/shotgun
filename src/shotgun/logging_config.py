"""Centralized logging configuration for Shotgun CLI."""

import logging
import logging.handlers
import sys
from datetime import datetime, timezone
from pathlib import Path

from shotgun.settings import settings
from shotgun.utils.env_utils import is_truthy

# Generate a single timestamp for this run to be used across all loggers
_RUN_TIMESTAMP = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def get_log_directory() -> Path:
    """Get the log directory path, creating it if necessary.

    Returns:
        Path to log directory (~/.shotgun-sh/logs/)
    """
    # Lazy import to avoid circular dependency
    from shotgun.utils.file_system_utils import get_shotgun_home

    log_dir = get_shotgun_home() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for different log levels."""

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        # Create a copy of the record to avoid modifying the original
        record = logging.makeLogRecord(record.__dict__)

        # Add color to levelname
        if record.levelname in self.COLORS:
            colored_levelname = (
                f"{self.COLORS[record.levelname]}{record.levelname}{self.RESET}"
            )
            record.levelname = colored_levelname

        return super().format(record)


def setup_logger(
    name: str,
    format_string: str | None = None,
) -> logging.Logger:
    """Set up a logger with consistent configuration.

    Args:
        name: Logger name (typically __name__)
        format_string: Custom format string, uses default if None

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Check if we already have a file handler
    has_file_handler = any(isinstance(h, logging.FileHandler) for h in logger.handlers)

    # If we already have a file handler, just return the logger
    if has_file_handler:
        return logger

    # Get log level from settings (already validated and uppercased)
    log_level = settings.logging.log_level

    logger.setLevel(getattr(logging, log_level))

    # Default format string
    if format_string is None:
        format_string = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    # Check if this is a dev build with Logfire enabled
    is_logfire_dev_build = False
    try:
        from shotgun.build_constants import IS_DEV_BUILD, LOGFIRE_ENABLED

        if IS_DEV_BUILD and is_truthy(LOGFIRE_ENABLED):
            is_logfire_dev_build = True
            # This debug message will only appear in file logs
            logger.debug("Console logging disabled for Logfire dev build")
    except ImportError:
        # No build constants available (local development)
        pass

    # Check if console logging is enabled (default: off)
    # Force console logging OFF if Logfire is enabled in dev build
    console_logging_enabled = (
        settings.logging.logging_to_console and not is_logfire_dev_build
    )

    if console_logging_enabled:
        # Create console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, log_level))

        # Use colored formatter for console
        console_formatter = ColoredFormatter(format_string, datefmt="%H:%M:%S")
        console_handler.setFormatter(console_formatter)

        # Add handler to logger
        logger.addHandler(console_handler)

    # Check if file logging is enabled (default: on)
    file_logging_enabled = settings.logging.logging_to_file

    if file_logging_enabled:
        try:
            # Create file handler with ISO8601 timestamp for each run
            log_dir = get_log_directory()
            log_file = log_dir / f"shotgun-{_RUN_TIMESTAMP}.log"

            # Use regular FileHandler - each run gets its own isolated log file
            file_handler = logging.FileHandler(
                filename=log_file,
                encoding="utf-8",
            )

            file_handler.setLevel(getattr(logging, log_level))

            # Use standard formatter for file (no colors)
            file_formatter = logging.Formatter(
                format_string, datefmt="%Y-%m-%d %H:%M:%S"
            )
            file_handler.setFormatter(file_formatter)

            # Add handler to logger
            logger.addHandler(file_handler)
        except Exception as e:
            # If file logging fails, log to stderr but don't crash
            print(f"Warning: Could not set up file logging: {e}", file=sys.stderr)

    # Prevent propagation to avoid duplicate messages from parent loggers
    if name != "shotgun":  # Keep propagation for root logger
        logger.propagate = False

    return logger


def get_early_logger(name: str) -> logging.Logger:
    """Get a logger with NullHandler for early initialization.

    Use this for loggers created at module import time, before
    configure_root_logger() is called. The NullHandler prevents
    Python from automatically adding a StreamHandler when WARNING
    or ERROR messages are logged.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger with NullHandler attached
    """
    logger = logging.getLogger(name)
    # Only add NullHandler if no handlers exist
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())
    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with default configuration.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance with handlers configured
    """
    logger = logging.getLogger(name)

    # Check if we have a file handler already
    has_file_handler = any(isinstance(h, logging.FileHandler) for h in logger.handlers)

    # If no file handler, set up the logger (will add file handler)
    if not has_file_handler:
        return setup_logger(name)

    return logger


def set_global_log_level(level: str) -> None:
    """Set log level for all shotgun loggers.

    Args:
        level: Log level ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
    """
    # Set level for all existing shotgun loggers
    for name, logger in logging.getLogger().manager.loggerDict.items():
        if isinstance(logger, logging.Logger) and name.startswith("shotgun"):
            logger.setLevel(getattr(logging, level.upper()))
            # Only set handler levels if handlers exist
            for handler in logger.handlers:
                handler.setLevel(getattr(logging, level.upper()))


def configure_root_logger() -> None:
    """Configure the root shotgun logger."""
    # Always set up the root logger to ensure file handler is added
    setup_logger("shotgun")

    # Also ensure main module gets configured
    setup_logger("__main__")
