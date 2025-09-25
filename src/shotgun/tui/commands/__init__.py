"""Command handling for the TUI chat interface."""

from collections.abc import Callable


class CommandHandler:
    """Handles slash commands in the TUI chat interface."""

    def __init__(self) -> None:
        """Initialize the command handler with available commands."""
        self.commands: dict[str, Callable[[], str]] = {
            "help": self.get_help_text,
        }

    def is_command(self, text: str) -> bool:
        """Check if the text is a command (starts with /)."""
        return text.strip().startswith("/")

    def parse_command(self, text: str) -> str:
        """Extract the command name from the text."""
        text = text.strip()
        if not text.startswith("/"):
            return ""

        # Split on whitespace and get the command part
        parts = text[1:].split()
        return parts[0] if parts else ""

    def handle_command(self, text: str) -> tuple[bool, str]:
        """
        Handle a command and return success status and response text.

        Args:
            text: The full command text including the leading /

        Returns:
            Tuple of (success, response_text)
        """
        if not self.is_command(text):
            return False, ""

        command = self.parse_command(text)

        if command in self.commands:
            response = self.commands[command]()
            return True, response
        else:
            return False, self.get_error_message(command)

    def get_help_text(self) -> str:
        """Return the help text for the /help command."""
        return """📚 **Shotgun Help**

**Commands:**
• `/help` - Show this help message

**Keyboard Shortcuts:**
• `Enter` - Send message
• `Ctrl+P` - Open command palette
• `Shift+Tab` - Cycle agent modes
• `Ctrl+C` - Quit application

**Agent Modes:**
• **Research** - Research topics with web search and synthesize findings
• **Specify** - Create detailed specifications and requirements documents
• **Planning** - Create comprehensive, actionable plans with milestones
• **Tasks** - Generate specific, actionable tasks from research and plans
• **Export** - Export artifacts and findings to various formats

**Usage:**
Type your message and press Enter to chat with the AI. The AI will respond based on the current mode."""

    def get_error_message(self, command: str) -> str:
        """Return a polite error message for unknown commands."""
        return f"⚠️ Sorry, `/{command}` is not a recognized command. Type `/help` to see available commands."
