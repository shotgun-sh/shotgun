"""Datetime utilities for consistent datetime formatting across the application."""

from datetime import datetime

from pydantic import BaseModel, Field


class DateTimeContext(BaseModel):
    """Structured datetime context with timezone information.

    This model provides consistently formatted datetime information
    for use in prompts, templates, and UI display.

    Attributes:
        datetime_formatted: Human-readable datetime string
        timezone_name: Short timezone name (e.g., "PST", "UTC")
        utc_offset: UTC offset formatted with colon (e.g., "UTC-08:00")

    Example:
        >>> dt_context = get_datetime_context()
        >>> print(dt_context.datetime_formatted)
        'Monday, January 13, 2025 at 3:45:30 PM'
        >>> print(dt_context.timezone_name)
        'PST'
        >>> print(dt_context.utc_offset)
        'UTC-08:00'
    """

    datetime_formatted: str = Field(
        description="Human-readable datetime string in format: 'Day, Month DD, YYYY at HH:MM:SS AM/PM'"
    )
    timezone_name: str = Field(description="Short timezone name (e.g., PST, EST, UTC)")
    utc_offset: str = Field(
        description="UTC offset formatted with colon (e.g., UTC-08:00, UTC+05:30)"
    )


def get_datetime_context() -> DateTimeContext:
    """Get formatted datetime context with timezone information.

    Returns a Pydantic model containing consistently formatted datetime
    information suitable for use in prompts and templates.

    Returns:
        DateTimeContext: Structured datetime context with formatted strings

    Example:
        >>> dt_context = get_datetime_context()
        >>> dt_context.datetime_formatted
        'Monday, January 13, 2025 at 3:45:30 PM'
        >>> dt_context.timezone_name
        'PST'
        >>> dt_context.utc_offset
        'UTC-08:00'
    """
    # Get current datetime with timezone information
    now = datetime.now().astimezone()

    # Format datetime in plain English
    # Example: "Monday, January 13, 2025 at 3:45:30 PM"
    datetime_formatted = now.strftime("%A, %B %d, %Y at %I:%M:%S %p")

    # Get timezone name and UTC offset
    # Example: "PST" and "UTC-08:00"
    timezone_name = now.strftime("%Z")
    utc_offset = now.strftime("%z")  # Format: +0800 or -0500

    # Reformat UTC offset to include colon: +08:00 or -05:00
    utc_offset_formatted = (
        f"UTC{utc_offset[:3]}:{utc_offset[3:]}" if utc_offset else "UTC"
    )

    return DateTimeContext(
        datetime_formatted=datetime_formatted,
        timezone_name=timezone_name,
        utc_offset=utc_offset_formatted,
    )
