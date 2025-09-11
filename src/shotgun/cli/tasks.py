"""Tasks command for shotgun CLI."""

from typing import Annotated

import typer

from shotgun.agents.tasks import TasksAgent
from shotgun.logging_config import set_global_log_level, setup_logger

app = typer.Typer(name="tasks", help="Generate task lists with agentic approach")
logger = setup_logger(__name__)


@app.callback(invoke_without_command=True)
def tasks(
    instruction: Annotated[
        str, typer.Argument(help="Task creation instruction or project description")
    ],
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Verbose output")
    ] = False,
    non_interactive: Annotated[
        bool,
        typer.Option(
            "--non-interactive", "-n", help="Disable user interaction (for CI/CD)"
        ),
    ] = False,
) -> None:
    """Generate actionable task lists based on existing research and plans.

    This command creates detailed task breakdowns using AI agents that analyze
    your research and plans to generate prioritized, actionable tasks with
    acceptance criteria and effort estimates.
    """
    # Set log level based on verbose flag
    if verbose:
        set_global_log_level("DEBUG")
        logger.debug("📊 Verbose mode enabled - DEBUG level logging active")

    logger.info("📋 Task Creation Instruction: %s", instruction)

    try:
        # Initialize the tasks agent
        agent = TasksAgent(non_interactive=non_interactive)

        # Start task creation process
        logger.info("🎯 Starting task creation...")
        results = agent.create_tasks_sync(instruction)

        # Display results
        logger.info("✅ Task Creation Complete!")
        logger.info("📋 Results:")
        logger.info("%s", results)
        logger.info("📄 Tasks saved to: .shotgun/tasks.md")

        if verbose:
            logger.debug("📚 Current tasks:")
            logger.debug("%s", agent.get_tasks_history())

    except Exception as e:
        logger.error("❌ Error during task creation: %s", str(e))
        if verbose:
            import traceback

            logger.debug("Full traceback:\n%s", traceback.format_exc())
