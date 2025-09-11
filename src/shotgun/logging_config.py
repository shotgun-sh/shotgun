"""Centralized logging configuration for Shotgun CLI."""

import logging
import os
import sys


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
        # Add color to levelname
        if record.levelname in self.COLORS:
            colored_levelname = (
                f"{self.COLORS[record.levelname]}{record.levelname}{self.RESET}"
            )
            record.levelname = colored_levelname

        return super().format(record)


def setup_logger(
    name: str,
    level: str = "INFO",
    verbose: bool = False,
    format_string: str | None = None,
) -> logging.Logger:
    """Set up a logger with consistent configuration.

    Args:
        name: Logger name (typically __name__)
        level: Base logging level ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
        verbose: If True, set level to DEBUG regardless of level parameter
        format_string: Custom format string, uses default if None

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers
    if logger.handlers:
        return logger

    # Set log level - check environment variable first, then verbose flag, then default
    env_level = os.getenv("SHOTGUN_LOG_LEVEL", "").upper()
    if env_level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
        log_level = env_level
    elif verbose:
        log_level = "DEBUG"
    else:
        log_level = level
    logger.setLevel(getattr(logging, log_level.upper()))

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))

    # Create formatter
    if format_string is None:
        format_string = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    formatter = ColoredFormatter(format_string, datefmt="%H:%M:%S")
    console_handler.setFormatter(formatter)

    # Add handler to logger
    logger.addHandler(console_handler)

    # Prevent propagation to avoid duplicate messages from parent loggers
    if name != "shotgun":  # Keep propagation for root logger
        logger.propagate = False

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with default configuration.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


def set_global_log_level(level: str) -> None:
    """Set log level for all shotgun loggers.

    Args:
        level: Log level ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
    """
    # Set level for all existing shotgun loggers
    for name, logger in logging.getLogger().manager.loggerDict.items():
        if isinstance(logger, logging.Logger) and name.startswith("shotgun"):
            logger.setLevel(getattr(logging, level.upper()))
            for handler in logger.handlers:
                handler.setLevel(getattr(logging, level.upper()))


def configure_root_logger(verbose: bool = False) -> None:
    """Configure the root shotgun logger.

    Args:
        verbose: Enable debug level logging
    """
    # Environment variable takes precedence over verbose flag
    env_level = os.getenv("SHOTGUN_LOG_LEVEL", "").upper()
    if env_level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
        level = env_level
    elif verbose:
        level = "DEBUG"
    else:
        level = "INFO"

    setup_logger("shotgun", level=level, verbose=verbose)
