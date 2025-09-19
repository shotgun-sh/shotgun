"""Utilities for artifact system."""

from .models import AgentMode

# Error message templates
INVALID_AGENT_MODE_MSG = (
    "Invalid agent mode '{mode}'. Valid modes: research, plan, tasks, specify"
)
VALIDATION_ERROR_MSG = "Validation error: {error}"

# Valid modes list for error messages
VALID_AGENT_MODES = ["research", "plan", "tasks", "specify"]


def parse_agent_mode_string(mode_str: str) -> AgentMode:
    """Parse agent mode string to AgentMode enum.

    Args:
        mode_str: String representation of agent mode

    Returns:
        AgentMode enum value

    Raises:
        ValueError: If mode_str is not a valid agent mode
    """
    try:
        return AgentMode(mode_str.lower())
    except ValueError as e:
        if "not a valid enumeration member" in str(e):
            raise ValueError(INVALID_AGENT_MODE_MSG.format(mode=mode_str)) from e
        raise ValueError(VALIDATION_ERROR_MSG.format(error=str(e))) from e


def generate_artifact_name(artifact_id: str) -> str:
    """Generate human-readable name from artifact ID.

    Args:
        artifact_id: Artifact identifier (slug format)

    Returns:
        Human-readable name
    """
    return artifact_id.replace("-", " ").title()


def format_agent_error_message(agent_mode: str, error: Exception) -> str:
    """Format error message for agent tools.

    Args:
        agent_mode: Agent mode string that caused the error
        error: The exception that occurred

    Returns:
        Formatted error message
    """
    if "not a valid enumeration member" in str(error):
        return INVALID_AGENT_MODE_MSG.format(mode=agent_mode)
    else:
        return VALIDATION_ERROR_MSG.format(error=str(error))


def handle_agent_mode_parsing(agent_mode: str) -> tuple[AgentMode | None, str | None]:
    """Handle agent mode parsing with error handling.

    Args:
        agent_mode: Agent mode string to parse

    Returns:
        Tuple of (parsed_mode, error_message). If parsing succeeds,
        error_message is None. If parsing fails, parsed_mode is None.
    """
    try:
        return parse_agent_mode_string(agent_mode), None
    except ValueError as e:
        return None, str(e)
