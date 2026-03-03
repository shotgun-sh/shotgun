"""Configuration management CLI commands."""

import asyncio
import json
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from shotgun.agents.config import ProviderType, get_config_manager
from shotgun.agents.config.constants import ConfigSection
from shotgun.logging_config import get_logger
from shotgun.utils.env_utils import is_shotgun_account_enabled

logger = get_logger(__name__)
console = Console()

app = typer.Typer(
    name="config",
    help="Manage Shotgun configuration",
    no_args_is_help=True,
)


@app.command()
def init(
    interactive: Annotated[
        bool,
        typer.Option("--interactive", "-i", help="Run interactive setup wizard"),
    ] = True,
) -> None:
    """Initialize Shotgun configuration."""
    config_manager = get_config_manager()

    if config_manager.config_path.exists() and not typer.confirm(
        f"Configuration already exists at {config_manager.config_path}. Overwrite?"
    ):
        console.print("❌ Configuration initialization cancelled.", style="red")
        raise typer.Exit(1)

    if interactive:
        console.print(
            "🚀 [bold blue]Welcome to Shotgun Configuration Setup![/bold blue]"
        )
        console.print()

        # Initialize with defaults
        asyncio.run(config_manager.initialize())

        # Ask for provider
        provider_choices = ["openai", "anthropic", "google"]
        console.print("Choose your AI provider:")
        for i, provider in enumerate(provider_choices, 1):
            console.print(f"  {i}. {provider}")

        while True:
            try:
                choice = typer.prompt("Enter choice (1-3)", type=int)
                if 1 <= choice <= 3:
                    provider = ProviderType(provider_choices[choice - 1])
                    break
                else:
                    console.print(
                        "❌ Invalid choice. Please enter 1, 2, or 3.", style="red"
                    )
            except ValueError:
                console.print("❌ Please enter a valid number.", style="red")

        # Ask for API key for the selected provider
        console.print(f"\n🔑 Setting up {provider.upper()} API key...")

        api_key = typer.prompt(
            f"Enter your {provider.upper()} API key",
            hide_input=True,
            default="",
        )

        if api_key:
            # update_provider will automatically set selected_model for first provider
            asyncio.run(config_manager.update_provider(provider, api_key=api_key))

        console.print(
            f"\n✅ [bold green]Configuration saved to {config_manager.config_path}[/bold green]"
        )
        console.print("🎯 You can now use Shotgun with your configured provider!")

    else:
        asyncio.run(config_manager.initialize())
        console.print(f"✅ Configuration initialized at {config_manager.config_path}")


@app.command()
def set(
    provider: Annotated[
        ProviderType,
        typer.Argument(help="AI provider to configure (openai, anthropic, google)"),
    ],
    api_key: Annotated[
        str | None,
        typer.Option("--api-key", "-k", help="API key for the provider"),
    ] = None,
) -> None:
    """Set configuration for a specific provider."""
    config_manager = get_config_manager()

    # If no API key provided via option, prompt for it
    if api_key is None:
        api_key = typer.prompt(
            f"Enter your {provider.upper()} API key",
            hide_input=True,
            default="",
        )

    try:
        if api_key:
            asyncio.run(config_manager.update_provider(provider, api_key=api_key))

        console.print(f"✅ Configuration updated for {provider}")

    except Exception as e:
        console.print(f"❌ Failed to update configuration: {e}", style="red")
        raise typer.Exit(1) from e


@app.command()
def get(
    provider: Annotated[
        ProviderType | None,
        typer.Option("--provider", "-p", help="Show config for specific provider"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON"),
    ] = False,
) -> None:
    """Display current configuration."""
    import asyncio

    config_manager = get_config_manager()
    config = asyncio.run(config_manager.load())

    if json_output:
        # Convert to dict and mask secrets
        data = config.model_dump()
        _mask_secrets(data)
        console.print(json.dumps(data, indent=2))
        return

    if provider:
        # Show specific provider configuration
        _show_provider_config(provider, config)
    else:
        # Show all configuration
        _show_full_config(config)


def _show_full_config(config: Any) -> None:
    """Display full configuration in a table."""
    table = Table(title="Shotgun Configuration", show_header=True)
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="white")

    # Selected model
    selected_model = config.selected_model or "None (will auto-detect)"
    table.add_row("Selected Model", f"[bold]{selected_model}[/bold]")
    table.add_row("", "")  # Separator

    # Provider configurations
    providers_to_show = [
        ("OpenAI", config.openai),
        ("Anthropic", config.anthropic),
        ("Google", config.google),
    ]

    # Only show Shotgun Account if feature flag is enabled
    if is_shotgun_account_enabled():
        providers_to_show.append(("Shotgun Account", config.shotgun))

    for provider_name, provider_config in providers_to_show:
        table.add_row(f"[bold]{provider_name}[/bold]", "")

        # API Key
        api_key_status = "✅ Set" if provider_config.api_key else "❌ Not set"
        table.add_row("  API Key", api_key_status)
        table.add_row("", "")  # Separator

    # Context7 (experimental)
    table.add_row("[bold]Context7 (experimental)[/bold]", "")
    context7_status = "✅ Set" if config.context7.api_key else "❌ Not set"
    table.add_row("  API Key", context7_status)
    table.add_row("", "")

    console.print(table)


