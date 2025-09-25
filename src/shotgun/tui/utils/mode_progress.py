"""Utility module for checking mode progress in .shotgun directories."""

import random
from pathlib import Path

from shotgun.agents.models import AgentType
from shotgun.utils.file_system_utils import get_shotgun_base_path


class ModeProgressChecker:
    """Checks progress across different agent modes based on file contents."""

    # Minimum file size in characters to consider a mode as "started"
    MIN_CONTENT_SIZE = 20

    # Map agent types to their corresponding files (in workflow order)
    MODE_FILES = {
        AgentType.RESEARCH: "research.md",
        AgentType.SPECIFY: "specification.md",
        AgentType.PLAN: "plan.md",
        AgentType.TASKS: "tasks.md",
        AgentType.EXPORT: "exports/",  # Export mode creates files in exports folder
    }

    def __init__(self, base_path: Path | None = None):
        """Initialize the progress checker.

        Args:
            base_path: Base path for .shotgun directory. Defaults to current directory.
        """
        self.base_path = base_path or get_shotgun_base_path()

    def has_mode_content(self, mode: AgentType) -> bool:
        """Check if a mode has meaningful content.

        Args:
            mode: The agent mode to check.

        Returns:
            True if the mode has a file with >20 characters.
        """
        if mode not in self.MODE_FILES:
            return False

        file_or_dir = self.MODE_FILES[mode]

        # Special handling for export mode (checks directory)
        if mode == AgentType.EXPORT:
            export_path = self.base_path / file_or_dir
            if export_path.exists() and export_path.is_dir():
                # Check if any files exist in exports directory
                for item in export_path.glob("*"):
                    if item.is_file() and not item.name.startswith("."):
                        try:
                            content = item.read_text(encoding="utf-8")
                            if len(content.strip()) > self.MIN_CONTENT_SIZE:
                                return True
                        except (OSError, UnicodeDecodeError):
                            continue
            return False

        # Check single file for other modes
        file_path = self.base_path / file_or_dir
        if not file_path.exists() or not file_path.is_file():
            return False

        try:
            content = file_path.read_text(encoding="utf-8")
            # Check if file has meaningful content
            return len(content.strip()) > self.MIN_CONTENT_SIZE
        except (OSError, UnicodeDecodeError):
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
                "Break down your project into actionable tasks (SHIFT+TAB for modes)",
                "Task creation time! Define your implementation steps (SHIFT+TAB to switch)",
                "Ready to get tactical? Create your task list (SHIFT+TAB for mode options)",
                "Task command center: Organize your work items (SHIFT+TAB to navigate)",
                " ✅ Task mode activated! Break it down into bite-sized pieces (SHIFT+TAB)",
            ],
            True: [
                "Tasks defined! Ready to export or cycle back (SHIFT+TAB)",
                "Task list complete! Export your work (SHIFT+TAB to Export)",
                "All tasks created! Time to export (SHIFT+TAB for Export mode)",
                "Implementation plan ready! Export everything (SHIFT+TAB to Export)",
                " 🎊 Tasks complete! Export your masterpiece (SHIFT+TAB)",
            ],
        },
        # Export mode
        AgentType.EXPORT: {
            False: [
                "Export your complete project documentation (SHIFT+TAB for modes)",
                "Ready to package everything? Export time! (SHIFT+TAB to switch)",
                "Export station: Generate deliverables (SHIFT+TAB for mode menu)",
                "Time to share your work! Export documents (SHIFT+TAB to navigate)",
                " 📦 Export mode! Package and share your creation (SHIFT+TAB)",
            ],
            True: [
                "Exported! Start new research or continue refining (SHIFT+TAB)",
                "Export complete! New cycle begins (SHIFT+TAB to Research)",
                "All exported! Ready for another round (SHIFT+TAB for Research)",
                "Documents exported! Start fresh (SHIFT+TAB to Research mode)",
                " 🎉 Export complete! Begin a new adventure (SHIFT+TAB)",
            ],
        },
        # Plan mode
        AgentType.PLAN: {
            False: [
                "Create a strategic plan for your project (SHIFT+TAB for modes)",
                "Planning phase: Map out your roadmap (SHIFT+TAB to switch)",
                "Time to strategize! Create your project plan (SHIFT+TAB for options)",
                "Plan your approach and milestones (SHIFT+TAB to navigate)",
                " 🗺️ Plan mode! Chart your course to success (SHIFT+TAB)",
            ],
            True: [
                "Plan complete! Move to Tasks mode (SHIFT+TAB)",
                "Strategy ready! Time for tasks (SHIFT+TAB to Tasks mode)",
                "Roadmap done! Create task list (SHIFT+TAB for Tasks)",
                "Planning complete! Break into tasks (SHIFT+TAB to Tasks)",
                " ⚡ Plan ready! Advance to Tasks mode (SHIFT+TAB)",
            ],
        },
    }

    def __init__(self, base_path: Path | None = None):
        """Initialize placeholder hints with progress checker.

        Args:
            base_path: Base path for checking progress. Defaults to current directory.
        """
        self.progress_checker = ModeProgressChecker(base_path)
        self._cached_hints: dict[tuple[AgentType, bool], str] = {}
        self._hint_indices: dict[tuple[AgentType, bool], int] = {}

    def get_hint(self, current_mode: AgentType, force_refresh: bool = False) -> str:
        """Get a dynamic hint based on current mode and progress.

        Args:
            current_mode: The current agent mode.
            force_refresh: Force recalculation of progress state.

        Returns:
            A contextual hint string for the placeholder.
        """
        # Default hint if mode not configured
        if current_mode not in self.HINTS:
            return f"Enter your {current_mode.value} mode prompt (SHIFT+TAB to switch modes)"

        # Determine if mode has content
        has_content = self.progress_checker.has_mode_content(current_mode)

        # Get hint variations for this mode and state
        hints_list = self.HINTS[current_mode][has_content]

        # Cache key for this mode and state
        cache_key = (current_mode, has_content)

        # Force refresh or first time
        if force_refresh or cache_key not in self._cached_hints:
            # Initialize index for this cache key if not exists
            if cache_key not in self._hint_indices:
                self._hint_indices[cache_key] = random.randint(0, len(hints_list) - 1)  # noqa: S311

            # Get hint at current index
            hint_index = self._hint_indices[cache_key]
            self._cached_hints[cache_key] = hints_list[hint_index]

        return self._cached_hints[cache_key]

    def get_placeholder_for_mode(self, current_mode: AgentType) -> str:
        """Get placeholder text for a given mode.

        This is an alias for get_hint() to maintain compatibility.

        Args:
            current_mode: The current agent mode.

        Returns:
            A contextual hint string for the placeholder.
        """
        return self.get_hint(current_mode)
