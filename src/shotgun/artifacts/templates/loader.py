"""Template loader for artifact templates."""

from pathlib import Path

import yaml

from shotgun.artifacts.models import AgentMode
from shotgun.logging_config import setup_logger
from shotgun.utils.file_system_utils import get_shotgun_home

from .models import ArtifactTemplate, TemplateSummary

logger = setup_logger(__name__)

TEMPLATES_DIR = Path(__file__).parent


class ArtifactTemplateLoader:
    """Loads and manages artifact templates from the filesystem."""

    def __init__(
        self, templates_dir: Path | None = None, include_user_templates: bool = True
    ):
        """Initialize the template loader.

        Args:
            templates_dir: Directory containing template files. Defaults to package templates.
            include_user_templates: Whether to include user templates from ~/.shotgun-sh/templates/
        """
        self.templates_dir = templates_dir or TEMPLATES_DIR
        self.include_user_templates = include_user_templates
        self.user_templates_dir = (
            get_shotgun_home() / "templates" if include_user_templates else None
        )

    def _discover_templates(self) -> dict[str, tuple[Path, AgentMode]]:
        """Discover all template files from both built-in and user directories."""
        # Start with built-in templates
        templates = self._discover_templates_from_dir(self.templates_dir, "built-in")

        # Add user templates (they can override built-in ones)
        if (
            self.include_user_templates
            and self.user_templates_dir
            and self.user_templates_dir.exists()
        ):
            user_templates = self._discover_templates_from_dir(
                self.user_templates_dir, "user"
            )
            templates.update(
                user_templates
            )  # User templates override built-in ones with same ID

        return templates

    def _discover_templates_from_dir(
        self, templates_dir: Path, source_type: str
    ) -> dict[str, tuple[Path, AgentMode]]:
        """Discover template files from a specific directory.

        Args:
            templates_dir: Directory to search for templates
            source_type: Type of templates ("built-in" or "user") for logging

        Returns:
            Dictionary mapping template IDs to (path, agent_mode) tuples
        """
        templates: dict[str, tuple[Path, AgentMode]] = {}

        if not templates_dir.exists():
            if source_type == "built-in":
                logger.warning("Templates directory does not exist: %s", templates_dir)
            else:
                logger.debug(
                    "User templates directory does not exist: %s", templates_dir
                )
            return templates

        logger.debug("Discovering %s templates from: %s", source_type, templates_dir)

        for mode_dir in templates_dir.iterdir():
            if not mode_dir.is_dir() or mode_dir.name.startswith("."):
                continue

            # Skip common non-agent directories without warnings
            if mode_dir.name in ("__pycache__", "node_modules", ".git", ".DS_Store"):
                continue

            try:
                agent_mode = AgentMode(mode_dir.name)
            except ValueError:
                logger.warning(
                    "Unknown agent mode directory in %s templates: %s",
                    source_type,
                    mode_dir.name,
                )
                continue

            # Find all YAML files in this mode directory
            for template_file in mode_dir.glob("*.yaml"):
                template_id = template_file.stem
                full_template_id = f"{agent_mode.value}/{template_id}"
                templates[full_template_id] = (template_file, agent_mode)
                logger.debug("Found %s template: %s", source_type, full_template_id)

        return templates

    def _load_template_file(
        self, template_path: Path, agent_mode: AgentMode, template_id: str
    ) -> ArtifactTemplate | None:
        """Load a single template file."""
        try:
            with open(template_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)

            # Validate required fields
            required_fields = ["name", "purpose", "prompt"]
            for field in required_fields:
                if field not in data:
                    logger.error(
                        "Template %s missing required field '%s'", template_path, field
                    )
                    return None

            template = ArtifactTemplate.from_yaml_dict(data, agent_mode, template_id)

            # Validate dependencies
            dependency_errors = template.validate_dependencies()
            if dependency_errors:
                logger.error(
                    "Template %s has dependency errors: %s",
                    template_path,
                    dependency_errors,
                )
                return None

            return template

        except yaml.YAMLError as e:
            logger.error("Failed to parse template YAML %s: %s", template_path, e)
            return None
        except Exception as e:
            logger.error("Failed to load template %s: %s", template_path, e)
            return None

    def get_template(self, template_id: str) -> ArtifactTemplate | None:
        """Get a template by ID.

        Args:
            template_id: Full template ID (e.g., 'research/market_research')

        Returns:
            Template instance or None if not found
        """
        discovered = self._discover_templates()
        if template_id not in discovered:
            return None

        template_path, agent_mode = discovered[template_id]
        return self._load_template_file(template_path, agent_mode, template_id)

    def list_templates(
        self, agent_mode: AgentMode | None = None
    ) -> list[TemplateSummary]:
        """List all available templates, optionally filtered by agent mode.

        Args:
            agent_mode: Optional agent mode filter

        Returns:
            List of template summaries
        """
        discovered = self._discover_templates()
        summaries = []

        for full_template_id, (
            template_path,
            template_agent_mode,
        ) in discovered.items():
            if agent_mode and template_agent_mode != agent_mode:
                continue

            template = self._load_template_file(
                template_path, template_agent_mode, full_template_id
            )
            if template:
                summaries.append(
                    TemplateSummary(
                        template_id=full_template_id,
                        name=template.name,
                        purpose=template.purpose,
                        agent_mode=template.agent_mode,
                        section_count=len(template.sections),
                    )
                )

        # Sort by agent mode, then by template name
        summaries.sort(key=lambda s: (s.agent_mode.value, s.name))
        return summaries

    def get_templates_for_mode(self, agent_mode: AgentMode) -> list[ArtifactTemplate]:
        """Get all templates for a specific agent mode.

        Args:
            agent_mode: Agent mode to filter by

        Returns:
            List of templates for the specified mode
        """
        discovered = self._discover_templates()
        templates = []

        for full_template_id, (
            template_path,
            template_agent_mode,
        ) in discovered.items():
            if template_agent_mode == agent_mode:
                template = self._load_template_file(
                    template_path, template_agent_mode, full_template_id
                )
                if template:
                    templates.append(template)

        templates.sort(key=lambda t: t.name)
        return templates

    def template_exists(self, template_id: str) -> bool:
        """Check if a template exists.

        Args:
            template_id: Template ID to check

        Returns:
            True if template exists, False otherwise
        """
        discovered = self._discover_templates()
        return template_id in discovered

    def get_template_by_short_id(
        self, short_id: str, agent_mode: AgentMode
    ) -> ArtifactTemplate | None:
        """Get template by short ID (without agent mode prefix).

        Args:
            short_id: Short template ID (e.g., 'market_research')
            agent_mode: Agent mode to search within

        Returns:
            Template instance or None if not found
        """
        full_id = f"{agent_mode.value}/{short_id}"
        return self.get_template(full_id)
