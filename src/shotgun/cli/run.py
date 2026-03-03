"""Run command for shotgun CLI - executes prompts using the Router agent."""

import asyncio
import traceback
from typing import Annotated

import typer

from shotgun.agents.config import ProviderType
from shotgun.agents.models import AgentRuntimeOptions
from shotgun.agents.router import (
    RouterMode,
    create_router_agent,
    run_router_agent,
)
from shotgun.cli.error_handler import print_agent_error
from shotgun.exceptions import UserActionableError
from shotgun.logging_config import get_logger
from shotgun.posthog_telemetry import track_event

app = typer.Typer(
    name="run", help="Run a prompt using the Router agent", no_args_is_help=True
)
logger = get_logger(__name__)


@app.callback(invoke_without_command=True)
def run(
    prompt: Annotated[str, typer.Argument(help="The prompt to execute")],
    non_interactive: Annotated[
        bool,
        typer.Option(
            "--non-interactive", "-n", help="Disable user interaction (for CI/CD)"
        ),
    ] = False,
    provider: Annotated[
        ProviderType | None,
        typer.Option("--provider", "-p", help="AI provider to use (overrides default)"),
    ] = None,
    model: Annotated[
        str | None,
        typer.Option(
            "--model",
            "-m",
            help="Model name to use (e.g., claude-sonnet-4-6, gpt-5.2)",
        ),
    ] = None,
) -> None:
    """Execute a prompt using the Router agent in drafting mode.

    The Router agent orchestrates sub-agents (Research, Specify, Plan, Tasks, Export)
    based on your prompt. In drafting mode, it auto-executes without confirmation.
    """
    logger.info("Running prompt: %s", prompt[:100])

    # If --model is specified, resolve and apply the override
    if model:
        from shotgun.agents.config.models import (
            get_valid_model_names,
            resolve_model_name,
        )
        from shotgun.agents.config.provider import (
            set_general_model_override,
            set_openai_compat_model,
        )
        from shotgun.settings import settings

        resolved = resolve_model_name(model)
        if resolved is not None:
            set_general_model_override(resolved)
        elif settings.openai_compat.base_url:
            # Unknown model but OpenAI-compat is active — backward compatible
            set_openai_compat_model(model)
        else:
            valid_names = get_valid_model_names()
            print(
                f"Error: Unknown model '{model}'.\n"
                f"Valid models: {', '.join(valid_names)}"
            )
            raise typer.Exit(1)

    try:
        asyncio.run(async_run(prompt, non_interactive, provider))
    except Exception as e:
        logger.error("Error during execution: %s", str(e))
        logger.debug("Full traceback:\n%s", traceback.format_exc())


async def async_run(
    prompt: str,
    non_interactive: bool,
    provider: ProviderType | None = None,
) -> None:
    """Async implementation of the run command."""
    track_event(
        "run_command",
        {
            "non_interactive": non_interactive,
            "provider": provider.value if provider else "default",
        },
    )

    # Create agent runtime options
    agent_runtime_options = AgentRuntimeOptions(
        interactive_mode=not non_interactive,
    )

    # Create the router agent
    agent, deps = await create_router_agent(agent_runtime_options, provider)

    # Set drafting mode for CLI (auto-execute without confirmation)
    deps.router_mode = RouterMode.DRAFTING

    logger.info("Starting Router agent in drafting mode...")
    try:
        result = await run_router_agent(agent, prompt, deps)
        print("Complete!")
        print("Response:")
        print(result.output)
    except UserActionableError as e:
        print_agent_error(e)
    except Exception as e:
        logger.exception("Unexpected error in run command")
        print(f"An unexpected error occurred: {str(e)}")
