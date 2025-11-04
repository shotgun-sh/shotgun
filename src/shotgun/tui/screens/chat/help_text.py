"""Helper functions for chat screen help text."""


def help_text_with_codebase(already_indexed: bool = False) -> str:
    """Generate help text for when a codebase is available.

    Args:
        already_indexed: Whether the codebase is already indexed.

    Returns:
        Formatted help text string.
    """
    return (
        "Howdy! Welcome to Shotgun - Spec Driven Development for Developers and AI Agents.\n\n"
        "Shotgun writes codebase-aware specs for your AI coding agents so they don't derail.\n\n"
        f"{'It' if already_indexed else 'Once your codebase is indexed, it'} can help you:\n"
        "- Research your codebase and spec out new features\n"
        "- Create implementation plans that fit your architecture\n"
        "- Generate AGENTS.md files for AI coding agents\n"
        "- Onboard to existing projects or plan refactors\n\n"
        "Ready to build something? Let's go.\n"
    )


def help_text_empty_dir() -> str:
    """Generate help text for empty directory.

    Returns:
        Formatted help text string.
    """
    return (
        "Howdy! Welcome to Shotgun - Spec Driven Development for Developers and AI Agents.\n\n"
        "Shotgun writes codebase-aware specs for your AI coding agents so they don't derail.\n\n"
        "It can help you:\n"
        "- Research your codebase and spec out new features\n"
        "- Create implementation plans that fit your architecture\n"
        "- Generate AGENTS.md files for AI coding agents\n"
        "- Onboard to existing projects or plan refactors\n\n"
        "Ready to build something? Let's go.\n"
    )
