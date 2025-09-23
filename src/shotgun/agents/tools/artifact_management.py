"""Artifact management tools for Pydantic AI agents.

These tools provide agents with the ability to create and manage structured
artifacts instead of flat markdown files.
"""

from pydantic_ai import RunContext

from shotgun.agents.models import AgentDeps
from shotgun.artifacts.utils import handle_agent_mode_parsing
from shotgun.logging_config import setup_logger

logger = setup_logger(__name__)


async def create_artifact(
    ctx: RunContext[AgentDeps],
    artifact_id: str,
    agent_mode: str,
    name: str,
    template_id: str = "",
) -> str:
    """Create a new artifact.

    Args:
        ctx: RunContext containing AgentDeps with artifact service
        artifact_id: Unique identifier for the artifact (slug format)
        agent_mode: Agent mode (research, plan, tasks)
        name: Human-readable name for the artifact
        template_id: Optional template ID to use for creating the artifact

    Returns:
        Success message including template content if template was used, or error message

    Example:
        create_artifact("market-analysis", "research", "Market Analysis")
        create_artifact("market-study", "research", "Market Study", "research/market_research")
    """
    logger.debug("🔧 Creating artifact: %s/%s", agent_mode, artifact_id)

    # Parse and validate agent mode
    mode, error_msg = handle_agent_mode_parsing(agent_mode)
    if error_msg:
        logger.error("❌ Create artifact failed: %s", error_msg)
        return f"Error: {error_msg}"
    # Type checker hint: mode is validated above
    if mode is None:
        return "Error: Invalid agent mode"

    try:
        service = ctx.deps.artifact_service

        # Pass template_id if provided and not empty
        template_to_use = template_id.strip() if template_id.strip() else None
        artifact = service.create_artifact(artifact_id, mode, name, template_to_use)

        # Track the artifact file creation
        from shotgun.agents.models import FileOperationType
        from shotgun.utils.file_system_utils import get_shotgun_base_path

        artifact_path = (
            get_shotgun_base_path() / mode.value / artifact_id / "artifact.yaml"
        )
        ctx.deps.file_tracker.add_operation(artifact_path, FileOperationType.CREATED)

        success_msg = (
            f"Created artifact '{artifact_id}' in {agent_mode} mode with name '{name}'"
        )

        # If template was used, include template content in the response
        if artifact.has_template():
            template_content = artifact.load_template_from_file()
            if template_content:
                success_msg += f"\n\nUsing template: {template_content.get('name', artifact.get_template_id())}"

                if "purpose" in template_content:
                    success_msg += f"\nPurpose: {template_content['purpose']}"
                if "prompt" in template_content:
                    success_msg += f"\nPrompt: {template_content['prompt']}"

                if "sections" in template_content and isinstance(
                    template_content["sections"], dict
                ):
                    success_msg += "\nSections to complete:"

                    # Sort sections by order if available
                    sections_dict = template_content["sections"]
                    sorted_sections = sorted(
                        sections_dict.items(),
                        key=lambda x: x[1].get("order", 999)
                        if isinstance(x[1], dict)
                        else 999,
                    )

                    for section_key, section_info in sorted_sections:
                        if isinstance(section_info, dict):
                            instructions = section_info.get("instructions", "")
                            success_msg += f"\n- {section_key}: {instructions}"
                            if section_info.get("depends_on"):
                                depends_on = section_info["depends_on"]
                                if isinstance(depends_on, list):
                                    success_msg += (
                                        f" (depends on: {', '.join(depends_on)})"
                                    )

        logger.debug("✅ %s", success_msg)
        return success_msg

    except Exception as e:
        error_msg = f"Failed to create artifact '{artifact_id}': {str(e)}"
        logger.error("❌ Create artifact failed: %s", error_msg)
        return f"Error: {error_msg}"


