"""Utility module for checking mode progress in .shotgun directories."""

import random
from pathlib import Path

from shotgun.agents.agent_manager import AgentType
from shotgun.artifacts.models import AgentMode
from shotgun.utils.file_system_utils import get_shotgun_base_path


class ModeProgressChecker:
    """Checks progress across different agent modes based on .shotgun directory contents."""

    # Minimum file size in characters to consider a mode as "started"
    MIN_CONTENT_SIZE = 20

    def __init__(self, base_path: Path | None = None):
        """Initialize the progress checker.

        Args:
            base_path: Base path for .shotgun directory. Defaults to current directory.
        """
        self.base_path = base_path or get_shotgun_base_path()

    def has_mode_content(self, mode: AgentType | AgentMode) -> bool:
        """Check if a mode directory has meaningful content.

        Args:
            mode: The agent mode to check.

        Returns:
            True if the mode has at least one file with >20 characters.
        """
        mode_value = mode.value if hasattr(mode, "value") else str(mode)
        mode_path = self.base_path / mode_value

        if not mode_path.exists() or not mode_path.is_dir():
            return False

        # Check all subdirectories and files
        for item in mode_path.rglob("*"):
            if item.is_file() and not item.name.startswith("."):
                try:
                    content = item.read_text(encoding="utf-8")
                    # Check if file has meaningful content
                    if len(content.strip()) > self.MIN_CONTENT_SIZE:
                        return True
                except (OSError, UnicodeDecodeError):
                    # Skip files that can't be read
                    continue

        return False

    def get_next_suggested_mode(self, current_mode: AgentType) -> AgentType | None:
        """Get the next suggested mode based on current progress.

        Args:
            current_mode: The current agent mode.

        Returns:
            The next suggested mode, or None if no suggestion.
        """
        mode_order = [
            AgentType.RESEARCH,
            AgentType.SPECIFY,
            AgentType.TASKS,
            AgentType.EXPORT,
        ]

        try:
            current_index = mode_order.index(current_mode)
        except ValueError:
            # Mode not in standard order (e.g., PLAN mode)
            return None

        # Check if current mode has content
        if not self.has_mode_content(current_mode):
            # Current mode is empty, no suggestion for next mode
            return None

        # Get next mode in sequence
        if current_index < len(mode_order) - 1:
            return mode_order[current_index + 1]

        # Export mode cycles back to Research
        return mode_order[0]


