"""Helper functions for chat screen help text."""


def help_text_with_codebase(already_indexed: bool = False) -> str:
    """Generate help text for when a codebase is available.

    Args:
        already_indexed: Whether the codebase is already indexed.

    Returns:
        Formatted help text string.
    """
    return (
        "Howdy! Welcome to Shotgun - the context tool for software engineering. \n\n"
        "You can research, build specs, plan, create tasks, and export context to your "
        "favorite code-gen agents.\n\n"
        f"{'' if already_indexed else 'Once your codebase is indexed, '}I can help with:\n\n"
        "- Speccing out a new feature\n"
        "- Onboarding you onto this project\n"
        "- Helping with a refactor spec\n"
        "- Creating AGENTS.md file for this project\n"
    )


def help_text_empty_dir() -> str:
    """Generate help text for empty directory.

    Returns:
        Formatted help text string.
    """
    return (
        "Howdy! Welcome to Shotgun - the context tool for software engineering.\n\n"
        "You can research, build specs, plan, create tasks, and export context to your "
        "favorite code-gen agents.\n\n"
        "What would you like to build? Here are some examples:\n\n"
        "- Research FastAPI vs Django\n"
        "- Plan my new web app using React\n"
        "- Create PRD for my planned product\n"
    )