def _show_provider_config(provider: ProviderType, config: Any) -> None:
    """Display configuration for a specific provider."""
    provider_str = provider.value if isinstance(provider, ProviderType) else provider

    if provider_str == "openai":
        provider_config = config.openai
    elif provider_str == "anthropic":
        provider_config = config.anthropic
    elif provider_str == "google":
        provider_config = config.google
    elif provider_str == "shotgun":
        provider_config = config.shotgun
    else:
        console.print(f"❌ Unknown provider: {provider}", style="red")
        return

    table = Table(title=f"{provider.upper()} Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="white")

    # API Key
    api_key_status = "✅ Set" if provider_config.api_key else "❌ Not set"
    table.add_row("API Key", api_key_status)

    console.print(table)


def _mask_secrets(data: dict[str, Any]) -> None:
    """Mask secrets in configuration data."""
    sections = [
        ConfigSection.OPENAI.value,
        ConfigSection.ANTHROPIC.value,
        ConfigSection.GOOGLE.value,
        ConfigSection.CONTEXT7.value,
    ]

    # Only mask shotgun if feature flag is enabled
    if is_shotgun_account_enabled():
        sections.append(ConfigSection.SHOTGUN.value)

    for section in sections:
        if section in data and isinstance(data[section], dict):
            if "api_key" in data[section] and data[section]["api_key"]:
                data[section]["api_key"] = _mask_value(data[section]["api_key"])


def _mask_value(value: str) -> str:
    """Mask a secret value."""
    if len(value) <= 8:
        return "••••••••"
    return f"{value[:4]}{'•' * (len(value) - 8)}{value[-4:]}"


@app.command(name="set-model")
def set_model(
    model_name: Annotated[
        str,
        typer.Argument(help="Model name to set as default (e.g., claude-sonnet-4-6)"),
    ],
) -> None:
    """Set the default model for Shotgun.

    Accepts model names in multiple formats:
      - Direct: claude-sonnet-4-6, gpt-5.2
      - Provider-prefixed: anthropic/claude-sonnet-4-6
      - LiteLLM format: gemini/gemini-3.1-pro-preview
    """
    from shotgun.agents.config.models import (
        MODEL_SPECS,
        ProviderType,
        get_valid_model_names,
        resolve_model_name,
    )
    from shotgun.agents.config.provider import _get_api_key, _has_provider_key

    resolved = resolve_model_name(model_name)
    if resolved is None:
        valid_names = get_valid_model_names()
        console.print(
            f"[red]Unknown model: '{model_name}'[/red]\n\n"
            f"[bold]Valid models:[/bold] {', '.join(valid_names)}"
        )
        raise typer.Exit(1)

    # Validate that an API key is available for this model
    config_manager = get_config_manager()
    config = asyncio.run(config_manager.load())
    spec = MODEL_SPECS[resolved]

    # Check key availability in priority order
    has_key = False
    # 1. BYOK key for the model's provider
    if _has_provider_key(config, spec.provider):
        has_key = True
    # 2. Shotgun Account key
    elif _get_api_key(config.shotgun.api_key):
        has_key = True
    # 3. OpenRouter key
    elif _get_api_key(config.openrouter.api_key, "OPENROUTER_API_KEY"):
        has_key = True

    if not has_key:
        env_var_map = {
            ProviderType.OPENAI: "OPENAI_API_KEY",
            ProviderType.ANTHROPIC: "ANTHROPIC_API_KEY",
            ProviderType.GOOGLE: "GEMINI_API_KEY",
        }
        env_var = env_var_map.get(spec.provider, "")
        console.print(
            f"[red]No API key available for {spec.provider.value} to use {resolved.value}.[/red]\n\n"
            f"Set it via: [bold]shotgun config set {spec.provider.value} --api-key <key>[/bold]"
            + (
                f" or set the [bold]{env_var}[/bold] environment variable."
                if env_var
                else "."
            )
        )
        raise typer.Exit(1)

    asyncio.run(config_manager.update_selected_model(resolved))
    console.print(f"[green]Default model set to:[/green] [bold]{resolved.value}[/bold]")


@app.command(name="set-context7")
def set_context7(
    api_key: Annotated[
        str | None,
        typer.Option("--api-key", "-k", help="Context7 API key"),
    ] = None,
) -> None:
    """Set Context7 API key for documentation lookup (experimental)."""
    config_manager = get_config_manager()

    if api_key is None:
        api_key = typer.prompt(
            "Enter your Context7 API key",
            hide_input=True,
            default="",
        )

    if not api_key:
        console.print("❌ No API key provided.", style="red")
        raise typer.Exit(1)

    try:
        asyncio.run(config_manager.update_context7(api_key))
        console.print("✅ Context7 API key configured successfully.")
    except Exception as e:
        console.print(f"❌ Failed to update Context7 configuration: {e}", style="red")
        raise typer.Exit(1) from e


@app.command(name="clear-context7")
def clear_context7() -> None:
    """Remove the Context7 API key."""
    config_manager = get_config_manager()

    try:
        asyncio.run(config_manager.update_context7(None))
        console.print("✅ Context7 API key removed.")
    except Exception as e:
        console.print(f"❌ Failed to clear Context7 configuration: {e}", style="red")
        raise typer.Exit(1) from e


@app.command()
def get_shotgun_instance_id() -> None:
    """Get the anonymous shotgun instance ID from configuration."""
    config_manager = get_config_manager()

    try:
        shotgun_instance_id = config_manager.get_shotgun_instance_id()
        console.print(f"[green]Shotgun Instance ID:[/green] {shotgun_instance_id}")
    except Exception as e:
        logger.error(f"Error getting shotgun instance ID: {e}")
        console.print(f"❌ Failed to get shotgun instance ID: {str(e)}", style="red")
        raise typer.Exit(1) from e