async def read_artifact(
    ctx: RunContext[AgentDeps],
    artifact_id: str,
    agent_mode: str,
) -> str:
    """Read all sections of an artifact.

    Args:
        ctx: RunContext containing AgentDeps with artifact service
        artifact_id: Artifact identifier
        agent_mode: Agent mode (research, plan, tasks)

    Returns:
        Combined content of all sections or error message

    Example:
        read_artifact("market-analysis", "research")
    """
    logger.debug("🔧 Reading artifact: %s/%s", agent_mode, artifact_id)

    # Parse and validate agent mode
    mode, error_msg = handle_agent_mode_parsing(agent_mode)
    if error_msg:
        logger.error("❌ Read artifact failed: %s", error_msg)
        return f"Error: {error_msg}"
    # Type checker hint: mode is validated above
    if mode is None:
        return "Error: Invalid agent mode"

    try:
        service = ctx.deps.artifact_service
        artifact = service.get_artifact(artifact_id, mode, "")

        if not artifact.sections:
            return f"Artifact '{artifact_id}' exists but has no sections."

        # Combine all sections with headers
        content_parts = [f"# {artifact.name}\n"]

        # Include template information if artifact was created from a template
        if artifact.has_template():
            template_content = artifact.load_template_from_file()
            if template_content:
                content_parts.append("\n## Template Information\n")
                content_parts.append(f"**Template ID:** {artifact.get_template_id()}\n")

                # Extract template info from the loaded template file
                if "name" in template_content:
                    content_parts.append(f"**Template:** {template_content['name']}\n")
                if "purpose" in template_content:
                    content_parts.append(
                        f"**Purpose:** {template_content['purpose']}\n"
                    )
                if "prompt" in template_content:
                    content_parts.append(f"**Prompt:** {template_content['prompt']}\n")

                if "sections" in template_content and isinstance(
                    template_content["sections"], dict
                ):
                    content_parts.append("\n### Template Sections:\n")

                    # Sort sections by order if available
                    sections_dict = template_content["sections"]
                    sorted_sections = sorted(
                        sections_dict.items(),
                        key=lambda x: x[1].get("order", 999)
                        if isinstance(x[1], dict)
                        else 999,
                    )

                    for section_key, section_info in sorted_sections:
                        if isinstance(section_info, dict):
                            content_parts.append(
                                f"- **{section_key}:** {section_info.get('instructions', '')}"
                            )
                            if section_info.get("depends_on"):
                                depends_on = section_info["depends_on"]
                                if isinstance(depends_on, list):
                                    content_parts.append(
                                        f" *(depends on: {', '.join(depends_on)})*"
                                    )
                            content_parts.append("")

        for section in artifact.get_ordered_sections():
            content_parts.append(f"\n## {section.title}\n")
            if section.content:
                content_parts.append(f"{section.content}\n")

        combined_content = "\n".join(content_parts)
        logger.debug(
            "📄 Read artifact with %d sections (%d characters)",
            len(artifact.sections),
            len(combined_content),
        )
        return combined_content

    except Exception as e:
        error_msg = f"Failed to read artifact '{artifact_id}': {str(e)}"
        logger.error("❌ Read artifact failed: %s", error_msg)
        return f"Error: {error_msg}"


async def write_artifact_section(
    ctx: RunContext[AgentDeps],
    artifact_id: str,
    agent_mode: str,
    section_number: int,
    section_slug: str,
    section_title: str,
    content: str,
) -> str:
    """Write content to a specific section of an artifact.

    Creates the artifact and/or section if they don't exist.

    Args:
        ctx: RunContext containing AgentDeps with artifact service
        artifact_id: Artifact identifier
        agent_mode: Agent mode (research, plan, tasks)
        section_number: Section number (1, 2, 3, etc.)
        section_slug: URL-friendly section identifier
        section_title: Human-readable section title
        content: Section content in markdown

    Returns:
        Success message or error message

    Example:
        write_artifact_section("market-analysis", "research", 1, "overview", "Market Overview", "...")
    """
    logger.debug(
        "🔧 Writing to artifact section: %s/%s section %d",
        agent_mode,
        artifact_id,
        section_number,
    )

    # Parse and validate agent mode
    mode, error_msg = handle_agent_mode_parsing(agent_mode)
    if error_msg:
        logger.error("❌ Write artifact section failed: %s", error_msg)
        return f"Error: {error_msg}"

    # At this point, mode is guaranteed to be not None due to successful validation
    if mode is None:
        return "Error: Agent mode validation failed"

    try:
        service = ctx.deps.artifact_service

        # Get or create the section
        section, created = service.get_or_create_section(
            artifact_id, mode, section_number, section_slug, section_title, content
        )

        # Track the section file operation
        from shotgun.agents.models import FileOperationType
        from shotgun.utils.file_system_utils import get_shotgun_base_path

        section_path = (
            get_shotgun_base_path()
            / mode.value
            / artifact_id
            / f"{section_number:02d}_{section_slug}.md"
        )
        operation = FileOperationType.CREATED if created else FileOperationType.UPDATED
        ctx.deps.file_tracker.add_operation(section_path, operation)

        if created:
            success_msg = (
                f"Created section {section_number} '{section_title}' "
                f"in artifact '{artifact_id}' with {len(content)} characters"
            )
        else:
            # Update existing section content
            service.update_section(artifact_id, mode, section_number, content=content)
            success_msg = (
                f"Updated section {section_number} '{section_title}' "
                f"in artifact '{artifact_id}' with {len(content)} characters"
            )

        logger.debug("✅ %s", success_msg)
        return success_msg

    except Exception as e:
        error_msg = (
            f"Failed to write section {section_number} "
            f"to artifact '{artifact_id}': {str(e)}"
        )
        logger.error("❌ Write artifact section failed: %s", error_msg)
        return f"Error: {error_msg}"


