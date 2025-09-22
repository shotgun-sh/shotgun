"""Utilities for working with environment variables."""


def is_truthy(value: str | None) -> bool:
    """Check if a string value represents true.

    Args:
        value: String value to check (e.g., from environment variable)

    Returns:
        True if value is "true", "1", or "yes" (case-insensitive)
        False otherwise (including None, empty string, or any other value)
    """
    if not value:
        return False
    return value.lower() in ("true", "1", "yes")


def is_falsy(value: str | None) -> bool:
    """Check if a string value explicitly represents false.

    Args:
        value: String value to check (e.g., from environment variable)

    Returns:
        True if value is "false", "0", or "no" (case-insensitive)
        False otherwise (including None, empty string, or any other value)

    Note:
        This is NOT the opposite of is_truthy(). A value can be neither
        truthy nor falsy (e.g., None, "", "maybe", etc.)
    """
    if not value:
        return False
    return value.lower() in ("false", "0", "no")