class PlaceholderHints:
    """Manages dynamic placeholder hints for each mode based on progress."""

    # Placeholder variations for each mode and state
    HINTS = {
        # Research mode
        AgentType.RESEARCH: {
            False: [
                "Research a product or idea (SHIFT+TAB to cycle modes)",
                "What would you like to explore? Start your research journey here (SHIFT+TAB to switch modes)",
                "Dive into discovery mode - research anything that sparks curiosity (SHIFT+TAB for mode menu)",
                "Ready to investigate? Feed me your burning questions (SHIFT+TAB to explore other modes)",
                " 🔍 The research rabbit hole awaits! What shall we uncover? (SHIFT+TAB for mode carousel)",
            ],
            True: [
                "Research complete! SHIFT+TAB to move to Specify mode",
                "Great research! Time to specify (SHIFT+TAB to Specify mode)",
                "Research done! Ready to create specifications (SHIFT+TAB to Specify)",
                "Findings gathered! Move to specifications (SHIFT+TAB for Specify mode)",
                " 🎯 Research complete! Advance to Specify mode (SHIFT+TAB)",
            ],
        },
        # Specify mode
        AgentType.SPECIFY: {
            False: [
                "Create detailed specifications and requirements (SHIFT+TAB to switch modes)",
                "Define your project specifications here (SHIFT+TAB to navigate modes)",
                "Time to get specific - write comprehensive specs (SHIFT+TAB for mode options)",
                "Specification station: Document requirements and designs (SHIFT+TAB to change modes)",
                " 📋 Spec-tacular time! Let's architect your ideas (SHIFT+TAB for mode magic)",
            ],
            True: [
                "Specifications complete! SHIFT+TAB to create a Plan",
                "Specs ready! Time to plan (SHIFT+TAB to Plan mode)",
                "Requirements defined! Move to planning (SHIFT+TAB to Plan)",
                "Specifications done! Create your roadmap (SHIFT+TAB for Plan mode)",
                " 🚀 Specs complete! Advance to Plan mode (SHIFT+TAB)",
            ],
        },
        # Tasks mode
        AgentType.TASKS: {
            False: [
                "Create actionable tasks and work items (SHIFT+TAB to switch modes)",
                "Define your task list and action items (SHIFT+TAB to explore modes)",
                "Task creation time - build your work breakdown (SHIFT+TAB for mode selection)",
                "The task forge awaits - create doable chunks of work (SHIFT+TAB to change modes)",
                " ⚡ Task mode activated! Let's define what needs doing (SHIFT+TAB for mode journey)",
            ],
            True: [
                "Tasks complete! SHIFT+TAB to Export mode",
                "Task list ready! Time to export (SHIFT+TAB to Export)",
                "Work items defined! Export your artifacts (SHIFT+TAB to Export mode)",
                "Tasks done! Ship them out (SHIFT+TAB for Export mode)",
                " 🎉 Tasks complete! Advance to Export mode (SHIFT+TAB)",
            ],
        },
        # Export mode
        AgentType.EXPORT: {
            False: [
                "Export artifacts to Claude Code, Cursor, or other tools (SHIFT+TAB to switch modes)",
                "Ready to export! Send work to your favorite IDE (SHIFT+TAB to navigate modes)",
                "Export central - Ship artifacts to dev tools (SHIFT+TAB for mode options)",
                "Time to set your work free! Export anywhere (SHIFT+TAB to change modes)",
                " 🚢 Launch pad ready! Blast artifacts to Claude Code & beyond (SHIFT+TAB for mode menu)",
            ],
            True: [
                "Exports complete! SHIFT+TAB to start new Research cycle",
                "Artifacts exported! Begin fresh research (SHIFT+TAB to Research mode)",
                "Export done! Start a new journey (SHIFT+TAB for Research)",
                "Work shipped! New research awaits (SHIFT+TAB to Research mode)",
                " 🎊 Export complete! Loop back to Research (SHIFT+TAB)",
            ],
        },
        # Plan mode (special case - not in main flow)
        AgentType.PLAN: {
            False: [
                "Create comprehensive plans with milestones (SHIFT+TAB to switch modes)",
                "Plan your project roadmap and milestones (SHIFT+TAB to explore modes)",
                "Strategic planning mode - design your journey (SHIFT+TAB for mode options)",
                "The planning parlor - where ideas become roadmaps (SHIFT+TAB to navigate)",
                " 📅 Planning paradise! Chart your course to success (SHIFT+TAB for modes)",
            ],
            True: [
                "Plan complete! SHIFT+TAB to create Tasks",
                "Roadmap ready! Time for tasks (SHIFT+TAB to Tasks mode)",
                "Planning done! Break it down to tasks (SHIFT+TAB to Tasks)",
                "Strategy set! Move to task creation (SHIFT+TAB for Tasks mode)",
                " 🗺️ Plan complete! Advance to Tasks mode (SHIFT+TAB)",
            ],
        },
    }

    def __init__(self, base_path: Path | None = None):
        """Initialize the placeholder hints manager.

        Args:
            base_path: Base path for .shotgun directory.
        """
        self.progress_checker = ModeProgressChecker(base_path)
        self._last_hints: dict[str, str] = {}  # Cache last selected hint per mode

    def get_placeholder_for_mode(self, mode: AgentType, force_new: bool = False) -> str:
        """Get a random placeholder hint for the given mode based on progress.

        Args:
            mode: The current agent mode.
            force_new: If True, always select a new random hint.

        Returns:
            A randomly selected placeholder hint appropriate for the mode and progress.
        """
        # Determine if mode has content
        has_content = self.progress_checker.has_mode_content(mode)

        # Get hints for this mode and state
        mode_hints = self.HINTS.get(mode, {})
        state_hints = mode_hints.get(has_content, [])

        if not state_hints:
            # Fallback if mode not configured
            return (
                f"Type your message for {mode.value} mode (SHIFT+TAB to switch modes)"
            )

        # Cache key for this mode/state combination
        cache_key = f"{mode.value}_{has_content}"

        # If not forcing new and we have a cached hint, return it
        if not force_new and cache_key in self._last_hints:
            return self._last_hints[cache_key]

        # Select a random hint
        hint = random.choice(state_hints)  # noqa: S311 - random is fine for UI hints
        self._last_hints[cache_key] = hint

        return hint
