"""Configuration management CLI commands."""

import json
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from shotgun.agents.config import ProviderType, get_config_manager
from shotgun.logging_config import get_logger

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
        config = config_manager.initialize()

        # Ask for default provider
        provider_choices = ["openai", "anthropic", "google"]
        console.print("Choose your default AI provider:")
        for i, provider in enumerate(provider_choices, 1):
            console.print(f"  {i}. {provider}")

        while True:
            try:
                choice = typer.prompt("Enter choice (1-3)", type=int)
                if 1 <= choice <= 3:
                    config.default_provider = ProviderType(provider_choices[choice - 1])
                    break
                else:
                    console.print(
                        "❌ Invalid choice. Please enter 1, 2, or 3.", style="red"
                    )
            except ValueError:
                console.print("❌ Please enter a valid number.", style="red")

        # Ask for API key for the selected provider
        provider = config.default_provider
        console.print(f"\n🔑 Setting up {provider.upper()} API key...")

        api_key = typer.prompt(
            f"Enter your {provider.upper()} API key",
            hide_input=True,
            default="",
        )

        if api_key:
            config_manager.update_provider(provider, api_key=api_key)

        config_manager.save()
        console.print(
            f"\n✅ [bold green]Configuration saved to {config_manager.config_path}[/bold green]"
        )
        console.print("🎯 You can now use Shotgun with your configured provider!")

    else:
        config_manager.initialize()
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
    default: Annotated[
        bool,
        typer.Option("--default", "-d", help="Set this provider as default"),
    ] = False,
) -> None:
    """Set configuration for a specific provider."""
    config_manager = get_config_manager()

    # If no API key provided via option and not just setting default, prompt for it
    if api_key is None and not default:
        api_key = typer.prompt(
            f"Enter your {provider.upper()} API key",
            hide_input=True,
            default="",
        )

    try:
        if api_key:
            config_manager.update_provider(provider, api_key=api_key)

        if default:
            config = config_manager.load()
            config.default_provider = provider
            config_manager.save(config)

        console.print(f"✅ Configuration updated for {provider}")

    except Exception as e:
        console.print(f"❌ Failed to update configuration: {e}", style="red")
        raise typer.Exit(1) from e


@app.command()
def set_default(
    provider: Annotated[
        ProviderType,
        typer.Argument(
            help="AI provider to set as default (openai, anthropic, google)"
        ),
    ],
) -> None:
    """Set the default AI provider without modifying API keys."""
    config_manager = get_config_manager()

    try:
        config = config_manager.load()

        # Check if the provider has an API key configured
        provider_config = getattr(config, provider.value)
        if not provider_config.api_key:
            console.print(
                f"⚠️  Warning: {provider.upper()} does not have an API key configured.",
                style="yellow",
            )
            console.print(f"Use 'shotgun config set {provider}' to configure it.")

        # Set as default
        config.default_provider = provider
        config_manager.save(config)

        console.print(f"✅ Default provider set to: {provider}")

    except Exception as e:
        console.print(f"❌ Failed to set default provider: {e}", style="red")
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
    config_manager = get_config_manager()
    config = config_manager.load()

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

    # Default provider
    table.add_row("Default Provider", f"[bold]{config.default_provider}[/bold]")
    table.add_row("", "")  # Separator

    # Provider configurations
    for provider_name, provider_config in [
        ("OpenAI", config.openai),
        ("Anthropic", config.anthropic),
        ("Google", config.google),
    ]:
        table.add_row(f"[bold]{provider_name}[/bold]", "")

        # API Key
        api_key_status = "✅ Set" if provider_config.api_key else "❌ Not set"
        table.add_row("  API Key", api_key_status)
        table.add_row("", "")  # Separator

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
    for provider in ["openai", "anthropic", "google"]:
        if provider in data and isinstance(data[provider], dict):
            if "api_key" in data[provider] and data[provider]["api_key"]:
                data[provider]["api_key"] = _mask_value(data[provider]["api_key"])


def _mask_value(value: str) -> str:
    """Mask a secret value."""
    if len(value) <= 8:
        return "••••••••"
    return f"{value[:4]}{'•' * (len(value) - 8)}{value[-4:]}"


@app.command()
def get_user_id() -> None:
    """Get the anonymous user ID from configuration."""
    config_manager = get_config_manager()

    try:
        user_id = config_manager.get_user_id()
        console.print(f"[green]User ID:[/green] {user_id}")
    except Exception as e:
        logger.error(f"Error getting user ID: {e}")
        console.print(f"❌ Failed to get user ID: {str(e)}", style="red")
        raise typer.Exit(1) from e
