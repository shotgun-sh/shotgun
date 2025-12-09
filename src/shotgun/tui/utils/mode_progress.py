"""Utility module for checking mode progress in .shotgun directories."""

import random
from pathlib import Path

import aiofiles

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

    async def has_mode_content(self, mode: AgentType) -> bool:
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
                            async with aiofiles.open(item, encoding="utf-8") as f:
                                content = await f.read()
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
            async with aiofiles.open(file_path, encoding="utf-8") as f:
                content = await f.read()
            # Check if file has meaningful content
            return len(content.strip()) > self.MIN_CONTENT_SIZE
        except (OSError, UnicodeDecodeError):
            return False

    async def get_next_suggested_mode(
        self, current_mode: AgentType
    ) -> AgentType | None:
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
        if not await self.has_mode_content(current_mode):
            # Current mode is empty, no suggestion for next mode
            return None

        # Get next mode in sequence
        if current_index < len(mode_order) - 1:
            return mode_order[current_index + 1]

        # Export mode cycles back to Research
        return mode_order[0]


class PlaceholderHints:
    """Manages dynamic placeholder hints for the Router agent."""

    # Placeholder variations for Router mode
    HINTS = {
        AgentType.ROUTER: {
            False: [
                "What would you like to work on? (SHIFT+TAB to toggle Planning/Drafting)",
                "Ask me to research, plan, or implement anything (SHIFT+TAB toggles mode)",
                "Describe your goal and I'll help break it down (SHIFT+TAB for mode toggle)",
                "Ready to help with research, specs, plans, or tasks (SHIFT+TAB toggles mode)",
                "Tell me what you need - I'll coordinate the work (SHIFT+TAB for Planning/Drafting)",
            ],
            True: [
                "Continue working or start something new (SHIFT+TAB toggles mode)",
                "What's next? (SHIFT+TAB to toggle Planning/Drafting)",
                "Ready for the next task (SHIFT+TAB toggles Planning/Drafting)",
                "Let's keep going! (SHIFT+TAB to toggle mode)",
                "What else can I help with? (SHIFT+TAB for mode toggle)",
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
        # Always use Router hints since Router is the only user-facing agent
        mode_key = AgentType.ROUTER

        # Default hint if mode not configured
        if mode_key not in self.HINTS:
            return "Enter your prompt (SHIFT+TAB to toggle Planning/Drafting mode)"

        # For placeholder text, we default to "no content" state (initial hints)
        # This avoids async file system checks in the UI rendering path
        has_content = False

        # Get hint variations for this mode and state
        hints_list = self.HINTS[mode_key][has_content]

        # Cache key for this mode and state
        cache_key = (mode_key, has_content)

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
