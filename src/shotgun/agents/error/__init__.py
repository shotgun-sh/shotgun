"""Agent error handling module.

This module provides error classification, message generation, and protocol
definitions for consistent error handling across TUI and CLI interfaces.
"""

from shotgun.agents.error.classifier import AgentErrorClassifier, ErrorType
from shotgun.agents.error.messages import ErrorMessageGenerator
from shotgun.agents.error.models import AgentErrorContext, ErrorMessage
from shotgun.agents.error.protocol import AgentErrorHandler

__all__ = [
    "AgentErrorClassifier",
    "AgentErrorContext",
    "AgentErrorHandler",
    "ErrorMessage",
    "ErrorMessageGenerator",
    "ErrorType",
]
