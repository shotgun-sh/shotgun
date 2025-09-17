"""Template loader utility for managing Jinja2 prompt templates."""

import time
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, Template, select_autoescape

from shotgun.logging_config import setup_logger

logger = setup_logger(__name__)


class PromptLoader:
    """Manages loading and rendering of Jinja2 prompt templates."""

    def __init__(self, templates_dir: str | Path | None = None) -> None:
        """Initialize the prompt loader.

        Args:
            templates_dir: Directory containing templates. Defaults to prompts directory.
        """
        if templates_dir is None:
            templates_dir = Path(__file__).parent
        else:
            templates_dir = Path(templates_dir)

        if not templates_dir.exists():
            raise ValueError(f"Templates directory does not exist: {templates_dir}")

        self.templates_dir = templates_dir
        self.env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=select_autoescape(["j2"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Add common global functions and variables
        self.env.globals.update(
            {
                "now": datetime.now,
                "timestamp": time.time,
                "current_timestamp": lambda: int(time.time()),
                "timestamp_minus": lambda seconds: int(time.time()) - seconds,
            }
        )

        logger.debug("Initialized PromptLoader with templates_dir: %s", templates_dir)

    def load_template(self, template_path: str) -> Template:
        """Load a template from the templates directory.

        Args:
            template_path: Path to template relative to templates directory

        Returns:
            Loaded Jinja2 template
        """
        try:
            template = self.env.get_template(template_path)
            logger.debug("Loaded template: %s", template_path)
            return template
        except Exception as e:
            logger.error("Failed to load template %s: %s", template_path, str(e))
            raise

    def render(self, template_path: str, **context: Any) -> str:
        """Render a template with the given context.

        Args:
            template_path: Path to template relative to templates directory
            **context: Variables to pass to the template

        Returns:
            Rendered template content
        """
        template = self.load_template(template_path)
        try:
            result = template.render(**context)
            logger.debug(
                "Rendered template %s with %d context variables",
                template_path,
                len(context),
            )
            return result
        except Exception as e:
            logger.error("Failed to render template %s: %s", template_path, str(e))
            raise

    def render_string(self, template_string: str, **context: Any) -> str:
        """Render a template from a string.

        Args:
            template_string: Template content as string
            **context: Variables to pass to the template

        Returns:
            Rendered template content
        """
        try:
            template = self.env.from_string(template_string)
            result = template.render(**context)
            logger.debug(
                "Rendered string template with %d context variables", len(context)
            )
            return result
        except Exception as e:
            logger.error("Failed to render string template: %s", str(e))
            raise


# Global instance for the default templates directory
_default_loader: PromptLoader | None = None


def get_prompt_loader() -> PromptLoader:
    """Get the default prompt loader instance.

    Returns:
        Default PromptLoader instance
    """
    global _default_loader
    if _default_loader is None:
        _default_loader = PromptLoader()
    return _default_loader


def render_prompt(template_path: str, **context: Any) -> str:
    """Convenience function to render a template using the default loader.

    Args:
        template_path: Path to template relative to templates directory
        **context: Variables to pass to the template

    Returns:
        Rendered template content
    """
    return get_prompt_loader().render(template_path, **context)
