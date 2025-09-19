"""Models for artifact templates."""

from typing import Any

from pydantic import BaseModel, Field

from shotgun.artifacts.models import AgentMode


class TemplateSection(BaseModel):
    """Represents a section in an artifact template."""

    instructions: str = Field(..., description="Detailed instructions for this section")
    depends_on: list[str] = Field(
        default_factory=list, description="List of section keys this section depends on"
    )

    @property
    def formatted_instructions(self) -> str:
        """Return formatted instructions for display."""
        return self.instructions.strip()


class ArtifactTemplate(BaseModel):
    """Represents an artifact template with structured guidance."""

    name: str = Field(..., description="Display name of the template")
    purpose: str = Field(..., description="Description of what this template is for")
    prompt: str = Field(..., description="System prompt for agents using this template")
    sections: dict[str, TemplateSection] = Field(
        default_factory=dict, description="Template sections with instructions"
    )
    agent_mode: AgentMode = Field(
        ..., description="Agent mode this template belongs to"
    )
    template_id: str = Field(..., description="Unique identifier for the template")

    def get_section(self, section_key: str) -> TemplateSection | None:
        """Get a template section by key."""
        return self.sections.get(section_key)

    def get_ordered_sections(self) -> list[tuple[str, TemplateSection]]:
        """Get sections in dependency order."""
        # Simple topological sort for section dependencies
        ordered = []
        processed = set()

        def process_section(key: str, section: TemplateSection) -> None:
            if key in processed:
                return

            # Process dependencies first
            for dep_key in section.depends_on:
                if dep_key in self.sections and dep_key not in processed:
                    process_section(dep_key, self.sections[dep_key])

            ordered.append((key, section))
            processed.add(key)

        for key, section in self.sections.items():
            process_section(key, section)

        return ordered

    def get_section_keys(self) -> list[str]:
        """Get all section keys."""
        return list(self.sections.keys())

    def validate_dependencies(self) -> list[str]:
        """Validate that all section dependencies exist. Returns list of errors."""
        errors = []

        for section_key, section in self.sections.items():
            for dep_key in section.depends_on:
                if dep_key not in self.sections:
                    errors.append(
                        f"Section '{section_key}' depends on non-existent section '{dep_key}'"
                    )

        return errors

    def to_yaml_dict(self) -> dict[str, Any]:
        """Convert to dictionary suitable for YAML serialization."""
        return {
            "name": self.name,
            "purpose": self.purpose,
            "prompt": self.prompt,
            "template_id": self.template_id,
            "sections": {
                key: {
                    "instructions": section.instructions,
                    **(
                        {"depends_on": section.depends_on} if section.depends_on else {}
                    ),
                }
                for key, section in self.sections.items()
            },
        }

    @classmethod
    def from_yaml_dict(
        cls, data: dict[str, Any], agent_mode: AgentMode, template_id: str
    ) -> "ArtifactTemplate":
        """Create template from YAML dictionary."""
        sections = {}

        for section_key, section_data in data.get("sections", {}).items():
            sections[section_key] = TemplateSection(
                instructions=section_data.get("instructions", ""),
                depends_on=section_data.get("depends_on", []),
            )

        return cls(
            name=data["name"],
            purpose=data["purpose"],
            prompt=data["prompt"],
            sections=sections,
            agent_mode=agent_mode,
            template_id=template_id,
        )


class TemplateSummary(BaseModel):
    """Summary information about a template for listing purposes."""

    template_id: str = Field(..., description="Unique identifier for the template")
    name: str = Field(..., description="Display name of the template")
    purpose: str = Field(..., description="Description of what this template is for")
    agent_mode: AgentMode = Field(
        ..., description="Agent mode this template belongs to"
    )
    section_count: int = Field(..., description="Number of sections in the template")

    def __str__(self) -> str:
        """String representation for CLI display."""
        return f"{self.template_id}: {self.purpose}"
