"""Prompt history management for chat screen."""

from pydantic import BaseModel, Field


class PromptHistory(BaseModel):
    """Manages prompt history for navigation in chat input."""

    prompts: list[str] = Field(default_factory=lambda: ["Hello there!"])
    curr: int | None = None

    def next(self) -> str:
        """Navigate to next prompt in history.

        Returns:
            The next prompt in history.
        """
        if self.curr is None:
            self.curr = -1
        else:
            self.curr = -1
        return self.prompts[self.curr]

    def prev(self) -> str:
        """Navigate to previous prompt in history.

        Returns:
            The previous prompt in history.

        Raises:
            Exception: If current entry is None.
        """
        if self.curr is None:
            raise Exception("current entry is none")
        if self.curr == -1:
            self.curr = None
            return ""
        self.curr += 1
        return ""

    def append(self, text: str) -> None:
        """Add a new prompt to history.

        Args:
            text: The prompt text to add.
        """
        self.prompts.append(text)
        self.curr = None