async def read_artifact_section(
    ctx: RunContext[AgentDeps],
    artifact_id: str,
    agent_mode: str,
    section_number: int,
) -> str:
    """Read content from a specific section of an artifact.

    Args:
        ctx: RunContext containing AgentDeps with artifact service
        artifact_id: Artifact identifier
        agent_mode: Agent mode (research, plan, tasks)
        section_number: Section number

    Returns:
        Section content or error message

    Example:
        read_artifact_section("market-analysis", "research", 1)
    """
    logger.debug(
        "🔧 Reading artifact section: %s/%s section %d",
        agent_mode,
        artifact_id,
        section_number,
    )

    # Parse and validate agent mode
    mode, error_msg = handle_agent_mode_parsing(agent_mode)
    if error_msg:
        logger.error("❌ Read artifact section failed: %s", error_msg)
        return f"Error: {error_msg}"

    # At this point, mode is guaranteed to be not None due to successful validation
    if mode is None:
        return "Error: Agent mode validation failed"

    try:
        service = ctx.deps.artifact_service

        section = service.get_section(artifact_id, mode, section_number)

        # Return section content (already contains title header from file storage)
        logger.debug(
            "📄 Read section %d with %d characters",
            section_number,
            len(section.content),
        )
        return section.content

    except Exception as e:
        error_msg = (
            f"Failed to read section {section_number} "
            f"from artifact '{artifact_id}': {str(e)}"
        )
        logger.error("❌ Read artifact section failed: %s", error_msg)
        return f"Error: {error_msg}"


async def list_artifacts(
    ctx: RunContext[AgentDeps],
    agent_mode: str | None = None,
) -> str:
    """List all artifacts, optionally filtered by agent mode.

    Args:
        ctx: RunContext containing AgentDeps with artifact service
        agent_mode: Optional agent mode filter (research, plan, tasks)

    Returns:
        Formatted list of artifacts or error message

    Example:
        list_artifacts("research")
        list_artifacts()  # List all artifacts
    """
    logger.debug("🔧 Listing artifacts for mode: %s", agent_mode or "all")

    try:
        service = ctx.deps.artifact_service

        mode = None
        if agent_mode:
            mode, error_msg = handle_agent_mode_parsing(agent_mode)
            if error_msg:
                logger.error("❌ List artifacts failed: %s", error_msg)
                return f"Error: {error_msg}"

        summaries = service.list_artifacts(mode)

        if not summaries:
            mode_text = f" for {agent_mode}" if agent_mode else ""
            return f"No artifacts found{mode_text}."

        # Format as table
        lines = [
            f"{'Agent':<10} {'ID':<25} {'Sections':<8} {'Updated'}",
            "-" * 55,
        ]

        for summary in summaries:
            lines.append(
                f"{summary.agent_mode.value:<10} "
                f"{summary.artifact_id[:25]:<25} "
                f"{summary.section_count:<8} "
                f"{summary.updated_at.strftime('%Y-%m-%d')}"
            )

        if len(summaries) > 0:
            lines.append(f"\nTotal: {len(summaries)} artifacts")

        result = "\n".join(lines)
        logger.debug("📄 Listed %d artifacts", len(summaries))
        return result

    except Exception as e:
        error_msg = f"Failed to list artifacts: {str(e)}"
        logger.error("❌ List artifacts failed: %s", error_msg)
        return f"Error: {error_msg}"


async def list_artifact_templates(
    ctx: RunContext[AgentDeps],
    agent_mode: str | None = None,
) -> str:
    """List available artifact templates, optionally filtered by agent mode.

    Args:
        ctx: RunContext containing AgentDeps with artifact service
        agent_mode: Optional agent mode filter (research, plan, tasks)

    Returns:
        Formatted list of templates or error message

    Example:
        list_artifact_templates("research")
        list_artifact_templates()  # List all templates
    """
    logger.debug("🔧 Listing templates for mode: %s", agent_mode or "all")

    try:
        service = ctx.deps.artifact_service

        mode = None
        if agent_mode:
            mode, error_msg = handle_agent_mode_parsing(agent_mode)
            if error_msg:
                logger.error("❌ List templates failed: %s", error_msg)
                return f"Error: {error_msg}"

        templates = service.list_templates(mode)

        if not templates:
            mode_text = f" for {agent_mode}" if agent_mode else ""
            return f"No templates found{mode_text}."

        # Format as list with template details
        lines = ["Available Templates:"]

        for template in templates:
            lines.append(f"\n• {template.template_id}")
            lines.append(f"  Name: {template.name}")
            lines.append(f"  Mode: {template.agent_mode.value}")
            lines.append(f"  Purpose: {template.purpose}")
            lines.append(f"  Sections: {template.section_count}")

        result = "\n".join(lines)
        logger.debug("📄 Listed %d templates", len(templates))
        return result

    except Exception as e:
        error_msg = f"Failed to list templates: {str(e)}"
        logger.error("❌ List templates failed: %s", error_msg)
        return f"Error: {error_msg}"
