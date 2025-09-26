"""Custom message types for Shotgun agents.

This module defines specialized SystemPromptPart subclasses to distinguish
between different types of system prompts in the agent pipeline.
"""

from dataclasses import dataclass, field

from pydantic_ai.messages import SystemPromptPart

from shotgun.agents.models import AgentType


@dataclass
class AgentSystemPrompt(SystemPromptPart):
    """System prompt containing the main agent instructions.

    This is the primary system prompt that defines the agent's role,
    capabilities, and behavior. It should be preserved during compaction.
    """

    prompt_type: str = "agent"
    agent_mode: AgentType | None = field(default=None)


@dataclass
class SystemStatusPrompt(SystemPromptPart):
    """System prompt containing current system status information.

    This includes table of contents, available files, and other contextual
    information about the current state. Only the most recent status should
    be preserved during compaction.
    """

    prompt_type: str = "status"
